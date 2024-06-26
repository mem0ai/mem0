import datetime
import json
import os
import re
import traceback
from typing import Any, List, Mapping, Optional, Union

import requests

from embedchain import App
from embedchain.config.vectordb.vectara import VectaraDBConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

BASE_URL = "https://api.vectara.io/v1"
START_SNIPPET = "<%START%>"
END_SNIPPET = "<%END%>"


class VectaraApp(App):
    def _remove_citation_from_text(self, text: str) -> str:
        pattern = r"\[\d+\]"
        return re.sub(pattern, "", text)

    def query(
        self,
        input_query: str,
        where: Optional[dict] = None,
        citations: bool = False,
        **kwargs: dict[str, Any],
    ) -> Union[tuple[str, list[tuple[str, dict]]], str]:
        """
        Queries Vectara by using it's end-to-end RAG functionality.

        :param input_query: The query to use.
        :type input_query: str
        :param where: A dictionary of key-value pairs to filter the database results., defaults to None
        :type where: Optional[dict[str, str]], optional
        :param kwargs: To read more params for the query function. Ex. we use citations boolean
        param to return context along with the answer
        :type kwargs: dict[str, Any]
        :return: The answer to the query, with citations if the citation flag is True
        or the dry run result
        :rtype: str, if citations is False, otherwise tuple[str, list[tuple[str,str,str]]]
        """
        # get the answer with Citation from Vectara
        answer, contexts = self.db._vectara_query(
            query_str=input_query, top_k=10, filter=self.db._form_filter_str(where), summarize=True, **kwargs
        )
        if not citations:
            answer = self._remove_citation_from_text(answer)
            answer = answer.replace(START_SNIPPET, "").replace(END_SNIPPET, "").replace(" . ", ". ")

        # Send anonymous telemetry
        self.telemetry.capture(event_name="query", properties=self._telemetry_props)

        if citations:
            return answer, contexts
        else:
            return answer


@register_deserializable
class VectaraDB(BaseVectorDB):
    """
    Vectara as vector database
    """

    def __init__(
        self,
        config: Optional[VectaraDBConfig] = None,
    ):
        """Vectara as vector database.

        :param config: Vectara database config, defaults to None
        :type config: VectaraDBConfig, optional
        :raises ValueError: No config provided
        """
        if config is None:
            self.config = VectaraDBConfig()
        else:
            if not isinstance(config, VectaraDBConfig):
                raise TypeError(
                    "config is not a `VectaraDBConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )
            self.config = config

        self.customer_id = os.environ.get("VECTARA_CUSTOMER_ID")
        self.vectara_oauth_client_id = os.environ.get("VECTARA_OAUTH_CLIENT_ID")
        self.vectara_oauth_secret = os.environ.get("VECTARA_OAUTH_SECRET")
        self.corpus_id = None

    def _initialize(self):
        """
        initialize the Vectara corpus
        """
        # Setup the Vectara corpus if it does not already exist
        self._setup_vectara_corpus()
        self.client = None
        self.jwt_token_expires_ts = None

    def _form_filter_str(self, where: Optional[dict[str, any]] = None) -> str:
        """
        Form a filter string from the where dict.
        """
        if where is None:
            return ""
        return " and ".join([f"(doc.{k} = '{v}')" for k, v in where.items()])

    def _get_jwt_token(self):
        """Connect to the server and get a JWT token."""
        token_endpoint = f"https://vectara-prod-{self.customer_id}.auth.us-west-2.amazoncognito.com/oauth2/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "client_credentials",
            "client_id": self.vectara_oauth_client_id,
            "client_secret": self.vectara_oauth_secret,
        }

        request_time = datetime.datetime.now().timestamp()
        response = requests.request(method="POST", url=token_endpoint, headers=headers, data=data)
        response_json = response.json()

        self.jwt_token = response_json.get("access_token")
        self.jwt_token_expires_ts = request_time + response_json.get("expires_in")
        return self.jwt_token

    def _request(
        self, endpoint: str, http_method: str = "POST", params: Mapping[str, Any] = None, data: Mapping[str, Any] = None
    ):
        url = f"{BASE_URL}/{endpoint}"

        current_ts = datetime.datetime.now().timestamp()
        if self.jwt_token_expires_ts is None or self.jwt_token_expires_ts - current_ts <= 60:
            self._get_jwt_token()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.jwt_token}",
            "customer-id": self.customer_id,
            "X-source": "embedchain",
        }

        response = requests.request(method=http_method, url=url, headers=headers, params=params, data=json.dumps(data))
        response.raise_for_status()
        return response.json()

    def _setup_vectara_corpus(self):
        """
        Check for an existing corpus in Vectara.
        If more than one exists - then return a message
        If exactly one exists with this name - ensure that the corpus has the correct metadata fields, and use it.
        If not, create it.
        """
        if self.corpus_id:
            return
        try:
            jwt_token = self._get_jwt_token()
            if not jwt_token:
                return "Unable to get JWT Token. Confirm your Client ID and Client Secret."

            list_corpora_response = self._request(
                endpoint="list-corpora", data={"numResults": 100, "filter": self.config.collection_name}
            )
            possible_corpora_ids_names_map = {
                corpus.get("id"): corpus.get("name")
                for corpus in list_corpora_response.get("corpus")
                if corpus.get("name") == self.config.collection_name
            }

            if len(possible_corpora_ids_names_map) > 1:
                return f"Multiple Corpora exist with name {self.config.collection_name}"
            if len(possible_corpora_ids_names_map) == 1:
                self.corpus_id = list(possible_corpora_ids_names_map.keys())[0]
            else:
                data = {
                    "corpus": {
                        "name": self.config.collection_name,
                        "filterAttributes": [
                            {
                                "name": "url",
                                "description": "url",
                                "indexed": True,
                                "type": "FILTER_ATTRIBUTE_TYPE__TEXT",
                                "level": "FILTER_ATTRIBUTE_LEVEL__DOCUMENT",
                            },
                            {
                                "name": "app_id",
                                "description": "app_id",
                                "indexed": True,
                                "type": "FILTER_ATTRIBUTE_TYPE__TEXT",
                                "level": "FILTER_ATTRIBUTE_LEVEL__DOCUMENT",
                            },
                        ],
                    }
                }
                create_corpus_response = self._request(endpoint="create-corpus", data=data)
                self.corpus_id = create_corpus_response.get("corpusId")

        except Exception as e:
            print(f"Exception in _setup_vectara_corpus: {e}")
            return str(e) + "\n" + "".join(traceback.TracebackException.from_exception(e).format())

    def get(self, ids: Optional[list[str]] = None, where: Optional[dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in Vectara

        :param ids: _list of doc ids to check for existence
        :type ids: list[str]
        :param where: to filter data
        :type where: dict[str, any]
        :param limit: limit the number of results
        :type limit: int
        :return: ids
        :rtype: Set[str]
        """
        self._setup_vectara_corpus()
        finished = False
        existing_ids = []
        page_key = None
        filter_str = self._form_filter_str(where)

        while not finished:
            data = {
                "corpusId": self.corpus_id,
                "numResults": 1000,
            }
            if page_key:
                data["pageKey"] = page_key
            if filter_str:
                data["metadataFilter"] = filter_str
            response = self._request(endpoint="list-documents", data=data)
            documents = response.get("document")
            new_ids = [doc["id"] for doc in documents if doc["id"] in ids]
            if limit:
                existing_ids.extend(new_ids[: max(0, limit - len(existing_ids))])
            else:
                existing_ids.extend(new_ids)
            next_page_key = response.get("nextPageKey", "")
            if next_page_key == "" or len(existing_ids) >= limit:
                finished = True
            else:
                page_key = next_page_key
        return {"ids": existing_ids}

    def add(
        self,
        documents: list[str],
        metadatas: list[object],
        ids: list[str],
        **kwargs: Optional[dict[str, any]],
    ):
        """add documents to Vectara

        :param documents: list of texts to add
        :type documents: list[str]
        :param metadatas: list of metadata associated with docs
        :type metadatas: list[object]
        :param ids: ids of docs
        :type ids: list[str]
        """
        self._setup_vectara_corpus()

        existing_ids = self.get(ids=ids).get("ids")
        new_ids = [id for id in ids if id not in existing_ids]
        print(f"Adding {len(new_ids)} new documents to Vectara (out of {len(ids)} submitted to indexing)...")

        for id, text, metadata in zip(ids, documents, metadatas):
            if id not in new_ids:
                continue
            document_metadata = self._normalize(metadata)
            data = {
                "customerId": self.customer_id,
                "corpusId": self.corpus_id,
                "document": {
                    "documentId": id,
                    "metadataJson": json.dumps(document_metadata),
                    "section": [{"text": text}],
                },
            }
            self._request(endpoint="index", data=data)

    def _normalize(self, metadata: dict) -> dict:
        result = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                result[key] = value
            else:
                # JSON encode all other types
                result[key] = json.dumps(value)
        return result

    def _vectara_query(
        self,
        query_str: str,
        top_k: int = 10,
        filter: str = "",
        lambda_val: float = 0.025,
        mmr_k: int = 50,
        mmr_diversity_bias: float = 0.3,
        summarize: bool = False,
        summary_k: int = 5,
        summary_lang: str = "eng",
        summary_prompt: str = "vectara-summary-ext-v1.2.0",
    ) -> List[Any]:
        """Query Vectara to get list of top_k results
        Args:
            query: Query Bundle
        """
        corpus_key = {
            "customerId": self.customer_id,
            "corpusId": self.corpus_id,
            "lexicalInterpolationConfig": {"lambda": lambda_val},
        }
        if len(filter) > 0:
            corpus_key["metadataFilter"] = filter
        else:
            corpus_key["metadataFilter"] = ""

        data = {
            "query": [
                {
                    "query": query_str,
                    "start": 0,
                    "numResults": mmr_k if mmr_diversity_bias > 0 else top_k,
                    "contextConfig": {
                        "sentencesBefore": 2,
                        "sentencesAfter": 2,
                        "startTag": START_SNIPPET,
                        "endTag": END_SNIPPET,
                    },
                    "corpusKey": [corpus_key],
                }
            ]
        }
        if mmr_diversity_bias > 0:
            data["query"][0]["rerankingConfig"] = {
                "rerankerId": 272725718,
                "mmrConfig": {"diversityBias": mmr_diversity_bias},
            }
        if summarize:
            data["query"][0]["summary"] = [
                {
                    "responseLang": summary_lang,
                    "maxSummarizedResults": summary_k,
                    "summarizerPromptName": summary_prompt,
                }
            ]

        result = self._request(endpoint="query", data=data)

        responses = result["responseSet"][0]["response"]
        documents = result["responseSet"][0]["document"]

        res = []
        for x in responses[:top_k]:
            md = {m["name"]: m["value"] for m in x["metadata"]}
            md["score"] = x["score"]
            doc_num = x["documentIndex"]
            doc_md = {m["name"]: m["value"] for m in documents[doc_num]["metadata"]}
            md.update(doc_md)
            text = x["text"]
            res.append((text, md))

        summary = result["responseSet"][0]["summary"][0]["text"] if summarize else None

        return summary, res

    def query(
        self,
        input_query: list[str],
        n_results: int,
        where: dict[str, any],
        citations: bool = False,
        **kwargs: Optional[dict[str, any]],
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        Issue a query on Vectara using semantic search
        :param input_query: list of query string
        :type input_query: list[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: Optional. to filter data
        :type where: dict[str, any]
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: list[str], if citations=False, otherwise list[tuple[str, str, str]]
        """
        self._setup_vectara_corpus()
        _, res = self._vectara_query(
            query_str=input_query, top_k=n_results, filter=self._form_filter_str(where), **kwargs
        )
        if citations:
            return res
        else:
            return [r[0] for r in res]

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        :param name: Name of the collection.
        :type name: str
        """
        if not isinstance(name, str):
            raise TypeError("Collection name must be a string")
        self.config.collection_name = name

    def count(self) -> int:
        """
        Count number of documents in the database.

        :return: number of documents
        :rtype: int
        """
        self._setup_vectara_corpus()
        finished = False
        count = 0
        page_key = ""
        while not finished:
            data = {
                "corpusId": self.corpus_id,
                "numResults": 1000,
                "pageKey": page_key,
            }
            response = self._request(endpoint="list-documents", data=data)
            documents = response.get("document")
            count += len(documents)
            next_page_key = response.get("nextPageKey", "")
            if next_page_key == "":
                finished = True
            else:
                page_key = next_page_key

        return count

    def reset(self):
        """
        Resets the database.
        """
        self._setup_vectara_corpus()
        data = {"corpusId": self.corpus_id}
        self._request(endpoint="reset-corpus", data=data)
