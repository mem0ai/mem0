# embedchain

[![PyPI](https://img.shields.io/pypi/v/embedchain)](https://pypi.org/project/embedchain/)
[![Discord](https://dcbadge.vercel.app/api/server/nhvCbCtKV?style=flat)](https://discord.gg/6PzXDgEjG5)
[![Twitter](https://img.shields.io/twitter/follow/embedchain)](https://twitter.com/embedchain)
[![Substack](https://img.shields.io/badge/Substack-%23006f5c.svg?logo=substack)](https://embedchain.substack.com/)

embedchain is a framework to easily create LLM powered bots over any dataset. If you want a javascript version, check out [embedchain-js](https://github.com/embedchain/embedchainjs)

# Latest Updates

- Introduce a new interface called `chat`. It remembers the history (last 5 messages) and can be used to powerful stateful bots. You can use it by calling `.chat` on any app instance. Works for both OpenAI and OpenSourceApp.

- Introduce a new app type called `OpenSourceApp`. It uses `gpt4all` as the LLM and `sentence transformers` all-MiniLM-L6-v2 as the embedding model. If you use this app, you dont have to pay for anything.

# What is embedchain?

Embedchain abstracts the entire process of loading a dataset, chunking it, creating embeddings and then storing in a vector database.

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

Creating a chatbot involves 3 steps:

- Import the App instance (App Types)
- Add Dataset (Add Dataset)
- Query or Chat on the dataset and get answers (Interface Types)

### App Types

We have three types of App.

#### 1. App (uses OpenAI models, paid)

```python
from embedchain import App

naval_chat_bot = App()
```

- `App` uses OpenAI's model, so these are paid models. You will be charged for embedding model usage and LLM usage.

- `App` uses OpenAI's embedding model to create embeddings for chunks and ChatGPT API as LLM to get answer given the relevant docs. Make sure that you have an OpenAI account and an API key. If you have don't have an API key, you can create one by visiting [this link](https://platform.openai.com/account/api-keys).

- Once you have the API key, set it in an environment variable called `OPENAI_API_KEY`

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-xxxx"
```

#### 2. OpenSourceApp (uses opensource models, free)

```python
from embedchain import OpenSourceApp

naval_chat_bot = OpenSourceApp()
```

- `OpenSourceApp` uses open source embedding and LLM model. It uses `all-MiniLM-L6-v2` from Sentence Transformers library as the embedding model and `gpt4all` as the LLM.

- Here there is no need to setup any api keys. You just need to install embedchain package and these will get automatically installed.

- Once you have imported and instantiated the app, every functionality from here onwards is the same for either type of app.

#### 3. PersonApp (uses OpenAI models, paid)

```python
from embedchain import PersonApp

naval_chat_bot = PersonApp("name_of_person_or_character") #Like "Yoda"
```

- `PersonApp` uses OpenAI's model, so these are paid models. You will be charged for embedding model usage and LLM usage.

- `PersonApp` uses OpenAI's embedding model to create embeddings for chunks and ChatGPT API as LLM to get answer given the relevant docs. Make sure that you have an OpenAI account and an API key. If you have don't have an API key, you can create one by visiting [this link](https://platform.openai.com/account/api-keys).

- Once you have the API key, set it in an environment variable called `OPENAI_API_KEY`

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-xxxx"
```

### Add Dataset

- This step assumes that you have already created an `app` instance by either using `App` or `OpenSourceApp`. We are calling our app instance as `naval_chat_bot`

- Now use `.add` function to add any dataset.

```python

# naval_chat_bot = App() or
# naval_chat_bot = OpenSourceApp()

# Embed Online Resources
naval_chat_bot.add("youtube_video", "https://www.youtube.com/watch?v=3qHkcs3kG44")
naval_chat_bot.add("pdf_file", "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf")
naval_chat_bot.add("web_page", "https://nav.al/feedback")
naval_chat_bot.add("web_page", "https://nav.al/agi")

# Embed Local Resources
naval_chat_bot.add_local("qna_pair", ("Who is Naval Ravikant?", "Naval Ravikant is an Indian-American entrepreneur and investor."))
```

- If there is any other app instance in your script or app, you can change the import as

```python
from embedchain import App as EmbedChainApp
from embedchain import OpenSourceApp as EmbedChainOSApp
from embedchain import PersonApp as EmbedChainPersonApp

# or

from embedchain import App as ECApp
from embedchain import OpenSourceApp as ECOSApp
from embedchain import PersonApp as ECPApp
```

## Interface Types

### Query Interface

- This interface is like a question answering bot. It takes a question and gets the answer. It does not maintain context about the previous chats.

- To use this, call `.query` function to get the answer for any query.

```python
print(naval_chat_bot.query("What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?"))
# answer: Naval argues that humans possess the unique capacity to understand explanations or concepts to the maximum extent possible in this physical reality.
```

### Chat Interface

- This interface is chat interface where it remembers previous conversation. Right now it remembers 5 conversation by default.

- To use this, call `.chat` function to get the answer for any query.

```python
print(naval_chat_bot.chat("How to be happy in life?"))
# answer: The most important trick to being happy is to realize happiness is a skill you develop and a choice you make. You choose to be happy, and then you work at it. It's just like building muscles or succeeding at your job. It's about recognizing the abundance and gifts around you at all times.

print(naval_chat_bot.chat("who is naval ravikant?"))
# answer: Naval Ravikant is an Indian-American entrepreneur and investor.

print(naval_chat_bot.chat("what did the author say about happiness?"))
# answer: The author, Naval Ravikant, believes that happiness is a choice you make and a skill you develop. He compares the mind to the body, stating that just as the body can be molded and changed, so can the mind. He emphasizes the importance of being present in the moment and not getting caught up in regrets of the past or worries about the future. By being present and grateful for where you are, you can experience true happiness.
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

### Doc File

To add any doc/docx file, use the data_type as `docx`. Eg:

```python
app.add('docx', 'a_local_docx_file_path')
```

### Text

To supply your own text, use the data_type as `text` and enter a string. The text is not processed, this can be very versatile. Eg:

```python
app.add_local('text', 'Seek wealth, not money or status. Wealth is having assets that earn while you sleep. Money is how we transfer time and wealth. Status is your place in the social hierarchy.')
```

Note: This is not used in the examples because in most cases you will supply a whole paragraph or file, which did not fit.

### QnA Pair

To supply your own QnA pair, use the data_type as `qna_pair` and enter a tuple. Eg:

```python
app.add_local('qna_pair', ("Question", "Answer"))
```

### Reusing a Vector DB

Default behavior is to create a persistent vector DB in the directory **./db**. You can split your application into two Python scripts: one to create a local vector DB and the other to reuse this local persistent vector DB. This is useful when you want to index hundreds of documents and separately implement a chat interface.

Create a local index:

```python

from embedchain import App

naval_chat_bot = App()
naval_chat_bot.add("youtube_video", "https://www.youtube.com/watch?v=3qHkcs3kG44")
naval_chat_bot.add("pdf_file", "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf")
```

You can reuse the local index with the same code, but without adding new documents:

```python

from embedchain import App

naval_chat_bot = App()
print(naval_chat_bot.query("What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?"))
```

### More Formats coming soon

- If you want to add any other format, please create an [issue](https://github.com/embedchain/embedchain/issues) and we will add it to the list of supported formats.

## Testing

Before you consume valueable tokens, you should make sure that the embedding you have done works and that it's receiving the correct document from the database.

For this you can use the `dry_run` method.

Following the example above, add this to your script:

```python
print(naval_chat_bot.dry_run('Can you tell me who Naval Ravikant is?'))

'''
Use the following pieces of context to answer the query at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
        Q: Who is Naval Ravikant?
A: Naval Ravikant is an Indian-American entrepreneur and investor.
        Query: Can you tell me who Naval Ravikant is?
        Helpful Answer:
'''
```

_The embedding is confirmed to work as expected. It returns the right document, even if the question is asked slightly different. No prompt tokens have been consumed._

**The dry run will still consume tokens to embed your query, but it is only ~1/15 of the prompt.**

# Advanced

## Configuration

Embedchain is made to work out of the box. However, for advanced users we're also offering configuration options. All of these configuration options are optional and have sane defaults.

### Example

Here's the readme example with configuration options.

```python
import os
from embedchain import App
from embedchain.config import InitConfig, AddConfig, QueryConfig
from chromadb.utils import embedding_functions

# Example: use your own embedding function
config = InitConfig(ef=embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                organization_id=os.getenv("OPENAI_ORGANIZATION"),
                model_name="text-embedding-ada-002"
            ))
naval_chat_bot = App(config)

add_config = AddConfig() # Currently no options
naval_chat_bot.add("youtube_video", "https://www.youtube.com/watch?v=3qHkcs3kG44", add_config)
naval_chat_bot.add("pdf_file", "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf", add_config)
naval_chat_bot.add("web_page", "https://nav.al/feedback", add_config)
naval_chat_bot.add("web_page", "https://nav.al/agi", add_config)

naval_chat_bot.add_local("qna_pair", ("Who is Naval Ravikant?", "Naval Ravikant is an Indian-American entrepreneur and investor."), add_config)

query_config = QueryConfig() # Currently no options
print(naval_chat_bot.query("What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?", query_config))
```

### Configs

This section describes all possible config options.

#### **InitConfig**

|option|description|type|default|
|---|---|---|---|
|ef|embedding function|chromadb.utils.embedding_functions|{text-embedding-ada-002}|
|db|vector database (experimental)|BaseVectorDB|ChromaDB|

#### **Add Config**

_coming soon_

#### **Query Config**

|option|description|type|default|
|---|---|---|---|
|template|custom template for prompt|Template|Template("Use the following pieces of context to answer the query at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer. \$context Query: $query Helpful Answer:")|

#### **Chat Config**

All options for query and...

_coming soon_

## Other methods

### Reset

Resets the database and deletes all embeddings. Irreversible. Requires reinitialization afterwards.

```python
app.reset()
```

### Count

Counts the number of embeddings (chunks) in the database.

```python
print(app.count())
# returns: 481
```

# How does it work?

Creating a chat bot over any dataset needs the following steps to happen

- load the data
- create meaningful chunks
- create embeddings for each chunk
- store the chunks in vector database

Whenever a user asks any query, following process happens to find the answer for the query

- create the embedding for query
- find similar documents for this query from vector database
- pass similar documents as context to LLM to get the final answer.

The process of loading the dataset and then querying involves multiple steps and each steps has nuances of it is own.

- How should I chunk the data? What is a meaningful chunk size?
- How should I create embeddings for each chunk? Which embedding model should I use?
- How should I store the chunks in vector database? Which vector database should I use?
- Should I store meta data along with the embeddings?
- How should I find similar documents for a query? Which ranking model should I use?

These questions may be trivial for some but for a lot of us, it needs research, experimentation and time to find out the accurate answers.

embedchain is a framework which takes care of all these nuances and provides a simple interface to create bots over any dataset.

In the first release, we are making it easier for anyone to get a chatbot over any dataset up and running in less than a minute. All you need to do is create an app instance, add the data sets using `.add` function and then use `.query` function to get the relevant answer.

# Tech Stack

embedchain is built on the following stack:

- [Langchain](https://github.com/hwchase17/langchain) as an LLM framework to load, chunk and index data
- [OpenAI's Ada embedding model](https://platform.openai.com/docs/guides/embeddings) to create embeddings
- [OpenAI's ChatGPT API](https://platform.openai.com/docs/guides/gpt/chat-completions-api) as LLM to get answers given the context
- [Chroma](https://github.com/chroma-core/chroma) as the vector database to store embeddings
- [gpt4all](https://github.com/nomic-ai/gpt4all) as an open source LLM
- [sentence-transformers](https://huggingface.co/sentence-transformers) as open source embedding model

# Team

## Author

- Taranjeet Singh ([@taranjeetio](https://twitter.com/taranjeetio))

## Maintainer

- [cachho](https://github.com/cachho)

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
