import chromadb
import openai
import os

from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.embeddings.openai import OpenAIEmbeddings

from embedchain.loaders.youtube_video import YoutubeVideoLoader
from embedchain.loaders.pdf_file import PdfFileLoader
from embedchain.loaders.web_page import WebPageLoader
from embedchain.chunkers.youtube_video import YoutubeVideoChunker
from embedchain.chunkers.pdf_file import PdfFileChunker
from embedchain.chunkers.web_page import WebPageChunker

load_dotenv()

embeddings = OpenAIEmbeddings()

ABS_PATH = os.getcwd()
DB_DIR = os.path.join(ABS_PATH, "db")

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-ada-002"
)


class EmbedChain:
    def __init__(self):
        self.chromadb_client = self._get_or_create_db()
        self.collection = self._get_or_create_collection()
        self.user_asks = []

    def _get_loader(self, data_type):
        loaders = {
            'youtube_video': YoutubeVideoLoader(),
            'pdf_file': PdfFileLoader(),
            'web_page': WebPageLoader()
        }
        if data_type in loaders:
            return loaders[data_type]
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _get_chunker(self, data_type):
        chunkers = {
            'youtube_video': YoutubeVideoChunker(),
            'pdf_file': PdfFileChunker(),
            'web_page': WebPageChunker()
        }
        if data_type in chunkers:
            return chunkers[data_type]
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def add(self, data_type, url):
        loader = self._get_loader(data_type)
        chunker = self._get_chunker(data_type)
        self.user_asks.append([data_type, url])
        self.load_and_embed(loader, chunker, url)

    def _get_or_create_db(self):
        client_settings = chromadb.config.Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=DB_DIR,
            anonymized_telemetry=False
        )
        return chromadb.Client(client_settings)

    def _get_or_create_collection(self):
        return self.chromadb_client.get_or_create_collection(
            'embedchain_store', embedding_function=openai_ef,
        )

    def load_embeddings_to_db(self, loader, chunker, url):
        embeddings_data = chunker.create_chunks(loader, url)
        documents = embeddings_data["documents"]
        metadatas = embeddings_data["metadatas"]
        ids = embeddings_data["ids"]
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Successfully saved {url}. Total chunks count: {self.collection.count()}")

    def load_and_embed(self, loader, chunker, url):
        return self.load_embeddings_to_db(loader, chunker, url)

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

    def get_answer_from_llm(self, query, context):
        prompt = f"""Use the following pieces of context to answer the query at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.
        {context}
        Query: {query}
        Helpful Answer:
        """
        answer = self.get_openai_answer(prompt)
        return answer

    def query(self, input_query):
        result = self.collection.query(
            query_texts=[input_query,],
            n_results=1,
        )
        result_formatted = self._format_result(result)
        answer = self.get_answer_from_llm(input_query, result_formatted[0][0].page_content)
        return answer


class App(EmbedChain):
    pass
