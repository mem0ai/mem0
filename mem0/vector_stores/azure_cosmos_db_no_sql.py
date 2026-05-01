"""Vector Store for CosmosDB NoSql."""
import re
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# A filter key is a dot-separated chain of identifiers, e.g. "user_id" or
# "metadata.category". We refuse anything else so that callers cannot smuggle
# SQL fragments through the filter dict (the values are always parameterized,
# but the keys are interpolated into the SQL text).
_FILTER_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")

try:
    from azure.cosmos import CosmosClient, DatabaseProxy, ContainerProxy, CosmosDict
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
except ImportError as e:
    raise ImportError(
        "The 'azure-cosmos' library is required. Install it with: pip install azure-cosmos"
    ) from e

class Constants:
    # User-agent suffix to pass when constructing CosmosClient:
    #   CosmosClient(url, credential, user_agent_suffix=Constants.USER_AGENT)
    USER_AGENT = "Mem0-CDBNoSql-VectorStore-Python"

    # All Search Types
    VECTOR = "vector"
    VECTOR_SCORE_THRESHOLD = "vector_score_threshold"
    FULL_TEXT_SEARCH = "full_text_search"
    FULL_TEXT_RANKING = "full_text_ranking"
    HYBRID = "hybrid"
    HYBRID_SCORE_THRESHOLD = "hybrid_score_threshold"

    # Default Database & Container Names
    VECTOR_SEARCH_DB = "vectorSearchDB"
    VECTOR_SEARCH_CONTAINER = "vectorSearchContainer"

    # Cosmos Database & Container Properties Keys
    OFFER_THROUGHPUT = "offer_throughput"
    SESSION_TOKEN = "session_token"
    INITIAL_HEADERS = "initial_headers"
    ETAG = "etag"
    MATCH_CONDITION = "matchCondition"
    PARTITION_KEY = "partition_key"
    DEFAULT_TTL = "default_ttl"
    UNIQUE_KEY_POLICY = "unique_key_policy"
    CONFLICT_RESOLUTION_POLICY = "conflict_resolution_policy"
    ANALYTICAL_STORAGE_TTL = "analytical_storage_ttl"
    COMPUTED_PROPERTIES = "computed_properties"

    # Vector Search Fields Keys
    TEXT_FIELD = "text_field"
    VECTOR_FIELD = "vector_field"

    # Field names
    ID = "id"
    DESCRIPTION = "description"
    METADATA = "metadata"

    # Cosmos DB internal system fields present on every item
    COSMOS_FIELD_RID = "_rid"
    COSMOS_FIELD_SELF = "_self"
    COSMOS_FIELD_ETAG = "_etag"
    COSMOS_FIELD_ATTACHMENTS = "_attachments"
    COSMOS_FIELD_TS = "_ts"

    # Vector Embedding Policy Keys
    VECTOR_EMBEDDINGS = "vectorEmbeddings"
    PATH = "path"
    DATA_TYPE = "dataType"
    DIMENSIONS = "dimensions"
    DISTANCE_FUNCTION = "distanceFunction"

    # Full text rank filter
    SEARCH_FIELD = "search_field"
    SEARCH_TEXT = "search_text"

    # Full text indexing policy
    FULL_TEXT_INDEXES = "fullTextIndexes"

    # Full text policy
    FULL_TEXT_PATHS = "fullTextPaths"

    # Parameter Keys
    LIMIT = "limit"
    NAME = "name"
    VALUE = "value"
    VECTOR_KEY = "vectorKey"
    WEIGHTS = "weights"
    SIMILARITY_SCORE = "SimilarityScore"
    FILTER_VALUE = "filter_value"

    # Default similarity score threshold
    DEFAULT_THRESHOLD: float = 0.5


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class Parameter:
    def __init__(self, key: str, value: Any) -> None:
        self.key = key
        self.value = value


class ParamMapping:
    def __init__(
        self,
        table: str,
        name_key: str = Constants.NAME,
        value_key: str = Constants.VALUE,
    ) -> None:
        self.table = table
        self.name_key = name_key
        self.value_key = value_key
        self.parameter_map: Dict[str, Parameter] = {}

    def add_parameter(self, key: str, value: Any) -> None:
        param_key = f"@{key}"
        self.parameter_map[key] = Parameter(key=param_key, value=value)

    def gen_proj_field(self, key: str, value: Any, alias: Optional[str] = None) -> str:
        if key not in self.parameter_map:
            self.add_parameter(key, value)
        projection = f"{self.table}[{self.parameter_map[key].key}]"
        if alias:
            projection += f" as {alias}"
        return projection

    def gen_param_key(self, key: str, value: Any) -> str:
        if key not in self.parameter_map:
            self.add_parameter(key, value)
        return self.parameter_map[key].key

    def gen_vector_distance_proj_field(
        self,
        vector_field: str,
        vector: Any,
        alias: Optional[str] = None,
    ) -> str:
        vector_key = self.gen_param_key(key=Constants.VECTOR_KEY, value=vector_field)
        vector_param_key = self.gen_param_key(key=Constants.VECTOR, value=vector)
        projection = f"VectorDistance({self.table}[{vector_key}], {vector_param_key})"
        if alias:
            projection += f" as {alias}"
        return projection

    def export_parameter_list(self) -> List[Dict[str, Any]]:
        return [
            {self.name_key: param.key, self.value_key: param.value}
            for param in self.parameter_map.values()
        ]


class AzureCosmosDBNoSql(VectorStoreBase):
    """Azure Cosmos DB NoSQL backed Vector Store.

    Provides CRUD operations plus similarity / hybrid search leveraging Cosmos DB
    vector and full text capabilities.
    """

    VALID_SEARCH_TYPES = (
        Constants.VECTOR,
        Constants.VECTOR_SCORE_THRESHOLD,
        Constants.FULL_TEXT_SEARCH,
        Constants.FULL_TEXT_RANKING,
        Constants.HYBRID,
        Constants.HYBRID_SCORE_THRESHOLD,
    )

    def _validate_vector_id(self, vector_id: str) -> None:
        """Raise ValueError if vector_id is falsy."""
        if not vector_id:
            raise ValueError("vector_id cannot be null or empty.")

    def _resolve_partition_key(self, vector_id: str, partition_key_value: Optional[str]) -> str:
        """Return partition_key_value, defaulting to vector_id when not supplied."""
        return partition_key_value if partition_key_value is not None else vector_id

    def __init__(
        self,
        *,
        cosmos_client: CosmosClient,
        vector_properties: Dict[str, Any],
        vector_search_fields: Dict[str, Any],
        indexing_policy: Optional[Dict[str, Any]] = None,
        cosmos_database_properties: Optional[Dict[str, Any]] = None,
        cosmos_collection_properties: Optional[Dict[str, Any]] = None,
        database_name: str = Constants.VECTOR_SEARCH_DB,
        collection_name: str = Constants.VECTOR_SEARCH_CONTAINER,
        search_type: str = Constants.VECTOR,
        metadata_key: str = Constants.METADATA,
        create_collection: bool = True,
        table_alias: str = "c",
        full_text_policy: Optional[Dict[str, Any]] = None,
        full_text_search_enabled: bool = False,
    ) -> None:
        """
        Initialize the AzureCosmosDBNoSql vector store.

        Required args:
            cosmos_client: Client used to connect to azure cosmosdb no sql account.
                It is recommended to pass ``user_agent_suffix=Constants.USER_AGENT`` when
                constructing the client so that requests are identifiable in diagnostics:
                ``CosmosClient(url, credential, user_agent_suffix=Constants.USER_AGENT)``.
            vector_properties: Vector embedding properties for the collection. Must contain
                'path', 'dataType', 'dimensions', and 'distanceFunction'.
            vector_search_fields: Field name mapping for search. Must contain
                'text_field' and 'vector_field'.

        Optional args:
            indexing_policy: Indexing policy for the collection. Defaults to an empty dict.
                Must include 'fullTextIndexes' when full_text_search_enabled=True.
            cosmos_database_properties: Extra properties forwarded to the
                ``create_database_if_not_exists`` call (e.g. offer_throughput, etag).
                Defaults to an empty dict.
            cosmos_collection_properties: Container properties forwarded to the
                ``create_container_if_not_exists`` call. Must include 'partition_key'
                when create_collection=True. Defaults to an empty dict.
            database_name: Name of the database. Defaults to 'vectorSearchDB'.
            collection_name: Name of the container. Defaults to 'vectorSearchContainer'.
            search_type: Default search type. Must be one of
                [vector, vector_score_threshold, full_text_search, full_text_ranking,
                hybrid, hybrid_score_threshold]. Defaults to 'vector'.
            metadata_key: Metadata field name used in the data schema. Defaults to 'metadata'.
            create_collection: Whether to create the container if it does not exist.
                Defaults to True.
            table_alias: Alias for the container in SQL queries. Defaults to 'c'.
            full_text_policy: Full-text policy for the collection. Must include 'fullTextPaths'
                when full_text_search_enabled=True. Defaults to None.
            full_text_search_enabled: Whether full-text search is enabled. Defaults to False.
        """
        self._cosmos_client: CosmosClient = cosmos_client
        self._vector_properties = vector_properties
        self._indexing_policy = indexing_policy or {}
        self._cosmos_collection_properties = cosmos_collection_properties or {}
        self._cosmos_database_properties = cosmos_database_properties or {}
        self._database_name = database_name
        self._collection_name = collection_name
        self._search_type = search_type
        self._metadata_key = metadata_key
        self._create_collection = create_collection
        self._table_alias = table_alias
        self._full_text_policy = full_text_policy
        self._full_text_search_enabled = full_text_search_enabled
        self._text_key = vector_search_fields.get(Constants.TEXT_FIELD) if vector_search_fields else None
        self._vector_key = vector_search_fields.get(Constants.VECTOR_FIELD) if vector_search_fields else None
        # Built once — _vector_key never changes after __init__.
        self._excluded_payload_fields: frozenset = frozenset({
            Constants.COSMOS_FIELD_RID,
            Constants.COSMOS_FIELD_SELF,
            Constants.COSMOS_FIELD_ETAG,
            Constants.COSMOS_FIELD_ATTACHMENTS,
            Constants.COSMOS_FIELD_TS,
            Constants.ID,
            Constants.SIMILARITY_SCORE,
            self._vector_key,
        })

        # Validate all init parameters
        self._validate_init_params(vector_search_fields=vector_search_fields)

        # Create (or ensure) the database exists
        self._database: DatabaseProxy = self._cosmos_client.create_database_if_not_exists(
            id=database_name,
            offer_throughput=self._cosmos_database_properties.get(Constants.OFFER_THROUGHPUT),
            session_token=self._cosmos_database_properties.get(Constants.SESSION_TOKEN),
            initial_headers=self._cosmos_database_properties.get(Constants.INITIAL_HEADERS),
            etag=self._cosmos_database_properties.get(Constants.ETAG),
            match_condition=self._cosmos_database_properties.get(Constants.MATCH_CONDITION),
        )

        # If create_collection is True, create the collection
        if self._create_collection:
            self._collection: ContainerProxy = \
                self.create_col(
                    name=self._collection_name,
                    vector_size=self._vector_properties[Constants.DIMENSIONS],
                    distance=self._vector_properties[Constants.DISTANCE_FUNCTION])
        else:
            self._collection: ContainerProxy  = self._database.get_container_client(container=self._collection_name)

    def _validate_init_params(
        self,
        vector_search_fields: Optional[Dict[str, Any]],
    ) -> None:
        """
        Validate all parameters supplied to ``__init__``.

        Raises:
            ValueError: When a required parameter is missing, empty, or an
                incompatible combination of parameters is detected.
        """
        # --- cosmos_client ---
        if self._cosmos_client is None:
            raise ValueError("'cosmos_client' is required and cannot be None.")

        # --- vector_properties ---
        if not self._vector_properties:
            raise ValueError("'vector_properties' is required and cannot be empty.")
        required_vector_keys = (
            Constants.PATH,
            Constants.DATA_TYPE,
            Constants.DIMENSIONS,
            Constants.DISTANCE_FUNCTION,
        )
        missing = [k for k in required_vector_keys if self._vector_properties.get(k) is None]
        if missing:
            raise ValueError(
                f"'vector_properties' is missing required key(s): {', '.join(missing)}. "
                f"Expected keys: {', '.join(required_vector_keys)}."
            )
        if not isinstance(self._vector_properties[Constants.DIMENSIONS], int) or \
                self._vector_properties[Constants.DIMENSIONS] <= 0:
            raise ValueError(
                f"'vector_properties[\"{Constants.DIMENSIONS}\"]' must be a positive integer."
            )

        # --- vector_search_fields ---
        if not vector_search_fields:
            raise ValueError(
                "'vector_search_fields' is required and cannot be empty. "
                f"It must contain '{Constants.TEXT_FIELD}' and '{Constants.VECTOR_FIELD}'."
            )
        if not vector_search_fields.get(Constants.TEXT_FIELD):
            raise ValueError(
                f"'vector_search_fields[\"{Constants.TEXT_FIELD}\"]' is required and cannot be empty."
            )
        if not vector_search_fields.get(Constants.VECTOR_FIELD):
            raise ValueError(
                f"'vector_search_fields[\"{Constants.VECTOR_FIELD}\"]' is required and cannot be empty."
            )

        # --- database_name / collection_name ---
        if not self._database_name or not self._database_name.strip():
            raise ValueError("'database_name' is required and cannot be empty.")
        if not self._collection_name or not self._collection_name.strip():
            raise ValueError("'collection_name' is required and cannot be empty.")

        # --- search_type ---
        if self._search_type not in self.VALID_SEARCH_TYPES:
            valid_options = ", ".join(self.VALID_SEARCH_TYPES)
            raise ValueError(
                f"Invalid 'search_type' '{self._search_type}'. "
                f"Valid options are: {valid_options}."
            )

        # --- metadata_key ---
        if not self._metadata_key or not self._metadata_key.strip():
            raise ValueError("'metadata_key' is required and cannot be empty.")

        # --- table_alias ---
        if not self._table_alias or not self._table_alias.strip():
            raise ValueError("'table_alias' is required and cannot be empty.")

        # --- full_text_search cross-field constraints ---
        if self._full_text_search_enabled:
            if self._search_type not in (
                Constants.FULL_TEXT_SEARCH,
                Constants.FULL_TEXT_RANKING,
                Constants.HYBRID,
                Constants.HYBRID_SCORE_THRESHOLD,
            ):
                raise ValueError(
                    f"'search_type' must be a full-text search type when 'full_text_search_enabled=True'. "
                    f"Got '{self._search_type}'."
                )
            if not (self._full_text_policy and self._full_text_policy.get(Constants.FULL_TEXT_PATHS)):
                raise ValueError(
                    f"'full_text_policy' with '{Constants.FULL_TEXT_PATHS}' is required "
                    f"when 'full_text_search_enabled=True'."
                )
            if not self._indexing_policy.get(Constants.FULL_TEXT_INDEXES):
                raise ValueError(
                    f"'indexing_policy' must include '{Constants.FULL_TEXT_INDEXES}' "
                    f"when 'full_text_search_enabled=True'."
                )

    def _validate_create_collection(self) -> None:
        """
        Validate parameters required for creating a Cosmos DB collection.
        Called just before ``create_container_if_not_exists``.
        """
        if self._database is None:
            raise ValueError("Database must be initialized before creating a collection.")
        if not self._collection_name:
            raise ValueError("Collection name cannot be null or empty.")
        if self._cosmos_collection_properties.get(Constants.PARTITION_KEY) is None:
            raise ValueError(
                f"'cosmos_collection_properties[\"{Constants.PARTITION_KEY}\"]' is required "
                f"and cannot be None when creating a collection."
            )

    def _create_vector_embedding_policy(
            self,
            path: str,
            data_type: str,
            dimensions: int,
            distance_function: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Create vector embedding policy dictionary."""
        return {
            Constants.VECTOR_EMBEDDINGS: [
                {
                    Constants.PATH: path,
                    Constants.DATA_TYPE: data_type,
                    Constants.DIMENSIONS: dimensions,
                    Constants.DISTANCE_FUNCTION: distance_function,
                }
            ]
        }

    def create_col(
            self,
            name: str,
            vector_size: int,
            distance: str,
    ) -> ContainerProxy:
        """Create (or ensure) the Cosmos DB collection exists.

        Args:
            name: Name of the collection to be created.
            vector_size: Dimension of the vectors.
            distance: Distance function to use for vector similarity.
        """
        self._validate_create_collection()

        # Create vector embedding policy
        vector_embedding_policy = self._create_vector_embedding_policy(
            path = self._vector_properties[Constants.PATH],
            data_type = self._vector_properties[Constants.DATA_TYPE],
            dimensions = vector_size,
            distance_function = distance,
        )

        return self._database.create_container_if_not_exists(
            id=name,
            partition_key=self._cosmos_collection_properties[Constants.PARTITION_KEY],
            indexing_policy=self._indexing_policy,
            default_ttl=self._cosmos_collection_properties.get(Constants.DEFAULT_TTL),
            offer_throughput=self._cosmos_collection_properties.get(Constants.OFFER_THROUGHPUT),
            unique_key_policy=self._cosmos_collection_properties.get(Constants.UNIQUE_KEY_POLICY),
            conflict_resolution_policy=self._cosmos_collection_properties.get(Constants.CONFLICT_RESOLUTION_POLICY),
            analytical_storage_ttl=self._cosmos_collection_properties.get(Constants.ANALYTICAL_STORAGE_TTL),
            computed_properties=self._cosmos_collection_properties.get(Constants.COMPUTED_PROPERTIES),
            etag=self._cosmos_collection_properties.get(Constants.ETAG),
            match_condition=self._cosmos_collection_properties.get(Constants.MATCH_CONDITION),
            session_token=self._cosmos_collection_properties.get(Constants.SESSION_TOKEN),
            initial_headers=self._cosmos_collection_properties.get(Constants.INITIAL_HEADERS),
            vector_embedding_policy=vector_embedding_policy,
            full_text_policy=self._full_text_policy,
        )

    def _create_item_to_insert(self, vector: List[float], payload: Optional[Dict], id: str) -> Dict[str, Any]:
        payload = payload or {}
        item = dict(payload)
        item[Constants.ID] = id
        item[self._vector_key] = vector
        return item

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """
        Insert Items into the Cosmos DB collection.

        Args:
            vectors: List of vectors to insert.
            payloads: Optional list of payloads associated with each vector.
            ids: Optional list of unique IDs for each vector.
        """
        if payloads is None:
            payloads = [{} for _ in vectors]
        if len(vectors) != len(payloads):
            raise ValueError("Length of vectors and payloads must match.")
        if ids and len(ids) != len(vectors):
            raise ValueError("Length of ids must match vectors length.")
        # If ids not provided, generate UUIDs
        _ids = ids or [str(uuid.uuid4()) for _ in vectors]

        # Insert each item into the collection
        for emb, pl, vid in zip(vectors, payloads, _ids):
            item = self._create_item_to_insert(emb, pl, vid)
            self._collection.create_item(item)

    def search(
        self,
        query: Optional[str] = None,
        vectors: Optional[List[float]] = None,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        search_type: Optional[str] = None,
        return_with_vectors: bool = False,
        offset_limit: Optional[str] = None,
        full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
        projection_mapping: Optional[Dict[str, Any]] = None,
        where: Optional[str] = None,
        weights: Optional[List[float]] = None,
        threshold: Optional[float] = Constants.DEFAULT_THRESHOLD,
    ) -> List[OutputData]:
        """
        Search for similar items in the Cosmos DB collection.

        Args:
            query: Text query used for full-text ranking search types. When the store is
                configured with a full-text or hybrid search_type and no
                ``full_text_rank_filter`` is provided, ``query`` is automatically mapped to
                ``[{"search_field": <text_field>, "search_text": query}]``. This allows
                mem0's standard ``Memory.search(query=...)`` API to work end-to-end without
                extra parameters.
            vectors: The vector embedding to run vector search. This is a single vector embedding.
            limit: The number of top similar items to retrieve.
            filters: Optional dict of exact-match filters to apply, e.g. {"metadata.a": 1, "id": "vec1"}.
                Each key-value pair is translated into a parameterized equality condition and combined
                with AND. When both 'filters' and 'where' are provided, the two conditions are merged
                into a single WHERE clause using AND.
            search_type: The type of search to perform. Valid options are:
                [vector, vector_score_threshold, full_text_search, full_text_ranking, hybrid, hybrid_score_threshold].
                Defaults to the instance-level search_type set at construction time.
            return_with_vectors: Set to True to include vector embeddings in the search results.
                Only applicable for vector and hybrid search types.
            offset_limit: Optional OFFSET and LIMIT clause for pagination.
            full_text_rank_filter: Optional list of full text rank filters.
                Each filter is a dict with 'search_field' and 'search_text' keys,
                such as {"search_field": "description", "search_text": "the fastest dog"}.
                When omitted but 'query' is provided, it is auto-built from 'query' and the
                configured 'text_field'.
            projection_mapping: Optional mapping for projecting specific fields.
            where: Optional raw WHERE clause expression for filtering results. This allows flexible
                filtering and is required for 'full_text_search' type,
                e.g. "FullTextContains(c.description, 'energetic')". When both 'where' and
                'filters' are provided, the two conditions are combined with AND (the raw
                'where' fragment is wrapped in parentheses to preserve precedence).
                SECURITY: this argument is interpolated verbatim into the SQL text. Never pass
                untrusted / user-supplied input here — use the structured 'filters' dict for
                anything that originates from end-user data.
            weights: Optional weights for hybrid search ranking.
            threshold: Similarity score threshold for filtering results.
        """
        # Fall back to the instance-level default when the caller omits search_type
        search_type = search_type or self._search_type

        # Auto-build full_text_rank_filter from `query` when using a text-ranking search type.
        # This lets mem0's standard Memory.search(query=...) work end-to-end without callers
        # having to construct full_text_rank_filter manually.
        if (
            full_text_rank_filter is None
            and query
            and self._text_key
            and self._is_full_text_search_type(search_type)
        ):
            full_text_rank_filter = [{"search_field": self._text_key, "search_text": query}]

        # Validate & build sql_query
        self._validate_search_args(
            search_type=search_type,
            vector=vectors,
            return_with_vectors=return_with_vectors,
            full_text_rank_filter=full_text_rank_filter,
        )
        sql_query, parameters = self._construct_query(
            limit=limit,
            search_type=search_type,
            vector=vectors,
            filters=filters,
            full_text_rank_filter=full_text_rank_filter,
            offset_limit=offset_limit,
            projection_mapping=projection_mapping,
            return_with_vectors=return_with_vectors,
            where=where,
            weights=weights,
        )
        return self._execute_query(
            query=sql_query,
            search_type=search_type,
            parameters=parameters,
            return_with_vectors=return_with_vectors,
            projection_mapping=projection_mapping,
            threshold=threshold,
        )

    def _validate_search_args(
        self,
        search_type: str,
        vector: Optional[List[float]] = None,
        return_with_vectors: bool = False,
        full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
    ):
        # Validate search_type
        if search_type not in self.VALID_SEARCH_TYPES:
            valid_options = ', '.join(self.VALID_SEARCH_TYPES)
            raise ValueError(
                f"Invalid search_type '{search_type}'. "
                f"Valid options are: {valid_options}."
            )

        if (
            self._full_text_search_enabled is False
            and self._is_full_text_search_type(search_type)
        ):
            raise ValueError(
                f"Full text search is not enabled for this collection, "
                f"cannot perform search_type '{search_type}'."
            )

        # full_text_rank_filter is required for text-ranking search types.
        # Note: search() auto-builds this from `query` before calling here,
        # so this error is only raised when neither query nor full_text_rank_filter is provided.
        if search_type in (
            Constants.FULL_TEXT_RANKING,
            Constants.HYBRID,
            Constants.HYBRID_SCORE_THRESHOLD,
        ) and not full_text_rank_filter:
            raise ValueError(
                f"'full_text_rank_filter' is required for search_type '{search_type}'. "
                f"Provide 'full_text_rank_filter' explicitly, or pass a 'query' string to "
                f"auto-generate it from the configured '{Constants.TEXT_FIELD}'."
            )

        # Validate vector and return_with_vectors
        if self._is_vector_search_type(search_type):
            if vector is None:
                raise ValueError(
                    f"Embedding must be provided for search_type '{search_type}'."
                )
        else:
            if return_with_vectors:
                raise ValueError(
                    "'return_with_vectors' can only be True for vector or hybrid search types "
                    "(those that compute a VectorDistance projection). Full-text-only modes do "
                    "not project the embedding."
                )

    def _is_vector_search_with_threshold(self, search_type: str) -> bool:
        """
        Check if the search type requires vector search with score threshold.

        Args:
            search_type (str): The type of search.
        """
        return search_type in (
            Constants.VECTOR_SCORE_THRESHOLD,
            Constants.HYBRID_SCORE_THRESHOLD,
        )

    def _is_full_text_search_type(self, search_type: str) -> bool:
        """
        Check if the search type is a full text search type.

        Args:
            search_type (str): The type of search.
        """
        return search_type in (
            Constants.FULL_TEXT_SEARCH,
            Constants.FULL_TEXT_RANKING,
            Constants.HYBRID,
            Constants.HYBRID_SCORE_THRESHOLD,
        )

    def _is_vector_search_type(self, search_type: str) -> bool:
        """
        Check if the search type requires vector search with vector embeddings.

        Args:
            search_type (str): The type of search.
        """
        return search_type in (
            Constants.VECTOR,
            Constants.VECTOR_SCORE_THRESHOLD,
            Constants.HYBRID,
            Constants.HYBRID_SCORE_THRESHOLD,
        )

    def _is_hybrid_search_type(self, search_type: str) -> bool:
        """
        Check if the search type is a hybrid search type (combines vector and full-text).

        Args:
            search_type (str): The type of search.
        """
        return search_type in (
            Constants.HYBRID,
            Constants.HYBRID_SCORE_THRESHOLD,
        )

    def _generate_projection_fields(
        self,
        search_type: str,
        param_mapping: ParamMapping,
        projection_mapping: Optional[Dict[str, Any]] = None,
        vector: Optional[List[float]] = None,
        full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        if projection_mapping:
            projection_fields = [f"{self._table_alias}.{key} as {alias}" for key, alias in projection_mapping.items()]
        else:
            # Use SELECT * so that all payload fields (data, hash, user_id, etc.) are
            # returned rather than only the fields known at query-build time.
            projection_fields = ["*"]

        # For vector search types, append the VectorDistance score projection.
        # SELECT * already includes the raw vector field; return_with_vectors is
        # handled downstream in _build_output_data_from_item.
        if self._is_vector_search_type(search_type):
            projection_fields.append(
                param_mapping.gen_vector_distance_proj_field(
                    vector_field=self._vector_key,
                    vector=vector,
                    alias=Constants.SIMILARITY_SCORE,
                )
            )
        return f" {', '.join(projection_fields)}"

    def _generate_limit_clause(self, param_mapping: ParamMapping, limit: int) -> str:
        limit_key = param_mapping.gen_param_key(key=Constants.LIMIT, value=limit)
        return f" TOP {limit_key}"

    def _generate_where_clause(
            self,
            param_mapping: ParamMapping,
            filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        where_clauses = []
        if filters:
            for idx, (key, value) in enumerate(filters.items()):
                # Filter keys are interpolated into the SQL text (only values
                # are parameterized via ParamMapping). Reject anything that is
                # not a dot-separated identifier chain so a caller cannot
                # smuggle SQL fragments through filters={"user_id OR 1=1 --": ...}.
                if not isinstance(key, str) or not _FILTER_KEY_RE.match(key):
                    raise ValueError(
                        f"Invalid filter key {key!r}. Filter keys must be a "
                        f"dot-separated chain of identifiers (e.g. 'user_id' "
                        f"or 'metadata.category')."
                    )
                filter_key = f"{self._table_alias}.{key}"
                filter_value = param_mapping.gen_param_key(key=f"{Constants.FILTER_VALUE}_{idx}", value=value)
                where_clauses.append(f"{filter_key}={filter_value}")
        return f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    def _generate_order_by_component_with_full_text_rank_filter(
        self,
        param_mapping: ParamMapping,
        full_text_rank_filter: Dict[str, str],
    ) -> str:
        search_field = full_text_rank_filter[Constants.SEARCH_FIELD]
        search_proj_field = param_mapping.gen_proj_field(key=search_field, value=search_field)
        search_text = full_text_rank_filter[Constants.SEARCH_TEXT]
        stripped_text = search_text.strip() if search_text else ""
        if not stripped_text:
            raise ValueError(
                f"'search_text' in full_text_rank_filter cannot be empty for field '{search_field}'."
            )
        terms = [
            param_mapping.gen_param_key(key=f"{search_field}_term_{i}", value=term)
            for i, term in enumerate(stripped_text.split())
        ]
        return f"FullTextScore({search_proj_field}, {', '.join(terms)})"

    def _generate_order_by_clause(
        self,
        search_type: str,
        param_mapping: ParamMapping,
        vector: Optional[List[float]] = None,
        weights: Optional[List[float]] = None,
        full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        order_by_clause = ""
        if search_type in (Constants.VECTOR, Constants.VECTOR_SCORE_THRESHOLD):
            vector_distance_proj_field = param_mapping.gen_vector_distance_proj_field(
                vector_field=self._vector_key, vector=vector
            )
            order_by_clause = f"ORDER BY {vector_distance_proj_field}"
        elif search_type in (
            Constants.FULL_TEXT_RANKING,
            Constants.HYBRID,
            Constants.HYBRID_SCORE_THRESHOLD,
        ):
            components = [
                self._generate_order_by_component_with_full_text_rank_filter(
                    param_mapping=param_mapping, full_text_rank_filter=item
                )
                for item in full_text_rank_filter
            ]
            if self._is_hybrid_search_type(search_type):
                components.append(
                    param_mapping.gen_vector_distance_proj_field(
                        vector_field=self._vector_key, vector=vector
                    )
                )
                if weights:
                    components.append(param_mapping.gen_param_key(key=Constants.WEIGHTS, value=weights))
            order_by_clause = (
                f"ORDER BY RANK {components[0]}" if len(components) == 1 else f"ORDER BY RANK RRF({', '.join(components)})"
            )
        return f" {order_by_clause}"

    def _construct_query(
        self,
        limit: int,
        search_type: str,
        vector: Optional[List[float]] = None,
        filters: Optional[Dict[str, Any]] = None,
        full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
        offset_limit: Optional[str] = None,
        projection_mapping: Optional[Dict[str, Any]] = None,
        return_with_vectors: bool = False,
        where: Optional[str] = None,
        weights: Optional[List[float]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        query = "SELECT"
        param_mapping = ParamMapping(table=self._table_alias)
        if not offset_limit:
            query += self._generate_limit_clause(param_mapping=param_mapping, limit=limit)

        query += self._generate_projection_fields(
            search_type=search_type,
            param_mapping=param_mapping,
            projection_mapping=projection_mapping,
            vector=vector,
            full_text_rank_filter=full_text_rank_filter,
        )

        query += f" FROM {self._table_alias}"

        # Build WHERE clause by merging `filters` dict and raw `where` string with AND.
        # `where` is wrapped in parentheses so that an OR inside the raw fragment
        # cannot bind looser than the AND that joins it to the structured filters
        # (otherwise `WHERE c.user_id=@v0 AND x=1 OR y=2` would parse as
        # `(c.user_id=@v0 AND x=1) OR y=2` and leak rows across tenants).
        filters_clause = self._generate_where_clause(param_mapping=param_mapping, filters=filters)
        if filters_clause and where:
            query += filters_clause + f" AND ({where})"
        elif filters_clause:
            query += filters_clause
        elif where:
            query += f" WHERE ({where})"

        if search_type != Constants.FULL_TEXT_SEARCH:
            order_by_clause = self._generate_order_by_clause(
                search_type=search_type,
                param_mapping=param_mapping,
                vector=vector,
                weights=weights,
                full_text_rank_filter=full_text_rank_filter,
            )
            query += order_by_clause

        if offset_limit:
            query += f" {offset_limit}"

        parameters = param_mapping.export_parameter_list()
        return query, parameters

    def _execute_query(
        self,
        query: str,
        search_type: Optional[str] = None,
        parameters: Optional[List[Dict[str, Any]]] = None,
        return_with_vectors: bool = False,
        projection_mapping: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = Constants.DEFAULT_THRESHOLD,
    ) -> List[OutputData]:
        parameters = parameters if parameters else []

        # Execute the query
        items = self._collection.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )

        # Filter items if it was threshold-based search
        if self._is_vector_search_with_threshold(search_type):
            threshold = threshold or 0.0
            filtered_items = [item for item in items if item.get(Constants.SIMILARITY_SCORE, 0.0) >= threshold]
        else:
            filtered_items = items

        # Build OutputData results
        results: List[OutputData] = []
        for item in filtered_items:
            output_data = self._build_output_data_from_item(
                item=item,
                return_with_vectors=return_with_vectors,
                projection_mapping=projection_mapping,
            )
            results.append(output_data)
        return results

    def _build_output_data_from_item(
        self,
        item: Dict[str, Any],
        return_with_vectors: Optional[bool] = True,
        projection_mapping: Optional[Dict[str, Any]] = None,
    ) -> OutputData:
        item_id = str(item.get(Constants.ID))
        score = item.get(Constants.SIMILARITY_SCORE, 0.0)

        # Build payload based on projection mapping
        if projection_mapping:
            payload = {alias: item.get(alias) for alias in projection_mapping.values()}
        else:
            # Exclude:
            #   - Cosmos DB internal fields (_rid, _self, _etag, _attachments, _ts)
            #   - Fields surfaced separately on OutputData: id, SimilarityScore
            #   - The vector field — re-added below only when return_with_vectors=True
            excluded = self._excluded_payload_fields
            payload = {k: v for k, v in item.items() if k not in excluded}

        # Include vector in payload if requested
        if return_with_vectors:
            payload[self._vector_key] = item.get(self._vector_key)

        return OutputData(id=item_id, score=score, payload=payload)

    def delete(
            self,
            vector_id: str,
            partition_key_value: Optional[str] = None
    ) -> None:
        """
        Delete an item from the Cosmos DB collection by ID.

        Args:
            vector_id: The unique ID of the item to delete.
            partition_key_value: The partition key value for the item. If not provided, defaults to vector_id.
        """
        self._validate_vector_id(vector_id)
        partition_key_value = self._resolve_partition_key(vector_id, partition_key_value)
        try:
            self._collection.delete_item(
                item=vector_id,
                partition_key=partition_key_value,
            )
            logger.info("Deleted document with ID '%s'.", vector_id)
        except CosmosResourceNotFoundError:
            logger.warning(
                "delete: document with ID '%s' was not found — treating as a no-op.",
                vector_id,
            )

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
        partition_key_value: Optional[str] = None,
    ) -> None:
        """
        Update an item in the Cosmos DB collection.

        Args:
            vector_id: The unique ID of the item to update.
            vector: The new vector embedding to update.
            payload: The new payload to update.
            partition_key_value: The partition key value for the item. If not provided, defaults to vector_id.
        """
        self._validate_vector_id(vector_id)
        partition_key_value = self._resolve_partition_key(vector_id, partition_key_value)

        # Retrieve existing item to merge data if needed
        try:
            existing: CosmosDict = self._collection.read_item(
                item=vector_id,
                partition_key=partition_key_value,
            )
        except CosmosResourceNotFoundError:
            raise ValueError(f"Cannot update: item '{vector_id}' not found.")

        # Merge existing data when partial update
        if vector is None:
            vector = existing.get(self._vector_key)
        if payload is None:
            # Preserve all application fields from the existing item so that
            # custom fields are not silently dropped on a partial update.
            # Exclude Cosmos DB internals, fields surfaced separately on OutputData,
            # and the vector field (handled via the `vector` parameter).
            excluded = self._excluded_payload_fields
            payload = {k: v for k, v in existing.items() if k not in excluded}
        item = self._create_item_to_insert(vector=vector, payload=payload, id=vector_id)
        self._collection.upsert_item(body=item)

    def get(
            self,
            vector_id: str,
            partition_key_value: Optional[str] = None,
            return_with_vectors: Optional[bool] = True,
    ) -> Optional[OutputData]:
        """
        Retrieve an item from the Cosmos DB collection by ID.

        Args:
            vector_id: The unique ID of the item to retrieve.
            partition_key_value: The partition key value for the item. If not provided, defaults to vector_id.
            return_with_vectors: Whether to include the vector embeddings in the result.
        """
        self._validate_vector_id(vector_id)
        partition_key_value = self._resolve_partition_key(vector_id, partition_key_value)

        # Retrieve the item
        try:
            item = self._collection.read_item(
                item=vector_id,
                partition_key=partition_key_value,
            )
        except CosmosResourceNotFoundError:
            return None

        return self._build_output_data_from_item(
            item=item,
            return_with_vectors=return_with_vectors,
        )

    def list_cols(self) -> List[str]:
        """
        List all collections in the database.
        """
        return [col[Constants.ID] for col in self._database.list_containers()]

    def delete_col(self) -> None:
        """
        Delete the Cosmos DB collection.
        """
        self._database.delete_container(container=self._collection_name)
        logger.info("Deleted collection '%s'.", self._collection_name)

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about the Cosmos DB collection.
        """
        return self._collection.read()

    def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> Tuple[List[OutputData], None]:
        """List items in the collection.

        Returns a ``(records, None)`` tuple consistent with other mem0 vector stores
        (e.g. Qdrant's ``scroll()`` returns ``(records, offset)``). The second element
        is always ``None`` — it exists so that ``Memory.delete_all()`` can do
        ``list(...)[0]`` to get the list of records.

        Args:
            filters: Optional filters to apply. Example: {"metadata.a": 1}
            limit: Maximum number of items to retrieve. Default is 100.
        """
        param_mapping = ParamMapping(table=self._table_alias)

        # Build query
        # Syntax : SELECT <limit_clause> * FROM c WHERE <where_clause>
        # Example: SELECT TOP @limit * FROM c WHERE c.metadata.a=@filter_value_0
        query = "SELECT"
        query += self._generate_limit_clause(param_mapping=param_mapping, limit=limit)
        query += f" * FROM {self._table_alias}"
        query += self._generate_where_clause(param_mapping=param_mapping, filters=filters)

        parameters = param_mapping.export_parameter_list()
        results = self._execute_query(query=query, parameters=parameters, return_with_vectors=False)
        return results, None

    def reset(self) -> None:
        """
        Reset the collection by deleting and recreating it.
        """
        self.delete_col()
        self._collection = self.create_col(
            name=self._collection_name,
            vector_size=self._vector_properties[Constants.DIMENSIONS],
            distance=self._vector_properties[Constants.DISTANCE_FUNCTION])
