"""Vector Store for CosmosDB NoSql."""
import uuid
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

from mem0.vector_stores.base import VectorStoreBase
from pydantic import BaseModel

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

try:
    from azure.cosmos import ContainerProxy, CosmosClient, DatabaseProxy, ContainerProxy
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
except ImportError:
    raise ImportError("The 'cosmos' library is required. Please install it using 'pip install cosmos'.")

class Constants:
    # User Agent for Cosmos DB No SQL client
    USER_AGENT = "LangChain-CDBNoSql-VectorStore-Python"

    # Search Types
    VECTOR: str = "vector"
    VECTOR_SCORE_THRESHOLD = "vector_score_threshold"
    FULL_TEXT_SEARCH = "full_text_search"
    FULL_TEXT_RANKING = "full_text_ranking"
    HYBRID = "hybrid"
    HYBRID_SCORE_THRESHOLD = "hybrid_score_threshold"

    SCORE_THRESHOLD = "score_threshold"

    # Vector Embedding Policy Keys
    VECTOR_INDEXES = "vectorIndexes"
    VECTOR_EMBEDDINGS = "vectorEmbeddings"
    DIMENSIONS = "dimensions"
    DISTANCE_FUNCTION = "distanceFunction"

    # Cosmos Database Properties Keys
    OFFER_THROUGHPUT = "offer_throughput"
    SESSION_TOKEN = "session_token"
    INITIAL_HEADERS = "initial_headers"
    ETAG = "etag"
    MATCH_CONDITION = "matchCondition"

    # Cosmos Container Properties Keys
    PARTITION_KEY = "partition_key"
    DEFAULT_TTL = "default_ttl"
    UNIQUE_KEY_POLICY = "unique_key_policy"
    CONFLICT_RESOLUTION_POLICY = "conflict_resolution_policy"
    ANALYTICAL_STORAGE_TTL = "analytical_storage_ttl"
    COMPUTED_PROPERTIES = "computed_properties"

    # Vector Search Fields Keys
    TEXT_FIELD = "text_field"
    EMBEDDING_FIELD = "embedding_field"

    # Field names
    ID = "id"
    DESCRIPTION = "description"
    METADATA = "metadata"

    # Parameter Keys
    LIMIT_KEY = "limit"
    NAME_KEY = "name"
    VALUE_KEY = "value"

    # Full text rank filter
    SEARCH_FIELD = "search_field"
    SEARCH_TEXT = "search_text"

    # Full text indexing policy
    FULL_TEXT_INDEXES = "fullTextIndexes"

    # Full text policy
    FULL_TEXT_PATHS = "fullTextPaths"

    # Add missing constants for keys used in the code
    EMBEDDING_KEY = "embeddingKey"
    EMBEDDINGS = "embeddings"
    VECTOR_SEARCH_DB = "vectorSearchDB"
    VECTOR_SEARCH_CONTAINER = "vectorSearchContainer"

    # Add missing constants for projection/alias keys
    TEXT_KEY = "textKey"
    METADATA_KEY = "metadataKey"
    EMBEDDING = "embedding"
    WEIGHTS = "weights"

    SIMILARITY_SCORE = "SimilarityScore"

class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class Parameter:
    def __init__(
            self,
            key: str,
            value: Any,
    ) -> None:
        self.key = key
        self.value = value


class PramMapping:
    def __init__(
            self,
            table: str,
            name_key: str = Constants.NAME_KEY,
            value_key: str = Constants.VALUE_KEY,
    ) -> None:
        self.table = table
        self.name_key = name_key
        self.value_key = value_key
        self.parameter_map: Dict[str, Parameter] = {}

    def add_parameter(self, key: str, value: Any):
        param_key = f"@{key}"
        self.parameter_map[key] = Parameter(
            key=param_key,
            value=value,
        )

    def gen_proj_field(
            self,
            key: str,
            value: Any,
            alias: Optional[str] = None,
    ) -> str:
        # Add parameter if not already present
        if key not in self.parameter_map:
            self.add_parameter(key, value)

        # Initialize projection string
        projection = f"{self.table}[{self.parameter_map[key].key}]"

        # Add alias if present
        if alias:
            projection += f" as {alias}"

        return projection

    def gen_param_key(
            self,
            key: str,
            value: Any,
    ) -> str:
        # Add parameter if not already present
        if key not in self.parameter_map:
            self.add_parameter(key, value)

        return self.parameter_map[key].key

    def gen_vector_distance_proj_field(
            self,
            embedding_field: str,
            embeddings: Any,
            alias: Optional[str] = None,
    ) -> str:
        embedding_key = self.gen_param_key(
            key=Constants.EMBEDDING_KEY,
            value=embedding_field,
        )
        embeddings_param_key = self.gen_param_key(
            key=Constants.EMBEDDINGS,
            value=embeddings,
        )
        projection = f"VectorDistance({self.table}[{embedding_key}], {embeddings_param_key})"
        if alias:
            projection += f" as {alias}"
        return projection

    def export_parameter_list(self) -> List[Dict[str, Any]]:
        return [
            {
                self.name_key: param.key,
                self.value_key: param.value,
            } for param in self.parameter_map.values()
        ]


class AzureCosmosDBNoSql(VectorStoreBase):
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
            vector_embedding_policy: Dict[str, Any],
            indexing_policy: Dict[str, Any],
            cosmos_database_properties: Dict[str, Any],
            cosmos_container_properties: Dict[str, Any],
            vector_search_fields: Dict[str, Any],
            database_name: str = Constants.VECTOR_SEARCH_DB,
            collection_name: str = Constants.VECTOR_SEARCH_CONTAINER,
            search_type: str = Constants.VECTOR,
            metadata_key: str = Constants.METADATA,
            create_container: bool = True,
            table_alias: str = "c",
            full_text_policy: Optional[Dict[str, Any]] = None,
            full_text_search_enabled: bool = False,
    ):
        self._cosmos_client: CosmosClient = cosmos_client
        self._vector_embedding_policy: Dict[str, Any] = vector_embedding_policy
        self._indexing_policy: Dict[str, Any] = indexing_policy
        self._cosmos_container_properties: Dict[str, Any] = cosmos_container_properties
        self._cosmos_database_properties: Dict[str, Any] = cosmos_database_properties
        self._vector_search_fields: Dict[str, Any] = vector_search_fields
        self._database_name: str = database_name
        self._collection_name: str = collection_name
        self._search_type: str = search_type
        self._metadata_key: str = metadata_key
        self._create_collection: bool = create_container
        self._table_alias = table_alias
        self._full_text_policy = full_text_policy
        self._full_text_search_enabled = full_text_search_enabled

        self._embedding_model_dims = self._vector_embedding_policy[Constants.VECTOR_EMBEDDINGS][0][Constants.DIMENSIONS]
        self._distance_function = self._vector_embedding_policy[Constants.VECTOR_EMBEDDINGS][0][Constants.DISTANCE_FUNCTION]

        self._database: DatabaseProxy = self._cosmos_client.create_database_if_not_exists(
            id = database_name,
            offer_throughput = self._cosmos_database_properties.get(Constants.OFFER_THROUGHPUT),
            session_token = self._cosmos_database_properties.get(Constants.SESSION_TOKEN),
            initial_headers = self._cosmos_database_properties.get(Constants.INITIAL_HEADERS),
            etag = self._cosmos_database_properties.get(Constants.ETAG),
            match_condition = self._cosmos_database_properties.get(Constants.MATCH_CONDITION),
        )
        if self._create_collection:
            self._container: ContainerProxy = self.create_col()
        else:
            self._container: ContainerProxy = self._database.get_container_client(container = self._collection_name)

    def _validate_create_container(self):
        # Validate required parameters
        if self._database is None:
            raise ValueError("Database must be initialized before creating a container.")

        if self._collection_name is None or self._collection_name == "":
            raise ValueError("Container name cannot be null or empty.")

        if (
                self._indexing_policy is None
                or Constants.VECTOR_INDEXES not in self._indexing_policy
                or self._indexing_policy[Constants.VECTOR_INDEXES] is None
                or len(self._indexing_policy[Constants.VECTOR_INDEXES]) == 0
        ):
            raise ValueError(
                f"{Constants.VECTOR_INDEXES} cannot be null or empty in the indexing_policy."
            )

        if (
                self._vector_embedding_policy is None
                or Constants.VECTOR_EMBEDDINGS not in self._vector_embedding_policy
                or len(self._vector_embedding_policy[Constants.VECTOR_EMBEDDINGS]) == 0
        ):
            raise ValueError(
                f"{Constants.VECTOR_EMBEDDINGS} cannot be null "
                "or empty in the vector_embedding_policy."
            )

        if (
                self._cosmos_container_properties is None
                or self._cosmos_container_properties[Constants.PARTITION_KEY] is None
        ):
            raise ValueError(
                f"{Constants.PARTITION_KEY} cannot be null or empty for a container."
            )

        if (
                self._vector_search_fields is None
                or Constants.TEXT_FIELD not in self._vector_search_fields
                or not self._vector_search_fields[Constants.TEXT_FIELD]
                or Constants.EMBEDDING_FIELD not in self._vector_search_fields
                or not self._vector_search_fields[Constants.EMBEDDING_FIELD]
        ):
            raise ValueError(
                f"{Constants.TEXT_FIELD} and {Constants.EMBEDDING_FIELD} cannot be null or empty in vector_search_fields."
            )

        if self._full_text_search_enabled:
            if (
                    self._indexing_policy[Constants.FULL_TEXT_INDEXES] is None
                    or len(self._indexing_policy[Constants.FULL_TEXT_INDEXES]) == 0
            ):
                raise ValueError(
                    f"{Constants.FULL_TEXT_INDEXES} cannot be null or empty in the "
                    "indexing_policy if full text search is enabled."
                )
            if (
                    self._full_text_policy is None
                    or len(self._full_text_policy[Constants.FULL_TEXT_PATHS]) == 0
            ):
                raise ValueError(
                    f"{Constants.FULL_TEXT_PATHS} cannot be null or empty in the "
                    "full_text_policy if full text search is enabled."
                )

    def create_col(self) -> ContainerProxy:
        """
            Create a new collection (table in Cosmos DB No SQL).
            Enables vector extension and creates appropriate indexes.
        """
        #Validate all required parameters before creating the container
        self._validate_create_container()

        # Create the collection if it already doesn't exist
        return self._database.create_container_if_not_exists(
            id=self._collection_name,
            partition_key=self._cosmos_container_properties[Constants.PARTITION_KEY],
            indexing_policy=self._indexing_policy,
            default_ttl=self._cosmos_container_properties.get(Constants.DEFAULT_TTL),
            offer_throughput=self._cosmos_container_properties.get(Constants.OFFER_THROUGHPUT),
            unique_key_policy=self._cosmos_container_properties.get(Constants.UNIQUE_KEY_POLICY),
            conflict_resolution_policy=self._cosmos_container_properties.get(Constants.CONFLICT_RESOLUTION_POLICY),
            analytical_storage_ttl=self._cosmos_container_properties.get(Constants.ANALYTICAL_STORAGE_TTL),
            computed_properties=self._cosmos_container_properties.get(Constants.COMPUTED_PROPERTIES),
            etag=self._cosmos_container_properties.get(Constants.ETAG),
            match_condition=self._cosmos_container_properties.get(Constants.MATCH_CONDITION),
            session_token=self._cosmos_container_properties.get(Constants.SESSION_TOKEN),
            initial_headers=self._cosmos_container_properties.get(Constants.INITIAL_HEADERS),
            vector_embedding_policy=self._vector_embedding_policy,
            full_text_policy=self._full_text_policy,
        )

    def _create_item_to_insert(self, embedding: List[float], payload: Dict, id: str) -> Dict:
        text_key = self._vector_search_fields[Constants.TEXT_FIELD]
        embedding_key = self._vector_search_fields[Constants.EMBEDDING_FIELD]
        meta_data_key = self._metadata_key

        item = {
            Constants.ID: id,
            text_key: payload.get(text_key, ""),
            embedding_key: embedding,
            meta_data_key: payload.get(meta_data_key, {}),
        }
        return item

    def insert(
        self, embeddings: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None
    ) -> None:
        """
        Insert vector embeddings into the collection.

        Args:
            embeddings (List[List[float]]): List of vector embeddings to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vector embeddings.
            ids (List[str], optional): List of IDs corresponding to vector embeddings.
        """
        _ids = list(ids if ids is not None else (str(uuid.uuid4()) for _ in payloads))

        # create the items to insert
        to_insert = [
            self._create_item_to_insert(
                embeddings[i], payload, _ids[i]
            ) for i, payload in enumerate(payloads)
        ]

        # insert the documents in CosmosDB No Sql
        for item in to_insert:
            self._container.create_item(item)


    def search(
            self,
            embedding: Optional[List[float]] = None,
            k: int = 4,
            with_embedding: bool = False,
            search_type: str = Constants.VECTOR,
            offset_limit: Optional[str] = None,
            full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
            projection_mapping: Optional[Dict[str, Any]] = None,
            where: Optional[str] = None,
            weights: Optional[List[float]] = None,
            threshold: Optional[float] = 0.5,
            **kwargs: Any,
    ) -> List[OutputData]:
        """Run similarity search."""
        search_type = search_type or self._search_type

        # Validate search arguments
        self._validate_search_args(
            search_type=search_type,
            embedding=embedding,
            with_embedding=with_embedding,
        )

         # Construct the query and parameters
        query, parameters = self._construct_query(
            k=k,
            search_type=search_type,
            embedding=embedding,
            full_text_rank_filter=full_text_rank_filter,
            offset_limit=offset_limit,
            projection_mapping=projection_mapping,
            with_embedding=with_embedding,
            where=where,
            weights=weights,
        )

        return self._execute_query(
            query=query,
            search_type=search_type,
            parameters=parameters,
            with_embedding=with_embedding,
            projection_mapping=projection_mapping,
            threshold=threshold,
            **kwargs,
        )

    def _validate_search_args(
        self,
        search_type: str,
        embedding: Optional[List[float]] = None,
        with_embedding: bool = False,
    ):
        # Validate search_type
        if search_type not in self.VALID_SEARCH_TYPES:
            valid_options = ', '.join(self.VALID_SEARCH_TYPES)
            raise ValueError(
                f"Invalid search_type '{search_type}'. "
                f"Valid options are: {valid_options}."
            )

        # Validate embedding and with_embedding
        if self._is_vector_search_with_embedding(search_type):
            if embedding is None:
                raise ValueError(
                    f"Embedding must be provided for search_type '{search_type}'."
                )
        else:
            if with_embedding:
                raise ValueError(
                    f"with_embedding can only be True for vector search types."
                )

    def _is_vector_search_with_embedding(self, search_type: str) -> bool:
        """
        Check if the search type requires vector search with embedding.

        Args:
            search_type (str): The type of search.
        """
        return search_type in (
            Constants.VECTOR,
            Constants.VECTOR_SCORE_THRESHOLD,
            Constants.HYBRID,
            Constants.HYBRID_SCORE_THRESHOLD,
        )

    def _generate_projection_fields_with_text_filters(
            self,
            param_mapping: PramMapping,
            full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        projection_fields = [f"{self._table_alias}.{Constants.ID} as {Constants.ID}"]

        projection_fields += [
            param_mapping.gen_proj_field(
                key=item[Constants.SEARCH_FIELD], alias=item[Constants.SEARCH_FIELD], value=item[Constants.SEARCH_FIELD],
            ) for item in full_text_rank_filter
        ]

        projection = ", ".join(projection_fields)
        return projection

    def _generate_projection_fields(
            self,
            search_type: str,
            param_mapping: PramMapping,
            projection_mapping: Optional[Dict[str, Any]] = None,
            with_embedding: bool = False,
            embedding: Optional[List[float]] = None,
            full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        if search_type in (Constants.FULL_TEXT_RANKING, Constants.FULL_TEXT_SEARCH):
            # TODO: add check for this case
            if not full_text_rank_filter:
                raise ValueError(
                    f"'full_text_rank_filter' required for {search_type}."
                )
            return self._generate_projection_fields_with_text_filters(
                param_mapping=param_mapping,
                full_text_rank_filter=full_text_rank_filter,
            )

        if projection_mapping:
            projection_fields = [f"{self._table_alias}.{key} as {alias}" for key, alias in projection_mapping.items()]
        else:
            # Default projection fields: id, description, metadata
            projection_fields = [f"{self._table_alias}.{Constants.ID} as {Constants.ID}"]
            projection_fields += [
                param_mapping.gen_proj_field(
                    key=key, value=value, alias=alias,
                ) for key, value, alias in [
                    (Constants.TEXT_KEY, self._vector_search_fields[Constants.TEXT_FIELD], Constants.DESCRIPTION),
                    (Constants.METADATA_KEY, self._metadata_key, self._metadata_key),
                ]
            ]

        if with_embedding:
            projection_field = param_mapping.gen_proj_field(
                key=Constants.EMBEDDING_KEY,
                value=self._vector_search_fields[Constants.EMBEDDING_FIELD],
                alias=Constants.EMBEDDING,
            )
            projection_fields.append(projection_field)

        # f"VectorDistance({embedding_key_field}, {embedding_param_key}) as SimilarityScore"
        projection_field = param_mapping.gen_vector_distance_proj_field(
            embedding_field=self._vector_search_fields[Constants.EMBEDDING_FIELD],
            embeddings=embedding,
            alias=Constants.SIMILARITY_SCORE,
        )
        projection_fields.append(projection_field)

        projection = ", ".join(projection_fields)
        return projection

    def _generate_order_by_component_with_full_text_rank_filter(
            self,
            param_mapping: PramMapping,
            full_text_rank_filter: Dict[str, str],
    ) -> str:
        search_field = full_text_rank_filter[Constants.SEARCH_FIELD]
        search_proj_field = param_mapping.gen_proj_field(
            key=search_field,
            value=search_field,
        )

        search_text = full_text_rank_filter[Constants.SEARCH_TEXT]
        terms = [
            param_mapping.gen_param_key(
                key=f"{search_field}_term_{i}",
                value=term,
            ) for i, term in enumerate(search_text.split())
        ]

        component = f"FullTextScore({search_proj_field}, {', '.join(terms)})"
        return component


    def _generate_order_by_clause(
            self,
            search_type: str,
            param_mapping: PramMapping,
            embedding: Optional[List[float]] = None,
            weights: Optional[List[float]] = None,
            full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        order_by_clause = ""
        if search_type in ("vector", "vector_score_threshold"):
            vector_distance_proj_field = param_mapping.gen_vector_distance_proj_field(
                embedding_field=self._vector_search_fields[Constants.EMBEDDING_FIELD],
                embeddings=embedding,
            )
            # f"ORDER BY VectorDistance({table}[@embeddingKey], @embeddings)"
            order_by_clause = f"ORDER BY {vector_distance_proj_field}"
        elif search_type in ("full_text_ranking", "hybrid", "hybrid_score_threshold"):
            if not full_text_rank_filter:
                raise ValueError(
                    f"'full_text_rank_filter' required for {search_type} search."
                )
            components = [
                self._generate_order_by_component_with_full_text_rank_filter(
                    param_mapping=param_mapping,
                    full_text_rank_filter=item,
                ) for item in full_text_rank_filter
            ]

            if "hybrid" in search_type:
                # Sample: f"VectorDistance({table}[@embeddingKey], @embeddings)"
                vector_distance_proj_field = param_mapping.gen_vector_distance_proj_field(
                    embedding_field=self._vector_search_fields[Constants.EMBEDDING_FIELD],
                    embeddings=embedding,
                )
                components.append(vector_distance_proj_field)

                # Add weights if provided
                if weights:
                    weights_key = param_mapping.gen_param_key(key=Constants.WEIGHTS, value=weights)
                    components.append(weights_key)

            # Generate ORDER BY clause
            if len(components) == 1:
                order_by_clause = f"ORDER BY RANK {components[0]}"
            else:
                order_by_clause = f"ORDER BY RANK RRF({', '.join(components)})"
        return order_by_clause


    def _construct_query(
            self,
            k: int,
            search_type: str,
            embedding: Optional[List[float]] = None,
            full_text_rank_filter: Optional[List[Dict[str, str]]] = None,
            offset_limit: Optional[str] = None,
            projection_mapping: Optional[Dict[str, Any]] = None,
            with_embedding: bool = False,
            where: Optional[str] = None,
            weights: Optional[List[float]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        # Init query string and parameters list
        query = ["SELECT"]
        param_mapping = PramMapping(table=self._table_alias)

        # TOP clause
        if not offset_limit:
            limit_key = param_mapping.gen_param_key(
                key=Constants.LIMIT_KEY,
                value=k,
            )
            query.append(f"TOP {limit_key}")

        # Projection fields
        projection_fields = self._generate_projection_fields(
            search_type=search_type,
            param_mapping=param_mapping,
            projection_mapping=projection_mapping,
            with_embedding=with_embedding,
            embedding=embedding,
            full_text_rank_filter=full_text_rank_filter,
        )
        query.append(projection_fields)

        # From clause
        query.append(f"FROM {self._table_alias}")

        # Where clause
        if where:
            query.append(f"WHERE {where}")

        # Order By clause
        if search_type != Constants.FULL_TEXT_SEARCH:
            order_by_clause = self._generate_order_by_clause(
                search_type=search_type,
                param_mapping=param_mapping,
                embedding=embedding,
                weights=weights,
                full_text_rank_filter=full_text_rank_filter,
            )
            query.append(order_by_clause)

        # Limit/Offset clause
        if offset_limit:
            query.append(f"{offset_limit}")

        parameters = param_mapping.export_parameter_list()
        return " ".join(query), parameters


    def _execute_query(
        self,
        query: str,
        search_type: str,
        parameters: List[Dict[str, Any]],
        with_embedding: bool,
        projection_mapping: Optional[Dict[str, Any]],
        threshold: Optional[float] = 0.0,
        **kwargs: Any,
    ) -> List[OutputData]:
        # Execute the query
        items = self._container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True,
                    **kwargs
                )

        # Process the results
        output_data_list = []
        score_exist = self._is_vector_search_with_embedding(search_type)
        threshold = threshold or 0.0
        text_key = self._vector_search_fields[Constants.TEXT_FIELD]
        if projection_mapping and text_key in projection_mapping:
            text_key = projection_mapping[text_key]
        embedding_key = self._vector_search_fields[Constants.EMBEDDING_FIELD]

        for item in items:
            # Filter by score threshold if applicable
            score = 0.0
            if score_exist:
                score = item[Constants.SIMILARITY_SCORE]
                if Constants.SCORE_THRESHOLD in search_type and score <= threshold:
                    continue

            # Add embedding to metadata if requested
            metadata = item.pop(self._metadata_key, {})
            if with_embedding:
                metadata[embedding_key] = item[embedding_key]

            # Add projection_mapping fields to metadata
            id = str(item[Constants.ID])
            if projection_mapping:
                for alias in projection_mapping.values():
                    if alias != text_key:
                        metadata[alias] = item[alias]
            else:
                metadata[Constants.ID] = id

            payload = {text_key: item[text_key], self._metadata_key: metadata}
            output_data_list.append(
                OutputData(id=id, score=score, payload=payload)
            )

        return output_data_list

    def delete(self, vector_id: str) -> None:
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        if vector_id is None or vector_id == "":
            raise ValueError("vector_id cannot be null or empty.")

        try:
            self._container.delete_item(
                item=vector_id,
                partition_key=self._cosmos_container_properties[Constants.PARTITION_KEY]
            )
            logger.info(f"Deleted document with ID '{vector_id}'.")
        except CosmosResourceNotFoundError as e:
            logger.error(f"Error deleting document: {e}")

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None) -> None:
        """
        Update a vector and its payload. If vector not exist, it will be created.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        item = self._create_item_to_insert(vector, payload, vector_id)
        self._container.upsert_item(body=item)

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            Optional[OutputData]: Retrieved vector or None if not found.
        """
        item = self._container.read_item(
            item=vector_id,
            partition_key=self._cosmos_container_properties[Constants.PARTITION_KEY])
        if item:
            logger.info(f"Retrieved document with ID '{vector_id}'.")
            return item
        else:
            logger.warning(f"Document with ID '{vector_id}' not found.")
            return None

    def list_cols(self) -> List[str]:
        """
        List all collections in the database.

        Returns:
            List[str]: List of collection names.
        """
        collection_names = [col[Constants.ID] for col in self._database.list_containers()]
        logger.info(f"Listing collections in database '{self._database_name}': {collection_names}")
        return collection_names


    def delete_col(self) -> None:
        """Delete the collection."""
        self._database.delete_container(container=self._collection_name)
        logger.info(f"Deleted collection '{self._collection_name}'.")

    def col_info(self) -> Dict[str, Any]:
        """
        Get properties of the collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        return self._container.read()

    def list(self, limit: int = 100) -> List[OutputData]:
        """
        List vectors in the collection.

        Args:
            limit (int, optional): Number of vectors to return.

        Returns:
            List[OutputData]: List of vectors.
        """
        items = list(self._container.read_all_items(max_item_count=limit))
        logger.info(f"Retrieved {len(items)} documents from collection '{self._collection_name}'.")
        return items

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self._collection_name}...")
        self.delete_col()
        self.create_col()
