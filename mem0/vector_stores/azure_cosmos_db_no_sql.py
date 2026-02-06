"""Vector Store for CosmosDB NoSql."""
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

try:
    from azure.cosmos import CosmosClient, DatabaseProxy, ContainerProxy, CosmosDict
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
except ImportError as e:
    raise ImportError(
        "The 'azure-cosmos' library is required. Install it with: pip install azure-cosmos"
    ) from e

class Constants:
    # User Agent for Cosmos DB No SQL client
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
    TEXT_KEY = "textKey"
    METADATA_KEY = "metadataKey"
    WEIGHTS = "weights"
    SIMILARITY_SCORE = "SimilarityScore"
    FILTER_VALUE = "filter_value"


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class Parameter:
    def __init__(self, key: str, value: Any) -> None:
        self.key = key
        self.value = value


class ParamMapping:  # Renamed from PramMapping (typo fix)
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

    def __init__(
        self,
        *,
        cosmos_client: CosmosClient,
        indexing_policy: Dict[str, Any],
        cosmos_database_properties: Dict[str, Any],
        cosmos_collection_properties: Dict[str, Any],
        vector_properties: Dict[str, Any],
        vector_search_fields: Dict[str, Any],
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

        Args:
            cosmos_client: Client used to connect to azure cosmosdb no sql account.
            indexing_policy: Indexing Policy for the collection.
            cosmos_database_properties: Database Properties for the collection.
            cosmos_collection_properties: Container Properties for the collection.
            vector_properties: Vector Embedding Properties for the collection.
            vector_search_fields: Vector Search and Text
                                  Search Fields for the collection.
            database_name: Name of the database to be created.
            collection_name: Name of the collection to be created.
            search_type: CosmosDB Search Type to be performed.
            metadata_key: Metadata key to use for data schema.
            create_collection: Set to true if the collection does not exist.
            table_alias: Alias for the table to use in the WHERE clause.
            full_text_policy: Full Text Policy for the collection.
            full_text_search_enabled: Set to true if the full text search is enabled.
        """
        self._cosmos_client: CosmosClient = cosmos_client
        self._indexing_policy = indexing_policy
        self._cosmos_collection_properties = cosmos_collection_properties
        self._cosmos_database_properties = cosmos_database_properties
        self._vector_properties = vector_properties
        self._database_name = database_name
        self._collection_name = collection_name
        self._search_type = search_type
        self._metadata_key = metadata_key
        self._create_collection = create_collection
        self._table_alias = table_alias
        self._full_text_policy = full_text_policy
        self._full_text_search_enabled = full_text_search_enabled

        # If vector_search_fields provided, extract text and vector fields
        if vector_search_fields is None:
            raise ValueError("vector_search_fields cannot be null. It must contain 'text_field' and 'vector_field'.")
        self._text_key = vector_search_fields.get(Constants.TEXT_FIELD)
        self._vector_key = vector_search_fields.get(Constants.VECTOR_FIELD)

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

    def _validate_create_collection(self) -> None:
        """
        Validate parameters required for creating a Cosmos DB collection.
        """
        if self._database is None:
            raise ValueError("Database must be initialized before creating a collection.")
        if not self._collection_name:
            raise ValueError("Collection name cannot be null or empty.")
        if (
            not self._cosmos_collection_properties
            or self._cosmos_collection_properties.get(Constants.PARTITION_KEY) is None
        ):
            raise ValueError(f"{Constants.PARTITION_KEY} cannot be null or empty for a collection.")
        if self._full_text_search_enabled:
            if not (self._indexing_policy and self._indexing_policy.get(Constants.FULL_TEXT_INDEXES)):
                raise ValueError(
                    f"{Constants.FULL_TEXT_INDEXES} cannot be null or empty in the indexing_policy if full text search is enabled."
                )
            if not (self._full_text_policy and self._full_text_policy.get(Constants.FULL_TEXT_PATHS)):
                raise ValueError(
                    f"{Constants.FULL_TEXT_PATHS} cannot be null or empty in the full_text_policy if full text search is enabled."
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
    ) -> ContainerProxy:  # signature updated to match base, args optional
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
        return {
            Constants.ID: id,
            self._text_key: payload.get(self._text_key, ""),
            self._vector_key: vector,
            self._metadata_key: payload.get(self._metadata_key, {}),
        }

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

    def _search(
            self,
            query: str,
            vectors: Optional[List[float]] = None,
            limit: int = 5,
            filters: Optional[Dict[str, Any]] = None,

    ):
        pass

    def search(
        self,
        query: Optional[str] = None,
        vectors: Optional[List[float]] = None,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        search_type: str = Constants.VECTOR,
        return_with_vectors: bool = False,
        offset_limit: Optional[str] = None,
        full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
        projection_mapping: Optional[Dict[str, Any]] = None,
        where: Optional[str] = None,
        weights: Optional[List[float]] = None,
        threshold: Optional[float] = 0.5,
    ) -> List[OutputData]:
        """
        Search for similar items in the Cosmos DB collection.

        Args:
            query: [Not Implemented] This will be ignored in the current implementation. Vector search will be
                performed based on the 'vectors' parameter.
                If text search is needed, use 'where' or 'full_text_rank_filter' instead.
            vectors: The vector embedding to run vector search. This is a single vector embedding.
            limit: The number of top similar items to retrieve.
            filters: [Not Implemented] This will be ignored in the current implementation.
                Use 'where' parameter for filtering instead, which allows more flexible and powerful filtering,
                including full text search conditions.
            search_type: The type of search to perform. Valid options are:
                [vector, vector_score_threshold, full_text_search, full_text_ranking, hybrid, hybrid_score_threshold].
            return_with_vectors: Set to True to include vector embeddings in the search results.
                Only applicable for vector and hybrid search types.
            offset_limit: Optional OFFSET and LIMIT clause for pagination.
            full_text_rank_filter: Optional list of full text rank filters.
                Each filter is a dict with 'search_field' and 'search_text' keys,
                such as {"search_field": "description", "search_text": "the fastest dog"}.
            projection_mapping: Optional mapping for projecting specific fields.
            where: Optional WHERE clause for filtering results. This allows filter results and integrations for
                'full_text_search' type, such as "FullTextContains(c.description, 'energetic')"
            weights: Optional weights for hybrid search ranking.
            threshold: Similarity score threshold for filtering results.
        """
        # Validate & build query
        search_type = search_type or self._search_type
        self._validate_search_args(search_type=search_type, vector=vectors, return_with_vectors=return_with_vectors)
        query, parameters = self._construct_query(
            limit=limit,
            search_type=search_type,
            vector=vectors,
            full_text_rank_filter=full_text_rank_filter,
            offset_limit=offset_limit,
            projection_mapping=projection_mapping,
            return_with_vectors=return_with_vectors,
            where=where,
            weights=weights,
        )
        return self._execute_query(
            query=query,
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


        # Validate vector and return_with_vectors
        if self._is_vector_search_type(search_type):
            if vector is None:
                raise ValueError(
                    f"Embedding must be provided for search_type '{search_type}'."
                )
        else:
            if return_with_vectors:
                raise ValueError(
                    "'return_with_vectors' can only be True for vector search types using vector embeddings."
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

    def _generate_projection_fields(
        self,
        search_type: str,
        param_mapping: ParamMapping,
        projection_mapping: Optional[Dict[str, Any]] = None,
        return_with_vectors: bool = False,
        vector: Optional[List[float]] = None,
        full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        if projection_mapping:
            projection_fields = [f"{self._table_alias}.{key} as {alias}" for key, alias in projection_mapping.items()]
        elif search_type == Constants.FULL_TEXT_RANKING:
            if not full_text_rank_filter:
                raise ValueError(f"'full_text_rank_filter' required for {search_type}.")

            projection_fields = [f"{self._table_alias}.{Constants.ID} as {Constants.ID}"]
            projection_fields += [
                param_mapping.gen_proj_field(
                    key=item[Constants.SEARCH_FIELD],
                    alias=item[Constants.SEARCH_FIELD],
                    value=item[Constants.SEARCH_FIELD],
                )
                for item in full_text_rank_filter
            ]
        else:
            projection_fields = [f"{self._table_alias}.{Constants.ID} as {Constants.ID}"]
            projection_fields += [
                param_mapping.gen_proj_field(key=key, value=key, alias=key)
                for key in [self._text_key, self._metadata_key]
            ]

        # If it's a vector search type, include vector distance projection and optionally the vector itself
        if Constants.VECTOR in search_type or Constants.HYBRID in search_type:
            if return_with_vectors:
                projection_fields.append(
                    param_mapping.gen_proj_field(
                        key=Constants.VECTOR_KEY,
                        value=self._vector_key,
                        alias=Constants.VECTOR,
                    )
                )
            projection_fields.append(
                param_mapping.gen_vector_distance_proj_field(
                    vector_field=self._vector_key,
                    vector=vector,
                    alias=Constants.SIMILARITY_SCORE,
                )
            )
        return f" {", ".join(projection_fields)}"

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
            id = 0
            for key, value in filters.items():
                filter_key = f"{self._table_alias}.{key}"
                filter_value = param_mapping.gen_param_key(key=f"{Constants.FILTER_VALUE}_{id}", value=value)

                where_clauses.append(f"{filter_key}={filter_value}")
                id += 1
        return f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    def _generate_order_by_component_with_full_text_rank_filter(
        self,
        param_mapping: ParamMapping,
        full_text_rank_filter: Dict[str, str],
    ) -> str:
        search_field = full_text_rank_filter[Constants.SEARCH_FIELD]
        search_proj_field = param_mapping.gen_proj_field(key=search_field, value=search_field)
        search_text = full_text_rank_filter[Constants.SEARCH_TEXT]
        terms = [
            param_mapping.gen_param_key(key=f"{search_field}_term_{i}", value=term)
            for i, term in enumerate(search_text.split())
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
            if not full_text_rank_filter:
                raise ValueError(f"'full_text_rank_filter' required for {search_type} search.")
            components = [
                self._generate_order_by_component_with_full_text_rank_filter(
                    param_mapping=param_mapping, full_text_rank_filter=item
                )
                for item in full_text_rank_filter
            ]
            if "hybrid" in search_type:
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
            return_with_vectors=return_with_vectors,
            vector=vector,
            full_text_rank_filter=full_text_rank_filter,
        )

        query += f" FROM {self._table_alias}"

        if where:
            query += f" WHERE {where}"

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
        parameters: Optional[List[Dict[str, Any]]] =  None,
        return_with_vectors: bool = True,
        projection_mapping: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = 0.0,
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
            filtered_items = [item for item in items if item.get(Constants.SIMILARITY_SCORE, 0.0) > threshold]
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
            payload = {alias: item[alias] for alias in projection_mapping.values()}
        else:
            # If no projection mapping, include text and metadata in payload
            payload = {
                self._text_key: item.get(self._text_key, ""),
                self._metadata_key: item.get(self._metadata_key, {})
            }

        # Include vector in payload if requested
        if return_with_vectors:
            payload[self._vector_key] = item[self._vector_key]

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
        if not vector_id:
            raise ValueError("vector_id cannot be null or empty.")
        if partition_key_value is None:
            partition_key_value = vector_id
        try:
            self._collection.delete_item(
                item=vector_id,
                partition_key=partition_key_value,
            )
            logger.info("Deleted document with ID '%s'.", vector_id)
        except CosmosResourceNotFoundError as e:
            logger.error("Error deleting document: %s", e)
            raise e

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
        if not vector_id:
            raise ValueError("vector_id cannot be null or empty.")
        if partition_key_value is None:
            partition_key_value = vector_id

        # Retrieve existing item to merge data if needed
        try:
            existing: CosmosDict = self._collection.read_item(
                item=vector_id,
                partition_key=partition_key_value,
            )
        except CosmosResourceNotFoundError:
            existing = None
        if existing:
            # Merge existing data when partial update
            if vector is None:
                vector = existing.get(self._vector_key)
            if payload is None:
                payload = {
                    self._text_key: existing.get(self._text_key, ""),
                    self._metadata_key: existing.get(self._metadata_key, {})
                }
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
        if not vector_id:
            raise ValueError("vector_id cannot be null or empty.")
        if partition_key_value is None:
            partition_key_value = vector_id

        # Retrieve the item
        item = self._collection.read_item(
            item=vector_id,
            partition_key=partition_key_value,
        )

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
    ) -> List[OutputData]:
        """List items in the collection.

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
        return self._execute_query(query=query, parameters=parameters)

    def reset(self) -> None:
        """
        Reset the collection by deleting and recreating it.
        """
        collection_name = self._collection_name
        self.delete_col()
        self.create_col(
            name=self._collection_name,
            vector_size=self._vector_properties[Constants.DIMENSIONS],
            distance=self._vector_properties[Constants.DISTANCE_FUNCTION])
