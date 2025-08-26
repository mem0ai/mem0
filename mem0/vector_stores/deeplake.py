import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    import deeplake
except ImportError:
    raise ImportError("The 'deeplake' library is required. Please install it using 'pip install deeplake'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class DeepLake(VectorStoreBase):
    def __init__(
        self,
        url: str,
        embedding_model_dims: int,
        quantize: bool = False,
        creds: Optional[Dict] = None,
        token: Optional[str] = None,
    ):
        """
        Initialize the DeepLake vector store.

        Args:
            url (str): The URL of the DeepLake database.
            creds (Dict, optional): Credentials for the DeepLake database.
            token (str, optional): Token for the DeepLake database.
        """
        exists = deeplake.exists(url, creds=creds, token=token)

        self.url = url
        self.creds = creds
        self.token = token
        self.embedding_model_dims = embedding_model_dims
        self.quantize = quantize

        self.client = None
        
        self.create_col(embedding_model_dims)
    
    def _collection_exists(self) -> bool:
        return deeplake.exists(self.url, creds=self.creds, token=self.token)

    def create_col(self, vector_size: int, distance: str = "cosine"):
        exists = self._collection_exists()
        if exists:
            logger.debug(f"Collection {self.url} already exists. Skipping creation.")
            self.client = deeplake.open(self.url, creds=self.creds, token=self.token)
            return
        
        schema = {
            "id": deeplake.types.Text(),
            "user_id": deeplake.types.Text(),
            "run_id": deeplake.types.Text(),
            "agent_id": deeplake.types.Text(),
            "vector": deeplake.types.Embedding(self.embedding_model_dims, quantization=deeplake.types.QuantizationType.Binary if self.quantize else None),
            "payload": deeplake.types.Dict()
        }
        
        self.client = deeplake.create(self.url, creds=self.creds, token=self.token, schema=schema)
        self.client.indexing_mode = deeplake.IndexingMode.Always

    @abstractmethod
    def insert(self, vectors, payloads=None, ids=None):
        """Insert vectors into a collection."""
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.url}")
        if not ids:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        if payloads is None:
            payloads = [{} for _ in range(len(vectors))]
        
        batch_data = {
            "id": ids,
            "vector": vectors,
            "payload": payloads,
        }

        metadata = defaultdict(list)

        for payload in payloads:
            for field in ["user_id", "run_id", "agent_id"]:
                if field in payload:
                    metadata[field].append(payload[field])
                else:
                    metadata[field].append("")
        
        metadata = dict(metadata)

        batch_data.update(metadata)

        self.client.append(batch_data)

    def _sanitize_key(self, key: str) -> str:
        return re.sub(r"[^\w]", "", key)

    def _build_filter_expression(self, filters):
        filter_conditions = []
        for key, value in filters.items():
            safe_key = self._sanitize_key(key)
            if isinstance(value, str):
                safe_value = value.replace("'", "''")
                condition = f"{safe_key} = '{safe_value}'"
            else:
                condition = f"{safe_key} = {value}"
            filter_conditions.append(condition)
        filter_expression = " AND ".join(filter_conditions)
        return filter_expression

    @abstractmethod
    def search(self, query, vectors, limit=5, filters=None):
        """Search for similar vectors."""
        where_clause = ""
        if filters:
            where_clause = f"WHERE {self._build_filter_expression(filters)}"

        emb_str = ", ".join([str(v) for v in vectors])
        search_results = self.client.query(f'''
            SELECT *
            {where_clause}
            ORDER BY COSINE_SIMILARITY(vector, ARRAY[{emb_str}]) DESC
            LIMIT {limit}
        ''')

        if len(search_results) == 0:
            return []

        payloads = search_results["payload"][:]
        ids = search_results["id"][:]
        scores = search_results["score"][:]

        results = []
        for i in range(len(search_results)):
            results.append(OutputData(id=ids[i], score=scores[i], payload=payloads[i]))
        return results
        
    @abstractmethod
    def delete(self, vector_id):
        """Delete a vector by ID."""        
        query = (
            f"SELECT * FROM (SELECT *, ROW_NUMBER() as row_id) WHERE id = '{vector_id}'"
        )
        results = self.client.query(query)

        if len(results) == 0:
            logger.warning(f"Vector {vector_id} not found in collection {self.url}")
            return

        for idx in sorted(results["row_id"][:], reverse=True):
            self.client.delete(idx)
        self.client.commit()

    @abstractmethod
    def update(self, vector_id, vector=None, payload=None):
        """Update a vector and its payload."""
        query = (
            f"SELECT * FROM (SELECT *, ROW_NUMBER() as row_id) WHERE id = '{vector_id}'"
        )
        results = self.client.query(query)

        if len(results) == 0:
            logger.warning(f"Vector {vector_id} not found in collection {self.url}")
            return
        
        index = results["row_id"][0]
        if vector is not None:
            self.client[index]["vector"] = vector

        if payload is not None:
            self.client[index]["payload"] = payload

        self.client.commit()

    @abstractmethod
    def get(self, vector_id) -> Optional[OutputData]:
        """Retrieve a vector by ID."""
        query = (
            f"SELECT * FROM (SELECT *, ROW_NUMBER() as row_id) WHERE id = '{vector_id}'"
        )
        query_results = self.client.query(query)

        if len(results) == 0:
            logger.warning(f"Vector {vector_id} not found in collection {self.url}")
            return
        return OutputData(id=query_results["vector_id"][0], score=None, payload=query_results["payload"][0])
        

    @abstractmethod
    def list_cols(self):
        """List all collections."""
        pass

    @abstractmethod
    def delete_col(self):
        """Delete a collection."""
        pass

    @abstractmethod
    def col_info(self):
        """Get information about a collection."""
        pass

    @abstractmethod
    def list(self, filters=None, limit=None):
        """List all memories."""
        pass

    @abstractmethod
    def reset(self):
        """Reset by delete the collection and recreate it."""
        pass
