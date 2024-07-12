import os

import streamlit as st

from embedchain import App


@st.cache_resource
def ec_app():
    return App.from_config(config_path="config.yaml")


with st.sidebar:
    huggingface_access_token = st.text_input("Hugging face Token", key="chatbot_api_key", type="password")
    "[Get Hugging Face Access Token](https://huggingface.co/settings/tokens)"
    "[View the source code](https://github.com/embedchain/examples/mistral-streamlit)"


st.title("💬 Chatbot")
st.caption("🚀 An Embedchain app powered by Mistral!")
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """
        Hi! I'm a chatbot. I can answer questions and learn new things!\n
        Ask me anything and if you want me to learn something do `/add <source>`.\n
        I can learn mostly everything. :)
        """,
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me anything!"):
    if not st.session_state.chatbot_api_key:
        st.error("Please enter your Hugging Face Access Token")
        st.stop()

    os.environ["HUGGINGFACE_ACCESS_TOKEN"] = st.session_state.chatbot_api_key
    app = ec_app()

    if prompt.startswith("/add"):
        with st.chat_message("user"):
            st.markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
        prompt = prompt.replace("/add", "").strip()
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("Adding to knowledge base...")
            app.add(prompt)
            message_placeholder.markdown(f"Added {prompt} to knowledge base!")
            st.session_state.messages.append({"role": "assistant", "content": f"Added {prompt} to knowledge base!"})
            st.stop()

    with st.chat_message("user"):
        st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        msg_placeholder = st.empty()
        msg_placeholder.markdown("Thinking...")
        full_response = ""

        for response in app.chat(prompt):
            msg_placeholder.empty()
            full_response += response

        msg_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
