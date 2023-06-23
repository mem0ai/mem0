import openai
import os

from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.embeddings.openai import OpenAIEmbeddings

from embedchain.loaders.youtube_video import YoutubeVideoLoader
from embedchain.loaders.pdf_file import PdfFileLoader
from embedchain.loaders.web_page import WebPageLoader
from embedchain.loaders.local_qna_pair import LocalQnaPairLoader
from embedchain.chunkers.youtube_video import YoutubeVideoChunker
from embedchain.chunkers.pdf_file import PdfFileChunker
from embedchain.chunkers.web_page import WebPageChunker
from embedchain.chunkers.qna_pair import QnaPairChunker
from embedchain.vectordb.chroma_db import ChromaDB

load_dotenv()

embeddings = OpenAIEmbeddings()

ABS_PATH = os.getcwd()
DB_DIR = os.path.join(ABS_PATH, "db")


class EmbedChain:
    def __init__(self, db=None):
        """
         Initializes the EmbedChain instance, sets up a vector DB client and
        creates a collection.

        :param db: The instance of the VectorDB subclass.
        """
        if db is None:
            db = ChromaDB()
        self.db_client = db.client
        self.collection = db.collection
        self.user_asks = []

    def _get_loader(self, data_type):
        """
        Returns the appropriate data loader for the given data type.

        :param data_type: The type of the data to load.
        :return: The loader for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        loaders = {
            'youtube_video': YoutubeVideoLoader(),
            'pdf_file': PdfFileLoader(),
            'web_page': WebPageLoader(),
            'qna_pair': LocalQnaPairLoader()
        }
        if data_type in loaders:
            return loaders[data_type]
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _get_chunker(self, data_type):
        """
        Returns the appropriate chunker for the given data type.

        :param data_type: The type of the data to chunk.
        :return: The chunker for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        chunkers = {
            'youtube_video': YoutubeVideoChunker(),
            'pdf_file': PdfFileChunker(),
            'web_page': WebPageChunker(),
            'qna_pair': QnaPairChunker(),
        }
        if data_type in chunkers:
            return chunkers[data_type]
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def add(self, data_type, url):
        """
        Adds the data from the given URL to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param data_type: The type of the data to add.
        :param url: The URL where the data is located.
        """
        loader = self._get_loader(data_type)
        chunker = self._get_chunker(data_type)
        self.user_asks.append([data_type, url])
        self.load_and_embed(loader, chunker, url)

    def add_local(self, data_type, content):
        """
        Adds the data you supply to the vector db.
        Loads the data, chunks it, create embedding for each chunk
        and then stores the embedding to vector database.

        :param data_type: The type of the data to add.
        :param content: The local data. Refer to the `README` for formatting.
        """
        loader = self._get_loader(data_type)
        chunker = self._get_chunker(data_type)
        self.user_asks.append([data_type, content])
        self.load_and_embed(loader, chunker, content)

    def load_and_embed(self, loader, chunker, url):
        """
        Loads the data from the given URL, chunks it, and adds it to the database.

        :param loader: The loader to use to load the data.
        :param chunker: The chunker to use to chunk the data.
        :param url: The URL where the data is located.
        """
        embeddings_data = chunker.create_chunks(loader, url)
        documents = embeddings_data["documents"]
        metadatas = embeddings_data["metadatas"]
        ids = embeddings_data["ids"]
        # get existing ids, and discard doc if any common id exist.
        existing_docs = self.collection.get(
            ids=ids,
            # where={"url": url}
        )
        existing_ids = set(existing_docs["ids"])

        if len(existing_ids):
            data_dict = {id: (doc, meta) for id, doc, meta in zip(ids, documents, metadatas)}
            data_dict = {id: value for id, value in data_dict.items() if id not in existing_ids}

            if not data_dict:
                print(f"All data from {url} already exists in the database.")
                return

            ids = list(data_dict.keys())
            documents, metadatas = zip(*data_dict.values())

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Successfully saved {url}. Total chunks count: {self.collection.count()}")

    def _format_result(self, results):
        return [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def get_openai_answer(self, prompt):
        messages = []
        messages.append({
            "role": "user", "content": prompt
        })
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages,
            temperature=0,
            max_tokens=1000,
            top_p=1,
        )
        return response["choices"][0]["message"]["content"]
    
    def retrieve_from_database(self, input_query):
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query

        :param input_query: The query to use.
        :return: The content of the document that matched your query.
        """
        result = self.collection.query(
            query_texts=[input_query,],
            n_results=1,
        )
        result_formatted = self._format_result(result)
        content = result_formatted[0][0].page_content
        return content
    
    def generate_prompt(self, input_query, context):
        """
        Generates a prompt based on the given query and context, ready to be passed to an LLM

        :param input_query: The query to use.
        :param context: Similar documents to the query used as context.
        :return: The prompt
        """
        prompt = f"""Use the following pieces of context to answer the query at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
        {context}
        Query: {input_query}
        Helpful Answer:
        """
        return prompt

    def get_answer_from_llm(self, prompt):
        """
        Gets an answer based on the given query and context by passing it
        to an LLM.

        :param query: The query to use.
        :param context: Similar documents to the query used as context.
        :return: The answer.
        """
        answer = self.get_openai_answer(prompt)
        return answer

    def query(self, input_query):
        """
        Queries the vector database based on the given input query.
        Gets relevant doc based on the query and then passes it to an
        LLM as context to get the answer.

        :param input_query: The query to use.
        :return: The answer to the query.
        """
        context = self.retrieve_from_database(input_query)
        prompt = self.generate_prompt(input_query, context)
        answer = self.get_answer_from_llm(prompt)
        return answer


class App(EmbedChain):
    """
    The EmbedChain app.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    """
    pass
