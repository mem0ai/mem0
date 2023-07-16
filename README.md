# embedchain

[![PyPI](https://img.shields.io/pypi/v/embedchain)](https://pypi.org/project/embedchain/)
[![Discord](https://dcbadge.vercel.app/api/server/nhvCbCtKV?style=flat)](https://discord.gg/6PzXDgEjG5)
[![Twitter](https://img.shields.io/twitter/follow/embedchain)](https://twitter.com/embedchain)
[![Substack](https://img.shields.io/badge/Substack-%23006f5c.svg?logo=substack)](https://embedchain.substack.com/)

Embedchain is a framework to easily create LLM powered bots over any dataset. If you want a javascript version, check out [embedchain-js](https://github.com/embedchain/embedchainjs)

## 🔧 Quick install

```bash
pip install embedchain
```

## 🔍 Demo

Try out PandasAI in your browser:

[![Open in Colab](https://camo.githubusercontent.com/84f0493939e0c4de4e6dbe113251b4bfb5353e57134ffd9fcab6b8714514d4d1/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/138lMWhENGeEu7Q1-6lNbNTHGLZXBBz_B?usp=sharing)

## 📖 Documentation

The documentation for PandasAI can be found at [docs.embedchain.ai](https://docs.embedchain.ai).

## 💻 Usage

Embedchain empowers you to create chatbot models similar to ChatGPT, using your own evolving dataset.

### Queries

For example, you can use Embedchain to create an Elon Musk bot using the following code:

```python
import os
from embedchain import App

# Create a bot instance
os.environ["OPENAI_API_KEY"] = "YOUR API KEY"
elon_bot = App()

# Instantiate a LLM
elon_bot.add("web_page", "https://en.wikipedia.org/wiki/Elon_Musk")
elon_bot.add("web_page", "https://tesla.com/elon-musk")
elon_bot.add("youtube_video", "https://www.youtube.com/watch?v=MxZpaJK74Y4")

# Query the bot
elon_bot.query("How many companies does Elon Musk run?")
# Elon Musk runs multiple companies. Some of the notable ones include SpaceX, Tesla, Neuralink, and The Boring Company. However, the exact number of companies he currently runs may vary as he is involved in various ventures and investments.
```
## ⚙️ Command-Line Tool

Pai is the command line tool designed to provide a convenient way to interact with PandasAI through a command line interface (CLI). In order to access the CLI tool, make sure to create a virtualenv for testing purpose and to install project dependencies in your local virtual environment using `pip` by running the following command:

Read more about how to use the CLI [here](https://pandas-ai.readthedocs.io/en/latest/pai_cli/).

## 🤝 Contributing

Contributions are welcome! Please check out the issues on the repository, and feel free to open a pull request.
For more information, please see the [contributing guidelines](CONTRIBUTING.md).

## Citation

If you utilize this repository, please consider citing it with:

```
@misc{embedchain,
  author = {Taranjeet Singh},
  title = {Embechain: Framework to easily create LLM powered bots over any dataset},
  year = {2023},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/embedchain/embedchain}},
}
```
