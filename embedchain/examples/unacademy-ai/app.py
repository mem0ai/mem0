import queue

import streamlit as st

from embedchain import App
from embedchain.config import BaseLlmConfig
from embedchain.helpers.callbacks import StreamingStdOutCallbackHandlerYield, generate


@st.cache_resource
def unacademy_ai():
    app = App()
    return app


app = unacademy_ai()

assistant_avatar_url = "https://cdn-images-1.medium.com/v2/resize:fit:1200/1*LdFNhpOe7uIn-bHK9VUinA.jpeg"

st.markdown(f"# <img src='{assistant_avatar_url}' width={35} /> Unacademy UPSC AI", unsafe_allow_html=True)

styled_caption = """
<p style="font-size: 17px; color: #aaa;">
🚀 An <a href="https://github.com/embedchain/embedchain">Embedchain</a> app powered with Unacademy\'s UPSC data!
</p>
"""
st.markdown(styled_caption, unsafe_allow_html=True)

with st.expander(":grey[Want to create your own Unacademy UPSC AI?]"):
    st.write(
        """
    ```bash
    pip install embedchain
    ```

    ```python
    from embedchain import App
    unacademy_ai_app = App()
    unacademy_ai_app.add(
        "https://unacademy.com/content/upsc/study-material/plan-policy/atma-nirbhar-bharat-3-0/",
        data_type="web_page"
    )
    unacademy_ai_app.chat("What is Atma Nirbhar 3.0?")
    ```

    For more information, checkout the [Embedchain docs](https://docs.embedchain.ai/get-started/quickstart).
    """
    )

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """Hi, I'm Unacademy UPSC AI bot, who can answer any questions related to UPSC preparation.
            Let me help you prepare better for UPSC.\n
Sample questions:
- What are the subjects in UPSC CSE?
- What is the CSE scholarship price amount?
- What are different indian calendar forms?
            """,
        }
    ]

for message in st.session_state.messages:
    role = message["role"]
    with st.chat_message(role, avatar=assistant_avatar_url if role == "assistant" else None):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me anything!"):
    with st.chat_message("user"):
        st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant", avatar=assistant_avatar_url):
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

        for answer_chunk in generate(q):
            full_response += answer_chunk
            msg_placeholder.markdown(full_response)

        answer, citations = results["answer"], results["citations"]

        if citations:
            full_response += "\n\n**Sources**:\n"
            sources = list(set(map(lambda x: x[1], citations)))
            for i, source in enumerate(sources):
                full_response += f"{i+1}. {source}\n"

        msg_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
