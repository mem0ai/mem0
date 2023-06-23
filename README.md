# embedchain

[![](https://dcbadge.vercel.app/api/server/nhvCbCtKV?style=flat)](https://discord.gg/nhvCbCtKV)
![PyPI](https://img.shields.io/pypi/v/embedchain)

embedchain is a framework to easily create LLM powered bots over any dataset.

It abstracts the enitre process of loading dataset, chunking it, creating embeddings and then storing in vector database.

You can add a single or multiple dataset using `.add` and `.add_local` function and then use `.query` function to find an answer from the added datasets.

If you want to create a Naval Ravikant bot which has 1 youtube video, 1 book as pdf and 2 of his blog posts, as well as a question and answer pair you supply, all you need to do is add the links to the videos, pdf and blog posts and the QnA pair and embedchain will create a bot for you.

```python

from embedchain import App

naval_chat_bot = App()

# Embed Online Resources
naval_chat_bot.add("youtube_video", "https://www.youtube.com/watch?v=3qHkcs3kG44")
naval_chat_bot.add("pdf_file", "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf")
naval_chat_bot.add("web_page", "https://nav.al/feedback")
naval_chat_bot.add("web_page", "https://nav.al/agi")

# Embed Local Resources
naval_chat_bot.add_local("qna_pair", ("Who is Naval Ravikant?", "Naval Ravikant is an Indian-American entrepreneur and investor."))

naval_chat_bot.query("What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?")
# answer: Naval argues that humans possess the unique capacity to understand explanations or concepts to the maximum extent possible in this physical reality.
```

# Getting Started

## Installation

First make sure that you have the package installed. If not, then install it using `pip`

```bash
pip install embedchain
```

## Usage

* We use OpenAI's embedding model to create embeddings for chunks and ChatGPT API as LLM to get answer given the relevant docs. Make sure that you have an OpenAI account and an API key. If you have dont have an API key, you can create one by visiting [this link](https://platform.openai.com/account/api-keys).

* Once you have the API key, set it in an environment variable called `OPENAI_API_KEY`

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-xxxx"
```

* Next import the `App` class from embedchain and use `.add` function to add any dataset.

```python

from embedchain import App

naval_ravikant_chat_bot_app = App()

# Embed Online Resources
naval_chat_bot.add("youtube_video", "https://www.youtube.com/watch?v=3qHkcs3kG44")
naval_chat_bot.add("pdf_file", "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf")
naval_chat_bot.add("web_page", "https://nav.al/feedback")
naval_chat_bot.add("web_page", "https://nav.al/agi")

# Embed Local Resources
naval_chat_bot.add_local("qna_pair", ("Who is Naval Ravikant?", "Naval Ravikant is an Indian-American entrepreneur and investor."))
```

* If there is any other app instance in your script or app, you can change the import as

```python
from embedchain import App as EmbedChainApp

# or

from embedchain import App as ECApp
```

* Now your app is created. You can use `.query` function to get the answer for any query.

```python
print(naval_chat_bot.query("What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?"))
# answer: Naval argues that humans possess the unique capacity to understand explanations or concepts to the maximum extent possible in this physical reality.
```

## Format supported

We support the following formats:

### Youtube Video

To add any youtube video to your app, use the data_type (first argument to `.add`) as `youtube_video`. Eg:

```python
app.add('youtube_video', 'a_valid_youtube_url_here')
```

### PDF File

To add any pdf file, use the data_type as `pdf_file`. Eg:

```python
app.add('pdf_file', 'a_valid_url_where_pdf_file_can_be_accessed')
```

Note that we do not support password protected pdfs.

### Web Page

To add any web page, use the data_type as `web_page`. Eg:

```python
app.add('web_page', 'a_valid_web_page_url')
```

### QnA Pair

To supply your own QnA pair, use the data_type as `qna_pair` and enter a tuple. Eg:

```python
app.add_local('qna_pair', ("Question", "Answer"))
```

### More Formats coming soon

* If you want to add any other format, please create an [issue](https://github.com/embedchain/embedchain/issues) and we will add it to the list of supported formats.

# How does it work?

Creating a chat bot over any dataset needs the following steps to happen

* load the data
* create meaningful chunks
* create embeddigns for each chunk
* store the chunks in vector database

Whenever a user asks any query, following process happens to find the answer for the query

* create the embedding for query
* find similar documents for this query from vector database
* pass similar documents as context to LLM to get the final answer.

The process of loading the dataset and then querying involves multiple steps and each steps has nuances of it is own.

* How should I chunk the data? What is a meaningful chunk size?
* How should I create embeddings for each chunk? Which embedding model should I use?
* How should I store the chunks in vector database? Which vector database should I use?
* Should I store meta data along with the embeddings?
* How should I find similar documents for a query? Which ranking model should I use?

These questions may be trivial for some but for a lot of us, it needs research, experimentation and time to find out the accurate answers.

embedchain is a framework which takes care of all these nuances and provides a simple interface to create bots over any dataset.

In the first release, we are making it easier for anyone to get a chatbot over any dataset up and running in less than a minute. All you need to do is create an app instance, add the data sets using `.add` function and then use `.query` function to get the relevant answer.

# Tech Stack

embedchain is built on the following stack:

- [Langchain](https://github.com/hwchase17/langchain) as an LLM framework to load, chunk and index data
- [OpenAI's Ada embedding model](https://platform.openai.com/docs/guides/embeddings) to create embeddings
- [OpenAI's ChatGPT API](https://platform.openai.com/docs/guides/gpt/chat-completions-api) as LLM to get answers given the context
- [Chroma](https://github.com/chroma-core/chroma) as the vector database to store embeddings

# Author

* Taranjeet Singh ([@taranjeetio](https://twitter.com/taranjeetio))