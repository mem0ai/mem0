from embedchain.config import ChatConfig, CustomAppConfig
from embedchain.embedchain import EmbedChain


class CustomApp(EmbedChain):
    """
    The custom EmbedChain app.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    dry_run(query): test your prompt without consuming tokens.
    """

    def __init__(self, config: CustomAppConfig = None):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        :raises ValueError: Config must be provided for custom app
        """
        if config is None:
            raise ValueError("Config must be provided for custom app")

        super().__init__(config)

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        # messages = []
        # messages.append({"role": "user", "content": prompt})
        # response = openai.ChatCompletion.create(
        #     model=config.model,
        #     messages=messages,
        #     temperature=config.temperature,
        #     max_tokens=config.max_tokens,
        #     top_p=config.top_p,
        #     stream=config.stream,
        # )

        # if config.stream:
        #     return self._stream_llm_model_response(response)
        # else:
        #     return response["choices"][0]["message"]["content"]
        raise NotImplementedError("Not yet implemented for custom app")

    def _stream_llm_model_response(self, response):
        """
        This is a generator for streaming response from the OpenAI completions API
        """
        for line in response:
            chunk = line["choices"][0].get("delta", {}).get("content", "")
            yield chunk
