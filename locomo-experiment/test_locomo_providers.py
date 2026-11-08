import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import mem0
from openai import OpenAI

import locomo_pilot
import locomo_threshold_ablation
from locomo_pilot import State
from locomo_providers import PROVIDERS, Provider, configure_provider, validate_provider


class ProviderTests(unittest.TestCase):
    def test_endpoints_and_run_directories_are_separate(self):
        official = PROVIDERS["openai"]
        default = PROVIDERS["zhizengzeng"]
        self.assertEqual(official.base_url, "https://api.openai.com/v1")
        self.assertEqual(default.base_url, "https://api.zhizengzeng.com/v1")
        self.assertNotEqual(official.run, default.run)
        self.assertNotEqual(official.key_file, default.key_file)

    def test_official_chat_and_embeddings_use_official_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key_file = root / "openai.key"
            key_file.write_text("test-key", encoding="utf-8")
            provider = Provider("openai", "https://api.openai.com/v1", key_file, root / "run")
            requests = []

            def handle(request):
                requests.append(request)
                if request.url.path.endswith("/embeddings"):
                    return httpx.Response(200, json={
                        "object": "list", "data": [{"object": "embedding", "index": 0, "embedding": [0.1]}],
                        "model": "text-embedding-3-small", "usage": {"prompt_tokens": 1, "total_tokens": 1},
                    })
                return httpx.Response(200, json={
                    "id": "test", "object": "chat.completion", "created": 0, "model": "gpt-4o-mini",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                })

            with patch.dict(PROVIDERS, {"openai": provider}), patch.dict(os.environ, {}, clear=False):
                selected, key = configure_provider("openai")
                with httpx.Client(transport=httpx.MockTransport(handle)) as http:
                    client = OpenAI(api_key=key, base_url=selected.base_url, http_client=http)
                    client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "test"}])
                    client.embeddings.create(model="text-embedding-3-small", input="test")
                self.assertEqual(os.environ["OPENAI_BASE_URL"], provider.base_url)
                self.assertEqual(os.environ["MEM0_DIR"], str(provider.run / "mem0-home"))
            self.assertEqual([str(r.url) for r in requests], [
                "https://api.openai.com/v1/chat/completions",
                "https://api.openai.com/v1/embeddings",
            ])

    def test_missing_and_empty_key_fail_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "missing.key"
            provider = Provider("openai", "https://api.openai.com/v1", key_file, Path(directory) / "run")
            with patch.dict(PROVIDERS, {"openai": provider}):
                with self.assertRaises(FileNotFoundError):
                    configure_provider("openai")
                key_file.write_text("", encoding="utf-8")
                with self.assertRaises(ValueError):
                    configure_provider("openai")

    def test_baseline_initializes_the_selected_provider_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("zhizengzeng", "openai"):
                with self.subTest(provider=name):
                    key_file = root / f"{name}.key"
                    key_file.write_text("test-key", encoding="utf-8")
                    provider = Provider(name, PROVIDERS[name].base_url, key_file, root / name)
                    memory = MagicMock()
                    with (
                        patch.dict(PROVIDERS, {name: provider}),
                        patch.dict(os.environ, {}, clear=False),
                        patch.object(mem0.Memory, "from_config", return_value=memory) as factory,
                        patch.object(locomo_pilot, "OpenAI") as client,
                        patch.object(sys, "argv", ["locomo_pilot.py", "--provider", name, "--max-ingest", "0"]),
                    ):
                        locomo_pilot.main()
                        config = factory.call_args.args[0]
                        self.assertEqual(config["llm"]["config"]["openai_base_url"], provider.base_url)
                        self.assertEqual(config["embedder"]["config"]["openai_base_url"], provider.base_url)
                        self.assertEqual(config["vector_store"]["config"]["path"], str(provider.run / "qdrant"))
                        self.assertTrue(all(call.kwargs["base_url"] == provider.base_url for call in client.call_args_list))
                        self.assertEqual(client.call_count, 3)
                        memory.add.assert_not_called()
                        self.assertEqual(json.loads((provider.run / "state.json").read_text())["provider"], name)

    def test_provider_mismatch_is_rejected_and_legacy_default_is_accepted(self):
        validate_provider({}, "zhizengzeng")
        with self.assertRaises(RuntimeError):
            validate_provider({}, "openai")
        with self.assertRaises(RuntimeError):
            validate_provider({"provider": "zhizengzeng"}, "openai")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = Provider("openai", "https://api.openai.com/v1", root / "key", root / "run")
            state = State(provider)
            self.assertEqual(json.loads(state.path.read_text())["provider"], "openai")
            State(provider)

    def test_threshold_uses_selected_baseline_and_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = Provider("openai", PROVIDERS["openai"].base_url, root / "key", root / "run")
            provider.key_file.write_text("test-key", encoding="utf-8")
            provider.run.mkdir()
            dataset = json.loads(locomo_pilot.DATASET.read_text(encoding="utf-8"))[0]
            ids = [i for i, question in enumerate(dataset["qa"]) if question["category"] == 4]
            dataset_hash = hashlib.sha256(locomo_pilot.DATASET.read_bytes()).hexdigest()
            questions = {
                str(i): {
                    "question": dataset["qa"][i]["question"], "gold": str(dataset["qa"][i]["answer"]),
                    "answer": "test", "memories": [[], []], "judgments": ["WRONG"] * 10,
                    "retrieval_seconds": 0, "answer_seconds": 0,
                }
                for i in ids
            }
            baseline_path = provider.run / "state.json"
            baseline_path.write_text(json.dumps({
                "provider": "openai", "dataset_sha256": dataset_hash, "inflight_ingest": [],
                "questions": questions,
            }), encoding="utf-8")
            (provider.run / "sample-70-seed-42.json").write_text(json.dumps({
                "dataset_sha256": dataset_hash, "question_indices": ids,
            }), encoding="utf-8")
            output = provider.run / "threshold05-ablation"
            output.mkdir()
            usage = {
                name: {"input_tokens": 0, "output_tokens": 0, "embedding_tokens": 0, "calls": 0}
                for name in ("search", "answer", "judge")
            }
            (output / "state.json").write_text(json.dumps({
                "provider": "openai", "dataset_sha256": dataset_hash, "top_k": 30, "threshold": 0.5,
                "question_indices": ids, "baseline_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                "judge_runs": 10, "questions": questions, "usage_by_phase": usage, "responses_without_usage": 0,
            }), encoding="utf-8")
            with (
                patch.dict(PROVIDERS, {"openai": provider}),
                patch.dict(os.environ, {}, clear=False),
                patch.object(mem0.Memory, "from_config") as factory,
                patch.object(locomo_threshold_ablation, "OpenAI") as client,
                patch.object(sys, "argv", ["locomo_threshold_ablation.py", "--provider", "openai",
                                           "--max-questions", "1"]),
            ):
                locomo_threshold_ablation.main()
                config = factory.call_args.args[0]
                self.assertEqual(config["vector_store"]["config"]["path"], str(provider.run / "qdrant"))
                self.assertEqual(config["llm"]["config"]["openai_base_url"], provider.base_url)
                self.assertEqual(client.call_args.kwargs["base_url"], provider.base_url)
                self.assertEqual(json.loads((output / "summary.json").read_text())["provider"], "openai")


if __name__ == "__main__":
    unittest.main()
