<p align="center">
  <a href="https://github.com/mem0ai/mem0">
    <img src="images/banner-sm.png" width="800px" alt="Mem0 - 面向个性化 AI 的智能记忆层">
  </a>
</p>

<h1 align="center">Mem0 — 面向个性化 AI 与智能体的核心记忆层</h1>

<p align="center">
  <a href="../README.md">English</a> · <b>简体中文</b>
</p>

<p align="center">
  <a href="https://mem0.ai">了解更多</a>
  ·
  <a href="https://mem0.dev/DiG">加入 Discord</a>
  ·
  <a href="https://mem0.dev/demo">在线演示</a>
</p>

<p align="center">
  <a href="https://mem0.dev/DiG">
    <img src="https://img.shields.io/badge/Discord-%235865F2.svg?&logo=discord&logoColor=white" alt="Mem0 Discord">
  </a>
  <a href="https://pepy.tech/project/mem0ai">
    <img src="https://img.shields.io/pypi/dm/mem0ai" alt="Mem0 PyPI - 下载量">
  </a>
  <a href="https://github.com/mem0ai/mem0">
    <img src="https://img.shields.io/github/commit-activity/m/mem0ai/mem0?style=flat-square" alt="GitHub 提交活跃度">
  </a>
  <a href="https://pypi.org/project/mem0ai" target="blank">
    <img src="https://img.shields.io/pypi/v/mem0ai?color=%2334D058&label=pypi%20package" alt="PyPI 版本">
  </a>
  <a href="https://www.npmjs.com/package/mem0ai" target="blank">
    <img src="https://img.shields.io/npm/v/mem0ai" alt="Npm 版本">
  </a>
  <a href="https://www.ycombinator.com/companies/mem0">
    <img src="https://img.shields.io/badge/Y%20Combinator-S24-orange?style=flat-square" alt="Y Combinator S24 孵化项目">
  </a>
</p>

<p align="center">
  <a href="https://mem0.ai/research"><strong>📄 基准评测：Mem0 高 Token 效率记忆算法研究论文 →</strong></a>
</p>

## 全新记忆算法 (2026年4月发布)

| 基准评测 (Benchmark) | 原版算法 | 全新算法 | Token 消耗 | P50 延迟 |
| --- | --- | --- | --- | --- |
| **LoCoMo** | 71.4 | **92.5** | 7.0K | 0.88s |
| **LongMemEval** | 67.8 | **94.4** | 6.8K | 1.09s |
| **BEAM (1M)** | — | **64.1** | 6.7K | 1.00s |
| **BEAM (10M)** | — | **48.6** | 6.9K | 1.05s |

所有基准测试均运行在代表生产环境的标准模型栈上。单次检索（单次调用，无需复杂的 Agent 循环）处于 top_200 的检索预算限制下。评测分数反映了 Mem0 全托管云平台的性能表现（云平台包含部分未在开源 SDK 中开放的专有级加速）；开源版用户可以预期获得方向一致的显著性能跃升。

**重大架构升级亮点：**
- **单次直出式 ADD 增量抽取** —— 单次 LLM 推理调用，不执行复杂的 UPDATE/DELETE 覆写，记忆持续增量沉淀且永不丢失。
- **Agent 生成的事实升级为一等公民** —— 当智能体确认执行了一项操作，该确认信息与外部输入享有同等权重存入记忆。
- **实体链接 (Entity Linking)** —— 自动化抽取实体、计算 Embedding 并跨记忆单元建立图谱关联，显著提升召回准确度。
- **多信号融合检索 (Multi-signal Retrieval)** —— 语义向量匹配、BM25 关键词匹配以及实体匹配三路并行打分并融合排序。
- **时序推理 (Temporal Reasoning)** —— 感知时间的智能检索，能够精准区分并排序当前状态、历史事件和未来规划相关的查询。

查阅 [版本升级迁移指南](https://docs.mem0.ai/migration/oss-v2-to-v3) 获取升级指引。我们的 [评测基准套件](https://github.com/mem0ai/memory-benchmarks) 完全开源，任何人均可自由复现上述数据。

## 科研亮点 (Research Highlights)
- **LoCoMo 得分 92.5** —— 较上一代算法大幅提升 +21 分
- **LongMemEval 得分 94.4** —— 提升 +27 分，智能体交互记忆召回率高达 98.2
- **BEAM (1M) 得分 64.1** —— 在 100 万 Token 规模下的生产级记忆基准评估
- [阅读完整学术论文](https://mem0.ai/research)

# 项目介绍 (Introduction)

[Mem0](https://mem0.ai)（读作 "mem-zero"）为各类 AI 助手与智能体构建智能化记忆中枢，实现高度个性化的人机交互。它能够记住用户偏好、自适应个体需求并在长期交互中持续进化学习——是客户服务、个人 AI 助理与全自主智能体系统的理想记忆方案。

### 核心特性与应用领域

**核心技术能力：**
- **多层次记忆体系 (Multi-Level Memory)**：无缝保留用户（User）、会话（Session）与智能体（Agent）状态，支持自适应个性化。
- **开发者极度友好**：直观极简的 API、跨平台 SDK（Python / TypeScript）以及全托管免运维云服务。

**典型应用场景：**
- **AI 个人助理**：提供始终如一、富含上下文沉淀的深度对话。
- **智能客户支持**：自动关联过往工单与用户历史记录，提供定制化解答。
- **医疗健康与陪伴**：记录个体生活习惯与病史偏好，赋能定制化健康关怀。
- **效率工具与游戏 AI**：根据用户习惯自适应工作流与游戏虚拟世界。

## 🚀 快速上手指南 (Quickstart Guide)

### AI 智能体一键注册

AI 智能体可以在 5 秒内自助生成可用的 Mem0 API Key —— 无需邮箱、无需控制台、无需短信验证码，仅需四条命令：

```bash
# 1. 安装 CLI 工具
npm install -g @mem0/cli      # 或使用: pip install mem0-cli

# 2. 以智能体身份初始化（将 `claude-code` 替换为你的智能体名称）
mem0 init --agent --agent-caller claude-code

# 3. 写入一条记忆
mem0 add "I am using mem0"

# 4. 搜索检索记忆
mem0 search "am I using mem0"
```

人类开发者后续只需运行 `mem0 init --email <your-email>` 即可认领该账户 —— API Key 保持不变，已有记忆完全保留。详见 [智能体注册指南](https://docs.mem0.ai/platform/agent-signup)。

### 架构方案选型对比

| 对比维度 | 开源开发库 (Library) | 私有化部署服务器 (Self-Hosted) | 全托管云平台 (Cloud Platform) |
|---|---|---|---|
| **最适合场景** | 本地测试、原型快速验证 | 需在企业私有云/本地基础设施运行的团队 | 零运维生产环境部署 |
| **安装配置** | `pip install mem0ai` | `docker compose up` | 注册即可使用 [app.mem0.ai](https://app.mem0.ai?utm_source=oss&utm_medium=readme) |
| **可视化控制台** | — | [支持](https://docs.mem0.ai/open-source/setup) | 完整支持 |
| **鉴权与 API Key 管理** | — | 包含 | 完整包含 |
| **企业级高级特性** | — | 基础体验 | 全功能包含 |

仅需简单体验？请使用开发库；团队私有环境构建？请选用自托管服务器；希望专注业务免除运维？请选择托管云平台。

### 1. 开发库安装 (pip / npm)

```bash
pip install mem0ai
```

如需启用支持 BM25 关键词匹配与实体抽取的增强混合检索，可安装 NLP 扩展：

```bash
pip install mem0ai[nlp]
python -m spacy download en_core_web_sm
```

使用 Node.js / TypeScript 开发：

```bash
npm install mem0ai
```

### 2. 私有化部署服务器 (Self-Hosted Server)

> **注意：** 自托管部署默认启用鉴权。如从旧版本升级，请配置 `ADMIN_API_KEY`，通过浏览器向导注册管理员账户，或仅在本地开发时设置 `AUTH_DISABLED=true`。详见 [升级说明](https://docs.mem0.ai/open-source/setup#upgrade-notes)。

```bash
# 推荐方式：单命令启动全套服务、创建管理员并颁发第一个 API Key
cd server && make bootstrap

# 手动模式：通过 Docker Compose 启动并通过网页向导配置
cd server && docker compose up -d    # 访问 http://localhost:3000
```

配置详情请参阅 [自托管技术文档](https://docs.mem0.ai/open-source/overview)。

### 3. 全托管云平台 (Cloud Platform)

1. 在 [Mem0 官方控制台](https://app.mem0.ai?utm_source=oss&utm_medium=readme) 注册账户
2. 获取 API Key，通过 SDK 轻松集成智能记忆层
3. 如需迁移已有 Qdrant 向量数据，请查阅 [数据迁移指南](https://docs.mem0.ai/migration/oss-to-platform)。

### 4. 命令行工具 (CLI)

在终端中快速管理记忆：

```bash
npm install -g @mem0/cli   # 或: pip install mem0-cli

mem0 init
mem0 add "Prefers dark mode and vim keybindings" --user-id alice
mem0 search "What does Alice prefer?" --user-id alice
```

完整命令请查阅 [CLI 官方文档](https://docs.mem0.ai/platform/cli)。

### 5. Agent Skills (智能编程助手技能扩展)

让你的 AI 编程助手（Claude Code、Codex、Cursor、Windsurf、OpenCode、OpenClaw 等符合 Skills 规范的工具）掌握构建 Mem0 的专业能力：

**参考知识技能（常驻助手上下文）：**
```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0
npx skills add https://github.com/mem0ai/mem0 --skill mem0-cli
npx skills add https://github.com/mem0ai/mem0 --skill mem0-vercel-ai-sdk
```

**工作流流水线技能（在现有工程中按需调用）：**
```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-integrate
npx skills add https://github.com/mem0ai/mem0 --skill mem0-test-integration
npx skills add https://github.com/mem0ai/mem0 --skill mem0-oss-to-platform
```

使用 `/mem0-integrate` 在现有代码库中以测试驱动方式快速接入 Mem0，使用 `/mem0-test-integration` 进行端到端验证，或使用 `/mem0-oss-to-platform` 从开源 SDK 平滑迁移至云平台。详见 [技能目录](../skills/)。

---

## 💻 基础 Python 实战示例

Mem0 依赖大语言模型完成信息抽取与检索，默认使用 OpenAI 的 `gpt-5-mini`，同时支持国内外主流各类开源和闭源 LLM（详见 [支持的 LLM 文档](https://docs.mem0.ai/components/llms/overview)）。
默认向量嵌入模型为 `text-embedding-3-small`，混合检索推荐搭配 [Qwen 600M](https://huggingface.co/Alibaba-NLP/gte-Qwen2-1.5B-instruct) 等高质量嵌入模型使用（详见 [支持的 Embedding 模型](https://docs.mem0.ai/components/embedders/overview)）。

```python
from openai import OpenAI
from mem0 import Memory

openai_client = OpenAI()
memory = Memory()

def chat_with_memories(message: str, user_id: str = "default_user") -> str:
    # 1. 检索与当前输入最相关的 Top-3 历史记忆
    relevant_memories = memory.search(query=message, filters={"user_id": user_id}, top_k=3)
    memories_str = "
".join(f"- {entry[memory]}" for entry in relevant_memories["results"])

    # 2. 将历史记忆注入 System Prompt 构建回复
    system_prompt = f"你是一名贴心的智能助手。请结合用户提问与历史记忆进行回答。
用户历史记忆：
{memories_str}"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]
    response = openai_client.chat.completions.create(model="gpt-5-mini", messages=messages)
    assistant_response = response.choices[0].message.content

    # 3. 将新一轮对话自动沉淀为新记忆
    messages.append({"role": "assistant", "content": assistant_response})
    memory.add(messages, user_id=user_id)

    return assistant_response

def main():
    print("AI 智能对话已启动（输入 exit 退出）")
    while True:
        user_input = input("你: ").strip()
        if user_input.lower() == "exit":
            print("再见！")
            break
        print(f"AI: {chat_with_memories(user_input)}")

if __name__ == "__main__":
    main()
```

---

## 🔗 生态集成与演示 (Integrations & Demos)

- **带持久记忆的 ChatGPT**：基于 Mem0 打造的个性化对话系统（[在线 Demo](https://mem0.dev/demo)）
- **全平台浏览器插件**：跨 ChatGPT、Perplexity 与 Claude 统一同步持久记忆（[Chrome 插件商店](https://chromewebstore.google.com/detail/onihkkbipkfeijkadecaafbgagkhglop?utm_source=item-share-cb)）
- **LangGraph 集成**：使用 LangGraph + Mem0 构建企业级智能客服机器人（[集成指南](https://docs.mem0.ai/integrations/langgraph)）
- **CrewAI 集成**：使用 Mem0 为多智能体团队定制个性化输出（[实战范例](https://docs.mem0.ai/integrations/crewai)）

## 📚 文档与技术支持

- 官方文档：https://docs.mem0.ai
- 开发者社区：[Discord](https://mem0.dev/DiG) · [X / Twitter](https://x.com/mem0ai)
- 团队联系邮箱：founders@mem0.ai

## 📖 学术引用 (Citation)

如在学术研究中使用了 Mem0，欢迎引用我们的论文：

```bibtex
@article{mem0,
  title={Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory},
  author={Chhikara, Prateek and Khant, Dev and Aryan, Saket and Singh, Taranjeet and Yadav, Deshraj},
  journal={arXiv preprint arXiv:2504.19413},
  year={2025}
}
```

## ⚖️ 开源许可证 (License)

遵循 [Apache 2.0](https://github.com/mem0ai/mem0/blob/main/LICENSE) 协议开源。

---

> 💡 **文档维护说明**：本中文文档由社区志愿者（@JasonYeYuhe）翻译维护，最后同步更新于 2026年9月1日。如发现内容与官方英文原版存在差异或新特性滞后，欢迎提交 PR 共同完善！
