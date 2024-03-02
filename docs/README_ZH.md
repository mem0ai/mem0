<p align="center">
  <img src="docs/logo/dark.svg" width="400px" alt="Embedchain Logo">
</p>

<p align="center">
  <a href="https://runacap.com/ross-index/q3-2023/" target="_blank" rel="noopener"><img style="width: 260px; height: 56px" src="https://runacap.com/wp-content/uploads/2023/10/ROSS_badge_black_Q3_2023.svg" alt="ROSS Index - Fastest Growing Open-Source Startups in Q3 2023 | Runa Capital" width="260" height="56"/></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/embedchain/">
    <img src="https://img.shields.io/pypi/v/embedchain" alt="PyPI">
  </a>
  <a href="https://pepy.tech/project/embedchain">
    <img src="https://static.pepy.tech/badge/embedchain" alt="Downloads">
  </a>
  <a href="https://embedchain.ai/slack">
    <img src="https://img.shields.io/badge/slack-embedchain-brightgreen.svg?logo=slack" alt="Slack">
  </a>
  <a href="https://embedchain.ai/discord">
    <img src="https://dcbadge.vercel.app/api/server/6PzXDgEjG5?style=flat" alt="Discord">
  </a>
  <a href="https://twitter.com/embedchain">
    <img src="https://img.shields.io/twitter/follow/embedchain" alt="Twitter">
  </a>
  <a href="https://colab.research.google.com/drive/138lMWhENGeEu7Q1-6lNbNTHGLZXBBz_B?usp=sharing">
    <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open in Colab">
  </a>
  <a href="https://codecov.io/gh/embedchain/embedchain">
    <img src="https://codecov.io/gh/embedchain/embedchain/graph/badge.svg?token=EMRRHZXW1Q" alt="codecov">
  </a>
</p>

<p align="center">
    <a href="../README.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
</p>

<hr />

## 什么是 Embedchain?

Embedchain 是一个开源 RAG 框架，可以轻松创建和部署 AI 应用程序。 Embedchain 的核心遵循“传统但可配置”的设计原则，为软件工程师和机器学习工程师服务。

Embedchain 简化了检索增强生成 (RAG) 应用程序的创建，为管理各种类型的非结构化数据提供了无缝流程。 它有效地将数据分割成可管理的块，生成相关的嵌入，并将其存储在向量数据库中以优化检索。 借助一套不同的 API，它使用户能够提取上下文信息、找到精确的答案或进行交互式聊天对话，所有这些都是根据自己的数据量身定制的。

## 🔧 快速安装

### Python API

```bash
pip install embedchain
```

## ✨ 实时演示

了解关于Embedchain创建的 [Chat with PDF](https://embedchain.ai/demo/chat-pdf) 实时演示，同时您也可以在 [这里](https://github.com/embedchain/embedchain/tree/main/examples/chat-pdf) 找到源代码。

## 🔍 用法

<!-- Demo GIF or Image -->
<p align="center">
  <img src="docs/images/cover.gif" width="900px" alt="Embedchain Demo">
</p>

例如，您可以使用以下代码创建 Elon Musk 机器人：

```python
import os
from embedchain import App

# 创建机器人
os.environ["OPENAI_API_KEY"] = "YOUR API KEY"
elon_bot = App()

# 嵌入在线资源
elon_bot.add("https://en.wikipedia.org/wiki/Elon_Musk")
elon_bot.add("https://www.forbes.com/profile/elon-musk")

# 查询机器人
elon_bot.query("How many companies does Elon Musk run and name those?")
# Answer: Elon Musk currently runs several companies. As of my knowledge, he is the CEO and lead designer of SpaceX, the CEO and product architect of Tesla, Inc., the CEO and founder of Neuralink, and the CEO and founder of The Boring Company. However, please note that this information may change over time, so it's always good to verify the latest updates.
```

您还可以在浏览器中使用 Google Colab 进行尝试：

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/17ON1LPonnXAtLaZEebnOktstB_1cJJmh?usp=sharing)

## 📖 文档
综合指南和 API 文档可帮助您充分利用 Embedchain：

- [介绍](https://docs.embedchain.ai/get-started/introduction#what-is-embedchain)
- [入门](https://docs.embedchain.ai/get-started/quickstart)
- [例子](https://docs.embedchain.ai/examples)
- [支持的数据类型](https://docs.embedchain.ai/components/data-sources/overview)

## 🔗 加入社区

* 加入我们的社区，与其他开发人员建立联系 [Slack 社区](https://embedchain.ai/slack) or [Discord 社区](https://embedchain.ai/discord).

* 深入 [GitHub 讨论](https://github.com/embedchain/embedchain/discussions)，提出问题或分享您的经验。

## 🤝 安排一对一会议

与创始人预订[一对一会议](https://cal.com/taranjeetio/ec)，讨论任何问题、提供反馈或探索我们如何为您改进 Embedchain。

## 🌐 贡献

欢迎贡献！ 请检查存储库上的问题，并随时提出拉取请求。
有关更多信息，请参阅[贡献指南](CONTRIBUTING.md)。

如需更多参考，请参阅[开发指南](https://docs.embedchain.ai/contribution/dev)和[文档指南](https://docs.embedchain.ai/contribution/docs)。

<a href="https://github.com/embedchain/embedchain/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=embedchain/embedchain" />
</a>

## 匿名遥测

我们收集匿名使用指标以提高软件包的质量和用户体验。 这包括功能使用频率和系统信息等数据，但绝不包括个人详细信息。 这些数据帮助我们确定改进的优先顺序并确保兼容性。 如果您希望选择退出，请设置环境变量“EC_TELEMETRY=false”。 我们优先考虑数据安全，不会与外部共享这些数据。

## 引文

如果您使用此存储库，请考虑使用以下方式引用它：

```
@misc{embedchain,
  author = {Taranjeet Singh, Deshraj Yadav},
  title = {Embedchain: The Open Source RAG Framework},
  year = {2023},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/embedchain/embedchain}},
}
```