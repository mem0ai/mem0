from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class DistanceStrategy(str, Enum):
    """Enumerator of the Distance strategies for calculating distances
    between vectors."""

    EUCLIDEAN_DISTANCE = "EUCLIDEAN_DISTANCE"
    MAX_INNER_PRODUCT = "MAX_INNER_PRODUCT"
    DOT_PRODUCT = "DOT_PRODUCT"
    JACCARD = "JACCARD"
    COSINE = "COSINE"


class BaseRetrievalStrategy(ABC):
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        raise ImportError("The 'elasticsearch' library is required. Please install it using 'pip install elasticsearch'.")
    

    @abstractmethod
    def query(
        self,
        query_vector: Union[List[float], None],
        query: Union[str, None] = None,
        *,
        k: int,
        fetch_k: int,
        vector_query_field: str,
        text_field: str,
        filter: List[dict],
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        """
        Executes when a search is performed on the store.

        Args:
            query_vector: The query vector,
                          or None if not using vector-based query.
            query: The text query, or None if not using text-based query.
            k: The total number of results to retrieve.
            fetch_k: The number of results to fetch initially.
            vector_query_field: The field containing the vector
                                representations in the index.
            text_field: The field containing the text data in the index.
            filter: List of filter clauses to apply to the query.
            similarity: The similarity strategy to use, or None if not using one.

        Returns:
            Dict: The Elasticsearch query body.
        """

    @abstractmethod
    def index(
        self,
        dims_length: Union[int, None],
        vector_query_field: str,
        text_field: str,
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        """
        Executes when the index is created.

        Args:
            dims_length: Numeric length of the embedding vectors,
                        or None if not using vector-based query.
            vector_query_field: The field containing the vector
                                representations in the index.
            text_field: The field containing the text data in the index.
            similarity: The similarity strategy to use,
                        or None if not using one.

        Returns:
            Dict: The Elasticsearch settings and mappings for the strategy.
        """
    
    def before_index_setup(
        self, client: "Elasticsearch", text_field: str, vector_query_field: str
    ) -> None:
        """
        Executes before the index is created. Used for setting up
        any required Elasticsearch resources like a pipeline.

        Args:
            client: The Elasticsearch client.
            text_field: The field containing the text data in the index.
            vector_query_field: The field containing the vector
                                representations in the index.
        """

    def require_inference(self) -> bool:
        """
        Returns whether or not the strategy requires inference
        to be performed on the text before it is added to the index.

        Returns:
            bool: Whether or not the strategy requires inference
            to be performed on the text before it is added to the index.
        """
        return True


class ApproxRetrievalStrategy(BaseRetrievalStrategy):
    """Approximate retrieval strategy using the `HNSW` algorithm."""
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        raise ImportError("The 'elasticsearch' library is required. Please install it using 'pip install elasticsearch'.")

    def __init__(
        self,
        query_model_id: Optional[str] = None,
        hybrid: Optional[bool] = False,
        rrf: Optional[Union[dict, bool]] = True,
    ):
        self.query_model_id = query_model_id
        self.hybrid = hybrid

        # RRF has two optional parameters
        # 'rank_constant', 'window_size'
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html
        self.rrf = rrf

    def query(
        self,
        query_vector: Union[List[float], None],
        query: Union[str, None],
        k: int,
        fetch_k: int,
        vector_query_field: str,
        text_field: str,
        filter: List[dict],
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        knn = {
            "filter": filter,
            "field": vector_query_field,
            "k": k,
            "num_candidates": fetch_k,
        }

        # Embedding provided via the embedding function
        if query_vector is not None and not self.query_model_id:
            knn["query_vector"] = list(query_vector)

        # Case 2: Used when model has been deployed to
        # Elasticsearch and can infer the query vector from the query text
        elif query and self.query_model_id:
            knn["query_vector_builder"] = {
                "text_embedding": {
                    "model_id": self.query_model_id,  # use 'model_id' argument
                    "model_text": query,  # use 'query' argument
                }
            }

        else:
            raise ValueError(
                "You must provide an embedding function or a"
                " query_model_id to perform a similarity search."
            )

        # If hybrid, add a query to the knn query
        # RRF is used to even the score from the knn query and text query
        # RRF has two optional parameters: {'rank_constant':int, 'window_size':int}
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html
        if self.hybrid:
            query_body = {
                "knn": knn,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match": {
                                    text_field: {
                                        "query": query,
                                    }
                                }
                            }
                        ],
                        "filter": filter,
                    }
                },
            }

            if isinstance(self.rrf, dict):
                query_body["rank"] = {"rrf": self.rrf}
            elif isinstance(self.rrf, bool) and self.rrf is True:
                query_body["rank"] = {"rrf": {}}

            return query_body
        else:
            return {"knn": knn}

    # def before_index_setup(
    #     self, client: "Elasticsearch", text_field: str, vector_query_field: str
    # ) -> None:
    #     if self.query_model_id:
    #         model_must_be_deployed(client, self.query_model_id)

    def index(
        self,
        dims_length: Union[int, None],
        vector_query_field: str,
        text_field: str,
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        """Create the mapping for the Elasticsearch index."""

        if similarity is DistanceStrategy.COSINE:
            similarityAlgo = "cosine"
        elif similarity is DistanceStrategy.EUCLIDEAN_DISTANCE:
            similarityAlgo = "l2_norm"
        elif similarity is DistanceStrategy.DOT_PRODUCT:
            similarityAlgo = "dot_product"
        elif similarity is DistanceStrategy.MAX_INNER_PRODUCT:
            similarityAlgo = "max_inner_product"
        else:
            raise ValueError(f"Similarity {similarity} not supported.")

        return {
            "mappings": {
                "properties": {
                    vector_query_field: {
                        "type": "dense_vector",
                        "dims": dims_length,
                        "index": True,
                        "similarity": similarityAlgo,
                    },
                }
            }
        }


class ExactRetrievalStrategy(BaseRetrievalStrategy):
    """Exact retrieval strategy using the `script_score` query."""

    def query(
        self,
        query_vector: Union[List[float], None],
        query: Union[str, None],
        k: int,
        fetch_k: int,
        vector_query_field: str,
        text_field: str,
        filter: Union[List[dict], None],
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        if similarity is DistanceStrategy.COSINE:
            similarityAlgo = (
                f"cosineSimilarity(params.query_vector, '{vector_query_field}') + 1.0"
            )
        elif similarity is DistanceStrategy.EUCLIDEAN_DISTANCE:
            similarityAlgo = (
                f"1 / (1 + l2norm(params.query_vector, '{vector_query_field}'))"
            )
        elif similarity is DistanceStrategy.DOT_PRODUCT:
            similarityAlgo = f"""
            double value = dotProduct(params.query_vector, '{vector_query_field}');
            return sigmoid(1, Math.E, -value);
            """
        else:
            raise ValueError(f"Similarity {similarity} not supported.")

        queryBool: Dict = {"match_all": {}}
        if filter:
            queryBool = {"bool": {"filter": filter}}

        return {
            "query": {
                "script_score": {
                    "query": queryBool,
                    "script": {
                        "source": similarityAlgo,
                        "params": {"query_vector": query_vector},
                    },
                },
            }
        }

    def index(
        self,
        dims_length: Union[int, None],
        vector_query_field: str,
        text_field: str,
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        """Create the mapping for the Elasticsearch index."""

        return {
            "mappings": {
                "properties": {
                    vector_query_field: {
                        "type": "dense_vector",
                        "dims": dims_length,
                        "index": False,
                    },
                }
            }
        }


class SparseRetrievalStrategy(BaseRetrievalStrategy):
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        raise ImportError("The 'elasticsearch' library is required. Please install it using 'pip install elasticsearch'.")
    """Sparse retrieval strategy using the `text_expansion` processor."""


    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id or ".elser_model_1"

    def query(
        self,
        query_vector: Union[List[float], None],
        query: Union[str, None],
        k: int,
        fetch_k: int,
        vector_query_field: str,
        text_field: str,
        filter: List[dict],
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        return {
            "query": {
                "bool": {
                    "must": [
                        {
                            "text_expansion": {
                                f"{vector_query_field}.tokens": {
                                    "model_id": self.model_id,
                                    "model_text": query,
                                }
                            }
                        }
                    ],
                    "filter": filter,
                }
            }
        }

    def _get_pipeline_name(self) -> str:
        return f"{self.model_id}_sparse_embedding"

    def before_index_setup(
        self, client: "Elasticsearch", text_field: str, vector_query_field: str
    ) -> None:
        if self.model_id:
            # model_must_be_deployed(client, self.model_id)

            # Create a pipeline for the model
            client.ingest.put_pipeline(
                id=self._get_pipeline_name(),
                description="Embedding pipeline for langchain vectorstore",
                processors=[
                    {
                        "inference": {
                            "model_id": self.model_id,
                            "target_field": vector_query_field,
                            "field_map": {text_field: "text_field"},
                            "inference_config": {
                                "text_expansion": {"results_field": "tokens"}
                            },
                        }
                    }
                ],
            )

    def index(
        self,
        dims_length: Union[int, None],
        vector_query_field: str,
        text_field: str,
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        return {
            "mappings": {
                "properties": {
                    vector_query_field: {
                        "properties": {"tokens": {"type": "rank_features"}}
                    }
                }
            },
            "settings": {"default_pipeline": self._get_pipeline_name()},
        }

    def require_inference(self) -> bool:
        return False


class BM25RetrievalStrategy(BaseRetrievalStrategy):
    """Retrieval strategy using the native BM25 algorithm of Elasticsearch."""

    def __init__(self, k1: Union[float, None] = None, b: Union[float, None] = None):
        self.k1 = k1
        self.b = b

    def query(
        self,
        query_vector: Union[List[float], None],
        query: Union[str, None],
        k: int,
        fetch_k: int,
        vector_query_field: str,
        text_field: str,
        filter: List[dict],
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        return {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                text_field: {
                                    "query": query,
                                }
                            },
                        },
                    ],
                    "filter": filter,
                },
            },
        }

    def index(
        self,
        dims_length: Union[int, None],
        vector_query_field: str,
        text_field: str,
        similarity: Union[DistanceStrategy, None],
    ) -> Dict:
        mappings: Dict = {
            "properties": {
                text_field: {
                    "type": "text",
                    "similarity": "custom_bm25",
                },
            },
        }
        settings: Dict = {
            "similarity": {
                "custom_bm25": {
                    "type": "BM25",
                },
            },
        }

        if self.k1 is not None:
            settings["similarity"]["custom_bm25"]["k1"] = self.k1

        if self.b is not None:
            settings["similarity"]["custom_bm25"]["b"] = self.b

        return {"mappings": mappings, "settings": settings}

    def require_inference(self) -> bool:
        return False


class ESVectorConfig(BaseModel):
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        raise ImportError("The 'elasticsearch' library is required. Please install it using 'pip install elasticsearch'.")

    Elasticsearch: ClassVar[type] = Elasticsearch


    collection_name: str = Field("mem0", description="Name of the index")
    client: Optional[Elasticsearch] = Field(None, description="Existing Elasticsearch client instance")
    endpoint: Optional[str] = Field(None, description="Endpoint for Elasticsearch server")
    api_key: Optional[str] = Field(None, description="API key for Elasticsearch server")
    vector_query_field: Optional[str] = Field('vector', description="Field name of vector")
    query_field: Optional[str] = Field('text', description="Field name of text")
    distance_strategy: Optional[
            Literal[
                DistanceStrategy.COSINE,
                DistanceStrategy.DOT_PRODUCT,
                DistanceStrategy.EUCLIDEAN_DISTANCE,
                DistanceStrategy.MAX_INNER_PRODUCT,
            ]
        ] = Field(None, description="distance strategy for calculating similarity")
    strategy: BaseRetrievalStrategy = Field(
        ApproxRetrievalStrategy(),
        description="Retrieva strategy for search"
    )

    class Config:
        arbitrary_types_allowed = True

    
    @staticmethod
    def ExactRetrievalStrategy() -> "ExactRetrievalStrategy":
        """Used to perform brute force / exact
        nearest neighbor search via script_score."""
        return ExactRetrievalStrategy()

    @staticmethod
    def ApproxRetrievalStrategy(
        query_model_id: Optional[str] = None,
        hybrid: Optional[bool] = False,
        rrf: Optional[Union[dict, bool]] = True,
    ) -> "ApproxRetrievalStrategy":
        """Used to perform approximate nearest neighbor search
        using the HNSW algorithm.

        At build index time, this strategy will create a
        dense vector field in the index and store the
        embedding vectors in the index.

        At query time, the text will either be embedded using the
        provided embedding function or the query_model_id
        will be used to embed the text using the model
        deployed to Elasticsearch.

        if query_model_id is used, do not provide an embedding function.

        Args:
            query_model_id: Optional. ID of the model to use to
                            embed the query text within the stack. Requires
                            embedding model to be deployed to Elasticsearch.
            hybrid: Optional. If True, will perform a hybrid search
                    using both the knn query and a text query.
                    Defaults to False.
            rrf: Optional. rrf is Reciprocal Rank Fusion.
                 When `hybrid` is True,
                    and `rrf` is True, then rrf: {}.
                    and `rrf` is False, then rrf is omitted.
                    and isinstance(rrf, dict) is True, then pass in the dict values.
                 rrf could be passed for adjusting 'rank_constant' and 'window_size'.
        """
        return ApproxRetrievalStrategy(
            query_model_id=query_model_id, hybrid=hybrid, rrf=rrf
        )

    @staticmethod
    def SparseVectorRetrievalStrategy(
        model_id: Optional[str] = None,
    ) -> "SparseRetrievalStrategy":
        """Used to perform sparse vector search via text_expansion.
        Used for when you want to use ELSER model to perform document search.

        At build index time, this strategy will create a pipeline that
        will embed the text using the ELSER model and store the
        resulting tokens in the index.

        At query time, the text will be embedded using the ELSER
        model and the resulting tokens will be used to
        perform a text_expansion query.

        Args:
            model_id: Optional. Default is ".elser_model_1".
                    ID of the model to use to embed the query text
                    within the stack. Requires embedding model to be
                    deployed to Elasticsearch.
        """
        return SparseRetrievalStrategy(model_id=model_id)

    @staticmethod
    def BM25RetrievalStrategy(
        k1: Union[float, None] = None, b: Union[float, None] = None
    ) -> "BM25RetrievalStrategy":
        """Used to apply BM25 without vector search.

        Args:
            k1: Optional. This corresponds to the BM25 parameter, k1. Default is None,
                which uses the default setting of Elasticsearch.
            b: Optional. This corresponds to the BM25 parameter, b. Default is None,
               which uses the default setting of Elasticsearch.
        """
        return BM25RetrievalStrategy(k1=k1, b=b)

