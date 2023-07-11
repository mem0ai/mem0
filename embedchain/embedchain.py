import logging
import os
from string import Template

import openai
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.memory import ConversationBufferMemory

from embedchain.config import AddConfig, ChatConfig, InitConfig, QueryConfig
from embedchain.config.QueryConfig import DEFAULT_PROMPT
from embedchain.data_formatter import DataFormatter

gpt4all_model = None

load_dotenv()

ABS_PATH = os.getcwd()
DB_DIR = os.path.join(ABS_PATH, "db")

memory = ConversationBufferMemory()


class EmbedChain:
    def __init__(self, config: InitConfig):
        """
        Initializes the EmbedChain instance, sets up a vector DB client and
        creates a collection.

        :param config: InitConfig instance to load as configuration.
        """

        self.config = config
        self.db_client = self.config.db.client
        self.collection = self.config.db.collection
        self.user_asks = []

    def add(self, data_type, url, config: AddConfig = None):
        """
        Adds the data from the given URL to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param data_type: The type of the data to add.
        :param url: The URL where the data is located.
        :param config: Optional. The `AddConfig` instance to use as configuration
        options.
        """
        if config is None:
            config = AddConfig()

        data_formatter = DataFormatter(data_type, config)
        self.user_asks.append([data_type, url])
        self.load_and_embed(data_formatter.loader, data_formatter.chunker, url)

    def add_local(self, data_type, content, config: AddConfig = None):
        """
        Adds the data you supply to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param data_type: The type of the data to add.
        :param content: The local data. Refer to the `README` for formatting.
        :param config: Optional. The `AddConfig` instance to use as
        configuration options.
        """
        if config is None:
            config = AddConfig()

        data_formatter = DataFormatter(data_type, config)
        self.user_asks.append([data_type, content])
        self.load_and_embed(
            data_formatter.loader,
            data_formatter.chunker,
            content,
        )

    def load_and_embed(self, loader, chunker, src):
        """
        Loads the data from the given URL, chunks it, and adds it to database.

        :param loader: The loader to use to load the data.
        :param chunker: The chunker to use to chunk the data.
        :param src: The data to be handled by the loader. Can be a URL for
        remote sources or local content for local loaders.
        """
        embeddings_data = chunker.create_chunks(loader, src)
        documents = embeddings_data["documents"]
        metadatas = embeddings_data["metadatas"]
        ids = embeddings_data["ids"]
        # get existing ids, and discard doc if any common id exist.
        existing_docs = self.collection.get(
            ids=ids,
            # where={"url": src}
        )
        existing_ids = set(existing_docs["ids"])

        if len(existing_ids):
            data_dict = {
                id: (doc, meta) for id, doc, meta in zip(ids, documents, metadatas)
            }
            data_dict = {
                id: value for id, value in data_dict.items() if id not in existing_ids
            }

            if not data_dict:
                print(f"All data from {src} already exists in the database.")
                return

            ids = list(data_dict.keys())
            documents, metadatas = zip(*data_dict.values())

        chunks_before_addition = self.count()
        self.collection.add(documents=documents, metadatas=list(metadatas), ids=ids)
        print(
            (
                f"Successfully saved {src}. New chunks count: "
                f"{self.count() - chunks_before_addition}"
            )
        )

    def _format_result(self, results):
        return [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def get_llm_model_answer(self, prompt):
        raise NotImplementedError

    def retrieve_from_database(self, input_query, config: QueryConfig):
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query

        :param input_query: The query to use.
        :param config: The query configuration.
        :return: The content of the document that matched your query.
        """
        result = self.collection.query(
            query_texts=[
                input_query,
            ],
            n_results=config.number_documents,
        )
        results_formatted = self._format_result(result)
        contents = [result[0].page_content for result in results_formatted]
        return contents

    def generate_prompt(self, input_query, contexts, config: QueryConfig):
        """
        Generates a prompt based on the given query and context, ready to be
        passed to an LLM

        :param input_query: The query to use.
        :param contexts: List of similar documents to the query used as context.
        :param config: Optional. The `QueryConfig` instance to use as
        configuration options.
        :return: The prompt
        """
        context_string = (" | ").join(contexts)
        if not config.history:
            prompt = config.template.substitute(
                context=context_string, query=input_query
            )
        else:
            prompt = config.template.substitute(
                context=context_string, query=input_query, history=config.history
            )
        return prompt

    def get_answer_from_llm(self, prompt, config: ChatConfig):
        """
        Gets an answer based on the given query and context by passing it
        to an LLM.

        :param query: The query to use.
        :param context: Similar documents to the query used as context.
        :return: The answer.
        """

        return self.get_llm_model_answer(prompt, config)

    def query(self, input_query, config: QueryConfig = None):
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        :param input_query: The query to use.
        :param config: Optional. The `QueryConfig` instance to use as
        configuration options.
        :return: The answer to the query.
        """
        if config is None:
            config = QueryConfig()
        contexts = self.retrieve_from_database(input_query, config)
        prompt = self.generate_prompt(input_query, contexts, config)
        logging.info(f"Prompt: {prompt}")
        answer = self.get_answer_from_llm(prompt, config)
        logging.info(f"Answer: {answer}")
        return answer

    def chat(self, input_query, config: ChatConfig = None):
        """
        Queries the vector database on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        Maintains last 5 conversations in memory.
        :param input_query: The query to use.
        :param config: Optional. The `ChatConfig` instance to use as
        configuration options.
        :return: The answer to the query.
        """
        if config is None:
            config = ChatConfig()

        contexts = self.retrieve_from_database(input_query, config)

        global memory
        chat_history = memory.load_memory_variables({})["history"]

        if chat_history:
            config.set_history(chat_history)

        prompt = self.generate_prompt(input_query, contexts, config)
        logging.info(f"Prompt: {prompt}")
        answer = self.get_answer_from_llm(prompt, config)

        memory.chat_memory.add_user_message(input_query)

        if isinstance(answer, str):
            memory.chat_memory.add_ai_message(answer)
            logging.info(f"Answer: {answer}")
            return answer
        else:
            # this is a streamed response and needs to be handled differently.
            return self._stream_chat_response(answer)

    def _stream_chat_response(self, answer):
        streamed_answer = ""
        for chunk in answer:
            streamed_answer.join(chunk)
            yield chunk
        memory.chat_memory.add_ai_message(streamed_answer)
        logging.info(f"Answer: {streamed_answer}")

    def dry_run(self, input_query, config: QueryConfig = None):
        """
        A dry run does everything except send the resulting prompt to
        the LLM. The purpose is to test the prompt, not the response.
        You can use it to test your prompt, including the context provided
        by the vector database's doc retrieval.
        The only thing the dry run does not consider is the cut-off due to
        the `max_tokens` parameter.

        :param input_query: The query to use.
        :param config: Optional. The `QueryConfig` instance to use as
        configuration options.
        :return: The prompt that would be sent to the LLM
        """
        if config is None:
            config = QueryConfig()
        contexts = self.retrieve_from_database(input_query, config)
        prompt = self.generate_prompt(input_query, contexts, config)
        logging.info(f"Prompt: {prompt}")
        return prompt

    def count(self):
        """
        Count the number of embeddings.

        :return: The number of embeddings.
        """
        return self.collection.count()

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        `App` has to be reinitialized after using this method.
        """
        self.db_client.reset()


class App(EmbedChain):
    """
    The EmbedChain app.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    dry_run(query): test your prompt without consuming tokens.
    """

    def __init__(self, config: InitConfig = None):
        """
        :param config: InitConfig instance to load as configuration. Optional.
        """
        if config is None:
            config = InitConfig()

        if not config.ef:
            config._set_embedding_function_to_default()

        if not config.db:
            config._set_db_to_default()

        super().__init__(config)

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        messages = []
        messages.append({"role": "user", "content": prompt})
        response = openai.ChatCompletion.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            stream=config.stream,
        )

        if config.stream:
            return self._stream_llm_model_response(response)
        else:
            return response["choices"][0]["message"]["content"]

    def _stream_llm_model_response(self, response):
        """
        This is a generator for streaming response from the OpenAI completions API
        """
        for line in response:
            chunk = line["choices"][0].get("delta", {}).get("content", "")
            yield chunk


class OpenSourceApp(EmbedChain):
    """
    The OpenSource app.
    Same as App, but uses an open source embedding model and LLM.

    Has two function: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    """

    def __init__(self, config: InitConfig = None):
        """
        :param config: InitConfig instance to load as configuration. Optional.
        `ef` defaults to open source.
        """
        print(
            "Loading open source embedding model. This may take some time..."
        )  # noqa:E501
        if not config:
            config = InitConfig()

        if not config.ef:
            config._set_embedding_function(
                embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            )

        if not config.db:
            config._set_db_to_default()

        print("Successfully loaded open source embedding model.")
        super().__init__(config)

    def get_llm_model_answer(self, prompt, config: ChatConfig):
        from gpt4all import GPT4All

        global gpt4all_model
        if gpt4all_model is None:
            gpt4all_model = GPT4All("orca-mini-3b.ggmlv3.q4_0.bin")
        response = gpt4all_model.generate(prompt=prompt, streaming=config.stream)
        return response


class EmbedChainPersonApp:
    """
    Base class to create a person bot.
    This bot behaves and speaks like a person.

    :param person: name of the person, better if its a well known person.
    :param config: InitConfig instance to load as configuration.
    """

    def __init__(self, person, config: InitConfig = None):
        self.person = person
        self.person_prompt = f"You are {person}. Whatever you say, you will always say in {person} style."  # noqa:E501
        self.template = Template(self.person_prompt + " " + DEFAULT_PROMPT)
        if config is None:
            config = InitConfig()
        super().__init__(config)


class PersonApp(EmbedChainPersonApp, App):
    """
    The Person app.
    Extends functionality from EmbedChainPersonApp and App
    """

    def query(self, input_query, config: QueryConfig = None):
        query_config = QueryConfig(
            template=self.template,
        )
        return super().query(input_query, query_config)

    def chat(self, input_query, config: ChatConfig = None):
        chat_config = ChatConfig(
            template=self.template,
        )
        return super().chat(input_query, chat_config)


class PersonOpenSourceApp(EmbedChainPersonApp, OpenSourceApp):
    """
    The Person app.
    Extends functionality from EmbedChainPersonApp and OpenSourceApp
    """

    def query(self, input_query, config: QueryConfig = None):
        query_config = QueryConfig(
            template=self.template,
        )
        return super().query(input_query, query_config)

    def chat(self, input_query, config: ChatConfig = None):
        chat_config = ChatConfig(
            template=self.template,
        )
        return super().chat(input_query, chat_config)
