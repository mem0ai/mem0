# embedchainjs

[![Discord](https://dcbadge.vercel.app/api/server/CUU9FPhRNt?style=flat)](https://discord.gg/CUU9FPhRNt)
[![Twitter](https://img.shields.io/twitter/follow/embedchain)](https://twitter.com/embedchain)
[![Substack](https://img.shields.io/badge/Substack-%23006f5c.svg?logo=substack)](https://embedchain.substack.com/)

embedchain is a framework to easily create LLM powered bots over any dataset. embedchainjs is Javascript version of embedchain. If you want a python version, check out [embedchain-python](https://github.com/embedchain/embedchain)

# 🤝 Let's Talk Embedchain!

Schedule a [Feedback Session](https://cal.com/taranjeetio/ec) with Taranjeet, the founder, to discuss any issues, provide feedback, or explore improvements.

# How it works

It abstracts the entire process of loading dataset, chunking it, creating embeddings and then storing in vector database.

You can add a single or multiple dataset using `.add` and `.addLocal` function and then use `.query` function to find an answer from the added datasets.

If you want to create a Naval Ravikant bot which has 2 of his blog posts, as well as a question and answer pair you supply, all you need to do is add the links to the blog posts and the QnA pair and embedchain will create a bot for you.

```javascript
const dotenv = require("dotenv");
dotenv.config();
const { App } = require("embedchain");

//Run the app commands inside an async function only
async function testApp() {
  const navalChatBot = await App();

  // Embed Online Resources
  await navalChatBot.add("web_page", "https://nav.al/feedback");
  await navalChatBot.add("web_page", "https://nav.al/agi");
  await navalChatBot.add(
    "pdf_file",
    "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf"
  );

  // Embed Local Resources
  await navalChatBot.addLocal("qna_pair", [
    "Who is Naval Ravikant?",
    "Naval Ravikant is an Indian-American entrepreneur and investor.",
  ]);

  const result = await navalChatBot.query(
    "What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?"
  );
  console.log(result);
  // answer: Naval argues that humans possess the unique capacity to understand explanations or concepts to the maximum extent possible in this physical reality.
}

testApp();
```

# Getting Started

## Installation

- First make sure that you have the package installed. If not, then install it using `npm`

```bash
npm install embedchain && npm install -S openai@^3.3.0
```

- Currently, it is only compatible with openai 3.X, not the latest version 4.X. Please make sure to use the right version, otherwise you will see the `ChromaDB` error `TypeError: OpenAIApi.Configuration is not a constructor`

- Make sure that dotenv package is installed and your `OPENAI_API_KEY` in a file called `.env` in the root folder. You can install dotenv by

```js
npm install dotenv
```

- Download and install Docker on your device by visiting [this link](https://www.docker.com/). You will need this to run Chroma vector database on your machine.

- Run the following commands to setup Chroma container in Docker

```bash
git clone https://github.com/chroma-core/chroma.git
cd chroma
docker-compose up -d --build
```

- Once Chroma container has been set up, run it inside Docker

## Usage

- We use OpenAI's embedding model to create embeddings for chunks and ChatGPT API as LLM to get answer given the relevant docs. Make sure that you have an OpenAI account and an API key. If you have dont have an API key, you can create one by visiting [this link](https://platform.openai.com/account/api-keys).

- Once you have the API key, set it in an environment variable called `OPENAI_API_KEY`

```js
// Set this inside your .env file
OPENAI_API_KEY = "sk-xxxx";
```

- Load the environment variables inside your .js file using the following commands

```js
const dotenv = require("dotenv");
dotenv.config();
```

- Next import the `App` class from embedchain and use `.add` function to add any dataset.
- Now your app is created. You can use `.query` function to get the answer for any query.

```js
const dotenv = require("dotenv");
dotenv.config();
const { App } = require("embedchain");

async function testApp() {
  const navalChatBot = await App();

  // Embed Online Resources
  await navalChatBot.add("web_page", "https://nav.al/feedback");
  await navalChatBot.add("web_page", "https://nav.al/agi");
  await navalChatBot.add(
    "pdf_file",
    "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf"
  );

  // Embed Local Resources
  await navalChatBot.addLocal("qna_pair", [
    "Who is Naval Ravikant?",
    "Naval Ravikant is an Indian-American entrepreneur and investor.",
  ]);

  const result = await navalChatBot.query(
    "What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?"
  );
  console.log(result);
  // answer: Naval argues that humans possess the unique capacity to understand explanations or concepts to the maximum extent possible in this physical reality.
}

testApp();
```

- If there is any other app instance in your script or app, you can change the import as

```javascript
const { App: EmbedChainApp } = require("embedchain");

// or

const { App: ECApp } = require("embedchain");
```

## Format supported

We support the following formats:

### PDF File

To add any pdf file, use the data_type as `pdf_file`. Eg:

```javascript
await app.add("pdf_file", "a_valid_url_where_pdf_file_can_be_accessed");
```

### Web Page

To add any web page, use the data_type as `web_page`. Eg:

```javascript
await app.add("web_page", "a_valid_web_page_url");
```

### QnA Pair

To supply your own QnA pair, use the data_type as `qna_pair` and enter a tuple. Eg:

```javascript
await app.addLocal("qna_pair", ["Question", "Answer"]);
```

### More Formats coming soon

- If you want to add any other format, please create an [issue](https://github.com/embedchain/embedchainjs/issues) and we will add it to the list of supported formats.

## Testing

Before you consume valueable tokens, you should make sure that the embedding you have done works and that it's receiving the correct document from the database.

For this you can use the `dryRun` method.

Following the example above, add this to your script:

```js
let result = await naval_chat_bot.dryRun("What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?");console.log(result);

'''
Use the following pieces of context to answer the query at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
terms of the unseen. And I think that’s critical. That is what humans do uniquely that no other creature, no other computer, no other intelligence—biological or artificial—that we have ever encountered does. And not only do we do it uniquely, but if we were to meet an alien species that also had the power to generate these good explanations, there is no explanation that they could generate that we could not understand. We are maximally capable of understanding. There is no concept out there that is possible in this physical reality that a human being, given sufficient time and resources and
Query: What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?
Helpful Answer:
'''
```

_The embedding is confirmed to work as expected. It returns the right document, even if the question is asked slightly different. No prompt tokens have been consumed._

**The dry run will still consume tokens to embed your query, but it is only ~1/15 of the prompt.**

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

# Team

## Author

- Taranjeet Singh ([@taranjeetio](https://twitter.com/taranjeetio))

## Maintainer

- [cachho](https://github.com/cachho)
- [sahilyadav902](https://github.com/sahilyadav902)

## Citation

If you utilize this repository, please consider citing it with:
```
@misc{embedchain,
  author = {Taranjeet Singh},
  title = {Embechain: Framework to easily create LLM powered bots over any dataset},
  year = {2023},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/embedchain/embedchainjs}},
}
```
