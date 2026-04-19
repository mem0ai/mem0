"""
EmbedChain BuyWhere Shopping Agent

This app demonstrates how to build a RAG-based shopping assistant
using EmbedChain and BuyWhere's product catalog API via MCP.
"""
import os
import queue
import threading

import streamlit as st
from embedchain import App
from embedchain.config import BaseLlmConfig
from embedchain.helpers.callbacks import StreamingStdOutCallbackHandlerYield, generate

BUYWHERE_API_KEY = os.environ.get("BUYWHERE_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def embedchain_shopping_bot(db_path, openai_key, buywhere_key):
    return App.from_config(
        config={
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.5,
                    "max_tokens": 1000,
                    "stream": True,
                    "api_key": openai_key,
                },
            },
            "vectordb": {
                "provider": "chroma",
                "config": {"collection_name": "buywhere-shopping", "dir": db_path, "allow_reset": True},
            },
            "embedder": {"provider": "openai", "config": {"api_key": openai_key}},
            "chunker": {"chunk_size": 2000, "chunk_overlap": 0, "length_function": "len"},
        }
    )


def init_buywhere_mcp(buywhere_key):
    from mcp import Client as MCPClient
    import httpx

    API_URL = "https://api.buywhere.ai"
    headers = {"Authorization": f"Bearer {buywhere_key}"}

    client = MCPClient()

    async def search_products(query, category=None, limit=10):
        params = {"q": query, "limit": limit}
        if category:
            params["category"] = category
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{API_URL}/v1/products", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def get_product(product_id):
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{API_URL}/v1/products/{product_id}", headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def find_best_price(product_name, category=None):
        params = {"q": product_name}
        if category:
            params["category"] = category
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{API_URL}/v1/products/best-price", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def get_deals(category=None, min_discount_pct=10, limit=10):
        params = {"min_discount_pct": min_discount_pct, "limit": limit}
        if category:
            params["category"] = category
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"{API_URL}/v1/deals", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    return {
        "search_products": search_products,
        "get_product": get_product,
        "find_best_price": find_best_price,
        "get_deals": get_deals,
    }


def get_ec_app():
    if "app" in st.session_state:
        return st.session_state.app

    if not OPENAI_API_KEY:
        return None

    db_path = "/tmp/buywhere_ec_db"
    os.makedirs(db_path, exist_ok=True)

    app = embedchain_shopping_bot(db_path, OPENAI_API_KEY, BUYWHERE_API_KEY)
    st.session_state.app = app
    return app


st.set_page_config(page_title="BuyWhere Shopping Agent", page_icon="🛒")

st.title("🛒 BuyWhere Shopping Agent")
st.markdown(
    "An EmbedChain-powered RAG app for shopping assistance with real-time "
    "price comparison across Singapore e-commerce platforms."
)

with st.sidebar:
    st.header("Configuration")

    openai_key = st.text_input(
        "OpenAI API Key",
        key="openai_key",
        type="password",
        help="Get your key at https://platform.openai.com/api-keys"
    )
    st.session_state.openai_key = openai_key

    buywhere_key = st.text_input(
        "BuyWhere API Key",
        key="buywhere_key",
        type="password",
        help="Get your key at https://buywhere.ai/developers"
    )
    st.session_state.buywhere_key = buywhere_key

    st.markdown("---")
    st.markdown("### Example Queries")
    st.markdown("- Find the best price for Nike Air Max")
    st.markdown("- Search for wireless headphones under $100")
    st.markdown("- Show me electronics deals with 20%+ discount")
    st.markdown("- Compare prices for Samsung Galaxy S24")

if not st.session_state.get("openai_key") or not st.session_state.get("buywhere_key"):
    st.warning("Please enter both OpenAI and BuyWhere API keys in the sidebar to continue.")
    st.stop()

BUYWHERE_API_KEY = st.session_state.buywhere_key
OPENAI_API_KEY = st.session_state.openai_key

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """
                🛒 **Welcome to BuyWhere Shopping Agent!**

                I can help you find products, compare prices across platforms, and discover deals.

                **What I can do:**
                - Search for products across 1.5M+ items
                - Find the best price for any product
                - Discover deals and discounts
                - Compare prices across Shopee, Lazada, Carousell, and more

                Just ask me what you're looking for!
            """,
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What are you looking for?"):
    if not st.session_state.get("openai_key") or not st.session_state.get("buywhere_key"):
        st.error("Please enter your API keys in the sidebar.")
        st.stop()

    with st.chat_message("user"):
        st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        msg_placeholder = st.empty()
        msg_placeholder.markdown("Thinking...")

        app = get_ec_app()
        if not app:
            st.error("Failed to initialize EmbedChain app. Please check your API keys.")
            st.stop()

        full_response = ""
        q = queue.Queue()

        def app_response():
            try:
                buywhere = init_buywhere_mcp(BUYWHERE_API_KEY)

                search_results = buywhere["search_products"](prompt, limit=5)

                context = "Product search results:\n"
                if search_results and "items" in search_results:
                    for item in search_results["items"][:5]:
                        context += f"- {item.get('name', 'Unknown')} | "
                        context += f"Price: {item.get('price', 'N/A')} | "
                        context += f"Source: {item.get('source', 'N/A')}\n"

                prompt_with_context = f"Based on these search results, answer the user's question. If the search results don't contain relevant info, say so.\n\nSearch results:\n{context}\n\nUser question: {prompt}"

                llm_config = app.llm.config.as_dict()
                llm_config["callbacks"] = [StreamingStdOutCallbackHandlerYield(q=q)]

                config = BaseLlmConfig(**llm_config)
                answer, citations = app.chat(prompt_with_context, config=config, citations=True)
                return answer, citations
            except Exception as e:
                return f"I encountered an error: {str(e)}", []

        results = {}
        thread = threading.Thread(target=lambda: results.update({"result": app_response()}))
        thread.start()

        for answer_chunk in generate(q):
            if isinstance(answer_chunk, str):
                full_response += answer_chunk
                msg_placeholder.markdown(full_response)

        thread.join()

        result = results.get("result", ("", []))
        if isinstance(result, tuple):
            answer, citations = result
        else:
            answer = result
            citations = []

        if citations:
            full_response += "\n\n**Sources:**\n"
            sources = list(set([citation[1].get("url", "Unknown") for citation in citations if citation]))
            for source in sources:
                full_response += f"- {source}\n"

        msg_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})