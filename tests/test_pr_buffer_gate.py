"""Regression tests for the relevance-based buffer gate (PR version).

Verifies:
1. Gate fires exactly on schedule (counter not clobbered by finally).
2. keep_ids passed to save_messages protect retained buffered messages
   from the FIFO trim (gate's KEEP decision is not undone).
3. LLM failure falls back without blocking message writes.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mem0.memory.storage import SQLiteManager
from mem0.memory.main import Memory


class FakeLLM:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def generate_response(self, messages, response_format=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated LLM failure")
        prompt = messages[-1]["content"]
        cur_text = re.search(r"## Current Conversation Messages[^#]*", prompt).group(0)
        buf_text = re.search(r"## Buffered Messages[^#]*", prompt).group(0)
        cur_items = re.findall(r"\[(\d+)\] (user|assistant): (.*)", cur_text)
        buf_items = re.findall(r"\[(\d+)\] (user|assistant): (.*)", buf_text)
        admit = [int(i) for i, _, c in cur_items
                 if any(k in c for k in ("代理池", "窗口", "熔断器", "面板", "字体", "排障", "打野池"))]
        keep = [int(i) for i, _, c in buf_items
                if any(k in c for k in ("代理池", "窗口", "熔断器", "面板", "字体", "排障", "打野池"))]
        return json.dumps({"admit_indices": admit, "keep_indices": keep})


class FakeConfig:
    cache_refresh_interval = 5
    cache_refresh_max_batch = 40


def make_host(db, llm, interval=5):
    host = object.__new__(Memory)
    host.config = FakeConfig()
    host.config.cache_refresh_interval = interval
    host.db = db
    host.llm = llm
    return host


def msg(content):
    return {"role": "user", "content": content}


def test_gate_fires_on_schedule():
    db = SQLiteManager(":memory:")
    llm = FakeLLM()
    host = make_host(db, llm, interval=5)
    m = [msg("代理池监控面板重写了")]
    for _ in range(4):
        admitted, keep = host._buffer_gate("s", m)
        db.save_messages(admitted, "s", keep_ids=keep)
    assert llm.calls == 0, f"4 batches should not fire LLM, calls={llm.calls}"
    admitted, keep = host._buffer_gate("s", m)
    db.save_messages(admitted, "s", keep_ids=keep)
    assert llm.calls == 1, f"5th batch must fire LLM, calls={llm.calls}"
    for _ in range(4):
        admitted, keep = host._buffer_gate("s", m)
        db.save_messages(admitted, "s", keep_ids=keep)
    assert llm.calls == 1, f"post-fire batches must not refire, calls={llm.calls}"
    print("✅ gate 按 interval 精确触发, 计数器不被 finally 误重置")


def test_keep_ids_protected_from_fifo():
    db = SQLiteManager(":memory:")
    protected = [msg("代理池状态"), msg("窗口自适应")]
    db.save_messages(protected, "s")
    prot_ids = {m["id"] for m in db.get_all_messages("s")}
    db.save_messages([msg(f"新消息 {i}") for i in range(12)], "s", keep_ids=prot_ids)
    remaining = db.get_all_messages("s")
    contents = {m["content"] for m in remaining}
    assert "代理池状态" in contents, "被保护的旧消息被 FIFO 误删"
    print("✅ keep_ids 保护的消息不被 save_messages FIFO 裁剪")


def test_llm_failure_fallback():
    db = SQLiteManager(":memory:")
    llm = FakeLLM()
    host = make_host(db, llm, interval=1)
    llm.fail = True
    admitted, keep = host._buffer_gate("s", [msg("代理池状态如何")])
    assert len(admitted) == 1, "LLM 失败不应阻塞消息写入"
    db.save_messages(admitted, "s", keep_ids=keep)
    assert len(db.get_all_messages("s")) == 1
    print("✅ LLM 失败时消息照常写入")


if __name__ == "__main__":
    test_gate_fires_on_schedule()
    test_keep_ids_protected_from_fifo()
    test_llm_failure_fallback()
    print("\n✅ PR-A 回归测试通过")
