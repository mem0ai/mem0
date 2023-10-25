# embedchain

[![PyPI](https://img.shields.io/pypi/v/embedchain)](https://pypi.org/project/embedchain/)
[![Slack](https://img.shields.io/badge/slack-embedchain-brightgreen.svg?logo=slack)](https://join.slack.com/t/embedchain/shared_invite/zt-22uwz3c46-Zg7cIh5rOBteT_xe1jwLDw)
[![Discord](https://dcbadge.vercel.app/api/server/6PzXDgEjG5?style=flat)](https://discord.gg/CUU9FPhRNt)
[![Twitter](https://img.shields.io/twitter/follow/embedchain)](https://twitter.com/embedchain)
[![Substack](https://img.shields.io/badge/Substack-%23006f5c.svg?logo=substack)](https://embedchain.substack.com/)
[![Open in Colab](https://camo.githubusercontent.com/84f0493939e0c4de4e6dbe113251b4bfb5353e57134ffd9fcab6b8714514d4d1/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/138lMWhENGeEu7Q1-6lNbNTHGLZXBBz_B?usp=sharing)
[![codecov](https://codecov.io/gh/embedchain/embedchain/graph/badge.svg?token=EMRRHZXW1Q)](https://codecov.io/gh/embedchain/embedchain)

Embedchain is a Data Platform for LLMs - load, index, retrieve, and sync any unstructured data. Using embedchain, you can easily create LLM powered apps over any data. If you want a javascript version, check out [embedchain-js](https://github.com/embedchain/embedchain/tree/main/embedchain-js)

## Community

* Join embedchain community on slack by accepting [this invite](https://join.slack.com/t/embedchain/shared_invite/zt-22uwz3c46-Zg7cIh5rOBteT_xe1jwLDw)

## 🤝 Schedule a 1-on-1 Session

Book a [1-on-1 Session](https://cal.com/taranjeetio/ec) with Taranjeet, the founder, to discuss any issues, provide feedback, or explore how we can improve Embedchain for you.

## 🔧 Quick install

```bash
pip install --upgrade embedchain
```

## 🔍 Demo

Try out embedchain in your browser:

[![Open in Colab](https://camo.githubusercontent.com/84f0493939e0c4de4e6dbe113251b4bfb5353e57134ffd9fcab6b8714514d4d1/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/17ON1LPonnXAtLaZEebnOktstB_1cJJmh?usp=sharing)

## 📖 Documentation

The documentation for embedchain can be found at [docs.embedchain.ai](https://docs.embedchain.ai).

## 💻 Usage

Embedchain empowers you to create ChatGPT like apps, on your own dynamic dataset.

### Data Types Supported

* Youtube video
* PDF file
* Web page
* Sitemap
* Doc file
* JSON file
* Code documentation website loader
* OpenAPI specs
* Notion
* Unstructured file loader and many more

You can find the full list of data types on [our documentation](https://docs.embedchain.ai/data-sources/csv).

### Queries

For example, you can use Embedchain to create an Elon Musk bot using the following code:

```python
import os
from embedchain import App

# Create a bot instance
os.environ["OPENAI_API_KEY"] = "YOUR API KEY"
elon_bot = App()

# Embed online resources
elon_bot.add("https://en.wikipedia.org/wiki/Elon_Musk")
elon_bot.add("https://www.forbes.com/profile/elon-musk")
elon_bot.add("https://www.youtube.com/watch?v=RcYjXbSJBN8")

# Query the bot
elon_bot.query("How many companies does Elon Musk run and name those?")
# Answer: Elon Musk currently runs several companies. As of my knowledge, he is the CEO and lead designer of SpaceX, the CEO and product architect of Tesla, Inc., the CEO and founder of Neuralink, and the CEO and founder of The Boring Company. However, please note that this information may change over time, so it's always good to verify the latest updates.
```

## Examples

| LLM          | Google Colab  | Replit   |
|--------------|---------------|----------|
| OpenAI       | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/openai.ipynb)           | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/openai#main.py)      |
| Anthropic    | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/anthropic.ipynb)        | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/anthropic#main.py)   |
| Azure OpenAI | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/azure-openai.ipynb)     | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/azureopenai#main.py) |
| VertexAI     | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/vertex_ai.ipynb)        | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/vertexai#main.py)    |
| Cohere       | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/cohere.ipynb)           | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/cohere#main.py)      |
| Hugging Face | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/hugging_face_hub.ipynb) | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/huggingface#main.py) |
| JinaChat     | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/jina.ipynb)             | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/jina#main.py)        |
| GPT4All      | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/gpt4all.ipynb)          | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/gpt4all#main.py)     |
| Llama2       | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/llama2.ipynb)           | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/llama2#main.py)      |

| Embedding model     | Google Colab                                                                                                                                                                            | Replit                                                                                                                        |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| OpenAI       | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/openai.ipynb)           | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/openai#main.py)      |
| VertexAI     | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/vertex_ai.ipynb)        | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/vertexai#main.py)    |
| GPT4All      | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/gpt4all.ipynb)          | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/gpt4all#main.py)     |
| Hugging Face | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/hugging_face_hub.ipynb) | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/huggingface#main.py) |

| Vector DB     | Google Colab                                                                                                                                                                         | Replit                                                                                                                          |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| ChromaDB      | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/chromadb.ipynb)      | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/chromadb#main.py)      |
| Elasticsearch | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/elasticsearch.ipynb) | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/elasticsearchdb#main.py) |
| Opensearch    | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/opensearch.ipynb)    | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/opensearchdb#main.py)    |
| Pinecone      | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/embedchain/embedchain/blob/main/notebooks/pinecone.ipynb)      | [![Try with Replit Badge](https://replit.com/badge?caption=Try%20with%20Replit&variant=small)](https://replit.com/@taranjeetio/pineconedb#main.py)      |

## 🤝 Contributing

Contributions are welcome! Please check out the issues on the repository, and feel free to open a pull request.
For more information, please see the [contributing guidelines](CONTRIBUTING.md).

For more reference, please go through [Development Guide](https://docs.embedchain.ai/contribution/dev) and [Documentation Guide](https://docs.embedchain.ai/contribution/docs).

<a href="https://github.com/embedchain/embedchain/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=embedchain/embedchain" />
</a>

## Telemetry

We collect anonymous usage metrics to enhance our package's quality and user experience. This includes data like feature usage frequency and system info, but never personal details. The data helps us prioritize improvements and ensure compatibility. If you wish to opt-out, set the `app.config.collect_metrics = False` in the code. We prioritize data security and don't share this data externally.

## Citation

If you utilize this repository, please consider citing it with:

```
@misc{embedchain,
  author = {Taranjeet Singh, Deshraj Yadav},
  title = {Embedchain: Data platform for LLMs - load, index, retrieve, and sync any unstructured data},
  year = {2023},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/embedchain/embedchain}},
}
```
