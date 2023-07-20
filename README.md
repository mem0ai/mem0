# embedchain

[![PyPI](https://img.shields.io/pypi/v/embedchain)](https://pypi.org/project/embedchain/)
[![Discord](https://dcbadge.vercel.app/api/server/nhvCbCtKV?style=flat)](https://discord.gg/6PzXDgEjG5)
[![Twitter](https://img.shields.io/twitter/follow/embedchain)](https://twitter.com/embedchain)
[![Substack](https://img.shields.io/badge/Substack-%23006f5c.svg?logo=substack)](https://embedchain.substack.com/)
[![Open in Colab](https://camo.githubusercontent.com/84f0493939e0c4de4e6dbe113251b4bfb5353e57134ffd9fcab6b8714514d4d1/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/138lMWhENGeEu7Q1-6lNbNTHGLZXBBz_B?usp=sharing)

Embedchain is a framework to easily create LLM powered bots over any dataset. If you want a javascript version, check out [embedchain-js](https://github.com/embedchain/embedchainjs)

## 🔧 Quick install

```bash
pip install embedchain
```

## 🔥 Latest

- **[2023/07/19]** Released support for 🦙 `llama2` model. Start creating your `llama2` based bots like this:

  ```python
  import os

  from embedchain import Llama2App

  os.environ['REPLICATE_API_TOKEN'] = "REPLICATE API TOKEN"

  zuck_bot = Llama2App()

  # Embed your data
  zuck_bot.add("youtube_video", "https://www.youtube.com/watch?v=Ff4fRgnuFgQ")
  zuck_bot.add("web_page", "https://en.wikipedia.org/wiki/Mark_Zuckerberg")

  # Nice, your bot is ready now. Start asking questions to your bot.
  zuck_bot.query("Who is Mark Zuckerberg?")
  # Answer: Mark Zuckerberg is an American internet entrepreneur and business magnate. He is the co-founder and CEO of Facebook.
  ```


## 🔍 Demo

Try out embedchain in your browser:

[![Open in Colab](https://camo.githubusercontent.com/84f0493939e0c4de4e6dbe113251b4bfb5353e57134ffd9fcab6b8714514d4d1/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/138lMWhENGeEu7Q1-6lNbNTHGLZXBBz_B?usp=sharing)

## 📖 Documentation

The documentation for embedchain can be found at [docs.embedchain.ai](https://docs.embedchain.ai).

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

# Embed online resources
elon_bot.add("web_page", "https://en.wikipedia.org/wiki/Elon_Musk")
elon_bot.add("web_page", "https://tesla.com/elon-musk")
elon_bot.add("youtube_video", "https://www.youtube.com/watch?v=MxZpaJK74Y4")

# Query the bot
elon_bot.query("How many companies does Elon Musk run?")
# Answer: Elon Musk runs four companies: Tesla, SpaceX, Neuralink, and The Boring Company
```

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
