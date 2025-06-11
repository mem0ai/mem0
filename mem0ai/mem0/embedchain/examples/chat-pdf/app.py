import os
import queue
import re
import tempfile
import threading

import streamlit as st

from embedchain import App
from embedchain.config import BaseLlmConfig
from embedchain.helpers.callbacks import StreamingStdOutCallbackHandlerYield, generate


def embedchain_bot(db_path, api_key):
    return App.from_config(
        config={
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.5,
                    "max_tokens": 1000,
                    "top_p": 1,
                    "stream": True,
                    "api_key": api_key,
                },
            },
            "vectordb": {
                "provider": "chroma",
                "config": {"collection_name": "chat-pdf", "dir": db_path, "allow_reset": True},
            },
            "embedder": {"provider": "openai", "config": {"api_key": api_key}},
            "chunker": {"chunk_size": 2000, "chunk_overlap": 0, "length_function": "len"},
        }
    )


def get_db_path():
    tmpdirname = tempfile.mkdtemp()
    return tmpdirname


def get_ec_app(api_key):
    if "app" in st.session_state:
        print("Found app in session state")
        app = st.session_state.app
    else:
        print("Creating app")
        db_path = get_db_path()
        app = embedchain_bot(db_path, api_key)
        st.session_state.app = app
    return app


with st.sidebar:
    openai_access_token = st.text_input("OpenAI API Key", key="api_key", type="password")
    "WE DO NOT STORE YOUR OPENAI KEY."
    "Just paste your OpenAI API key here and we'll use it to power the chatbot. [Get your OpenAI API key](https://platform.openai.com/api-keys)"  # noqa: E501

    if st.session_state.api_key:
        app = get_ec_app(st.session_state.api_key)

    pdf_files = st.file_uploader("Upload your PDF files", accept_multiple_files=True, type="pdf")
    add_pdf_files = st.session_state.get("add_pdf_files", [])
    for pdf_file in pdf_files:
        file_name = pdf_file.name
        if file_name in add_pdf_files:
            continue
        try:
            if not st.session_state.api_key:
                st.error("Please enter your OpenAI API Key")
                st.stop()
            temp_file_name = None
            with tempfile.NamedTemporaryFile(mode="wb", delete=False, prefix=file_name, suffix=".pdf") as f:
                f.write(pdf_file.getvalue())
                temp_file_name = f.name
            if temp_file_name:
                st.markdown(f"Adding {file_name} to knowledge base...")
                app.add(temp_file_name, data_type="pdf_file")
                st.markdown("")
                add_pdf_files.append(file_name)
                os.remove(temp_file_name)
            st.session_state.messages.append({"role": "assistant", "content": f"Added {file_name} to knowledge base!"})
        except Exception as e:
            st.error(f"Error adding {file_name} to knowledge base: {e}")
            st.stop()
    st.session_state["add_pdf_files"] = add_pdf_files

st.title("📄 Embedchain - Chat with PDF")
styled_caption = '<p style="font-size: 17px; color: #aaa;">🚀 An <a href="https://github.com/embedchain/embedchain">Embedchain</a> app powered by OpenAI!</p>'  # noqa: E501
st.markdown(styled_caption, unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """
                Hi! I'm chatbot powered by Embedchain, which can answer questions about your pdf documents.\n
                Upload your pdf documents here and I'll answer your questions about them! 
            """,
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me anything!"):
    if not st.session_state.api_key:
        st.error("Please enter your OpenAI API Key", icon="🤖")
        st.stop()

    app = get_ec_app(st.session_state.api_key)

    with st.chat_message("user"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(prompt)

    with st.chat_message("assistant"):
        msg_placeholder = st.empty()
        msg_placeholder.markdown("Thinking...")
        full_response = ""

        q = queue.Queue()

        def app_response(result):
            llm_config = app.llm.config.as_dict()
            llm_config["callbacks"] = [StreamingStdOutCallbackHandlerYield(q=q)]
            config = BaseLlmConfig(**llm_config)
            answer, citations = app.chat(prompt, config=config, citations=True)
            result["answer"] = answer
            result["citations"] = citations

        results = {}
        thread = threading.Thread(target=app_response, args=(results,))
        thread.start()

        for answer_chunk in generate(q):
            full_response += answer_chunk
            msg_placeholder.markdown(full_response)

        thread.join()
        answer, citations = results["answer"], results["citations"]
        if citations:
            full_response += "\n\n**Sources**:\n"
            sources = []
            for i, citation in enumerate(citations):
                source = citation[1]["url"]
                pattern = re.compile(r"([^/]+)\.[^\.]+\.pdf$")
                match = pattern.search(source)
                if match:
                    source = match.group(1) + ".pdf"
                sources.append(source)
            sources = list(set(sources))
            for source in sources:
                full_response += f"- {source}\n"

        msg_placeholder.markdown(full_response)
        print("Answer: ", full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
