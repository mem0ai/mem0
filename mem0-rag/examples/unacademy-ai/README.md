## Unacademy UPSC AI

This directory contains the code used to implement [Unacademy UPSC AI](https://unacademy-ai.streamlit.app/) using Embedchain. It is built on 16K+ youtube videos and 800+ course pages from Unacademy website. You can find the full list of data sources [here](https://gist.github.com/deshraj/7714feadccca13cefe574951652fa9b2).

## Run locally

You can run Unacademy AI locally as a streamlit app using the following command:

```bash
export OPENAI_API_KEY=sk-xxx
pip install -r requirements.txt
streamlit run app.py
```

Note: Remember to set your `OPENAI_API_KEY`.

## Deploy to production

You can create your own Unacademy AI or similar RAG applications in production using one of the several deployment methods provided in [our docs](https://docs.embedchain.ai/get-started/deployment).
