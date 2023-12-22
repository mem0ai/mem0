## Sadhguru AI

This directory contains the code used to implement [Sadhguru AI](https://sadhguru-ai.streamlit.app/) using Embedchain. It is built on 3K+ videos and 1K+ articles of Sadhguru. You can find the full list of data sources [here](https://gist.github.com/deshraj/50b0597157e04829bbbb7bc418be6ccb).

## Run locally

You can run Sadhguru AI locally as a streamlit app using the following command:

```bash
export OPENAI_API_KEY=sk-xxx
pip install -r requirements.txt
streamlit run app.py
```

Note: Remember to set your `OPENAI_API_KEY`.

## Deploy to production

You can create your own Sadhguru AI or similar RAG applications in production using one of the several deployment methods provided in [our docs](https://docs.embedchain.ai/get-started/deployment).
