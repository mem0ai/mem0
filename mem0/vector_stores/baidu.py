import logging
import time
from typing import Dict, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    import pymochow
    from pymochow.configuration import Configuration
    from pymochow.auth.bce_credentials import BceCredentials
    from pymochow.model.enum import FieldType, MetricType, IndexType, TableState, ServerErrCode
    from pymochow.model.schema import Field, Schema, VectorIndex, FilteringIndex, HNSWParams, AutoBuildRowCountIncrement
    from pymochow.model.table import Partition, Row, VectorSearchConfig, VectorTopkSearchRequest, FloatVector
    from pymochow.exception import ServerError
except ImportError:
    raise ImportError("The 'pymochow' library is required. Please install it using 'pip install pymochow'.")

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class BaiduDB(VectorStoreBase):
    def __init__(
        self,
        endpoint: str,
        account: str,
        api_key: str,
        database_name: str,
        table_name: str,
        embedding_model_dims: int,
        metric_type: MetricType,
    ) -> None:
        """Initialize the BaiduDB database.

        Args:
            endpoint (str): Endpoint URL for Baidu VectorDB.
            account (str): Account for Baidu VectorDB.
            api_key (str): API Key for Baidu VectorDB.
            database_name (str): Name of the database.
            table_name (str): Name of the table.
            embedding_model_dims (int): Dimensions of the embedding model.
            metric_type (MetricType): Metric type for similarity search.
        """
        self.endpoint = endpoint
        self.account = account
        self.api_key = api_key
        self.database_name = database_name
        self.table_name = table_name
        self.embedding_model_dims = embedding_model_dims
        self.metric_type = metric_type

        # Initialize Mochow client
        config = Configuration(credentials=BceCredentials(account, api_key), endpoint=endpoint)
        self.client = pymochow.MochowClient(config)

        # Ensure database and table exist
        self._create_database_if_not_exists()
        self.create_col(
            name=self.table_name,
            vector_size=self.embedding_model_dims,
            distance=self.metric_type,
        )

    def _create_database_if_not_exists(self):
        """Create database if it doesn't exist."""
        try:
            # Check if database exists
            databases = self.client.list_databases()
            db_exists = any(db.database_name == self.database_name for db in databases)
            if not db_exists:
                self._database = self.client.create_database(self.database_name)
                logger.info(f"Created database: {self.database_name}")
            else:
                self._database = self.client.database(self.database_name)
                logger.info(f"Database {self.database_name} already exists")
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            raise

    def create_col(self, name, vector_size, distance):
        """Create a new table.

        Args:
            name (str): Name of the table to create.
            vector_size (int): Dimension of the vector.
            distance (str): Metric type for similarity search.
        """
        # Check if table already exists
        try:
            tables = self._database.list_table()
            table_exists = any(table.table_name == name for table in tables)
            if table_exists:
                logger.info(f"Table {name} already exists. Skipping creation.")
                self._table = self._database.describe_table(name)
                return

            # Convert distance string to MetricType enum
            metric_type = None
            for k, v in MetricType.__members__.items():
                if k == distance:
                    metric_type = v
            if metric_type is None:
                raise ValueError(f"Unsupported metric_type: {distance}")

            # Define table schema
            fields = [
                Field(
                    "id", FieldType.STRING, primary_key=True, partition_key=True, auto_increment=False, not_null=True
                ),
                Field("vector", FieldType.FLOAT_VECTOR, dimension=vector_size),
                Field("metadata", FieldType.JSON),
            ]

            # Create vector index
            indexes = [
                VectorIndex(
                    index_name="vector_idx",
                    index_type=IndexType.HNSW,
                    field="vector",
                    metric_type=metric_type,
                    params=HNSWParams(m=16, efconstruction=200),
                    auto_build=True,
                    auto_build_index_policy=AutoBuildRowCountIncrement(row_count_increment=10000),
                ),
                FilteringIndex(index_name="metadata_filtering_idx", fields=["metadata"]),
            ]

            schema = Schema(fields=fields, indexes=indexes)

            # Create table
            self._table = self._database.create_table(
                table_name=name, replication=3, partition=Partition(partition_num=1), schema=schema
            )
            logger.info(f"Created table: {name}")

            # Wait for table to be ready
            while True:
                time.sleep(2)
                table = self._database.describe_table(name)
                if table.state == TableState.NORMAL:
                    logger.info(f"Table {name} is ready.")
                    break
                logger.info(f"Waiting for table {name} to be ready, current state: {table.state}")
            self._table = table
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            raise

    def insert(self, vectors, payloads=None, ids=None):
        """Insert vectors into the table.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        # Prepare data for insertion
        for idx, vector, metadata in zip(ids, vectors, payloads):
            row = Row(id=idx, vector=vector, metadata=metadata)
            self._table.upsert(rows=[row])

    def search(self, query: str, vectors: list, limit: int = 5, filters: dict = None) -> list:
        """
        Search for similar vectors.

        Args:
            query (str): Query string.
            vectors (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        # Add filters if provided
        search_filter = None
        if filters:
            search_filter = self._create_filter(filters)

        # Create AnnSearch for vector search
        request = VectorTopkSearchRequest(
            vector_field="vector",
            vector=FloatVector(vectors),
            limit=limit,
            filter=search_filter,
            config=VectorSearchConfig(ef=200),
        )

        # Perform search
        projections = ["id", "metadata"]
        res = self._table.vector_search(request=request, projections=projections)

        # Parse results
        output = []
        for row in res.rows:
            row_data = row.get("row", {})
            output_data = OutputData(
                id=row_data.get("id"), score=row.get("score", 0.0), payload=row_data.get("metadata", {})
            )
            output.append(output_data)

        return output

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self._table.delete(primary_key={"id": vector_id})

    def update(self, vector_id=None, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        row = Row(id=vector_id, vector=vector, metadata=payload)
        self._table.upsert(rows=[row])

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        projections = ["id", "metadata"]
        result = self._table.query(primary_key={"id": vector_id}, projections=projections)
        row = result.row
        return OutputData(id=row.get("id"), score=None, payload=row.get("metadata", {}))

    def list_cols(self):
        """
        List all tables (collections).

        Returns:
            List[str]: List of table names.
        """
        tables = self._database.list_table()
        return [table.table_name for table in tables]

    def delete_col(self):
        """Delete the table."""
        try:
            tables = self._database.list_table()

            # skip drop table if table not exists
            table_exists = any(table.table_name == self.table_name for table in tables)
            if not table_exists:
                logger.info(f"Table {self.table_name} does not exist, skipping deletion")
                return

            # Delete the table
            self._database.drop_table(self.table_name)
            logger.info(f"Initiated deletion of table {self.table_name}")

            # Wait for table to be completely deleted
            while True:
                time.sleep(2)
                try:
                    self._database.describe_table(self.table_name)
                    logger.info(f"Waiting for table {self.table_name} to be deleted...")
                except ServerError as e:
                    if e.code == ServerErrCode.TABLE_NOT_EXIST:
                        logger.info(f"Table {self.table_name} has been completely deleted")
                        break
                    logger.error(f"Error checking table status: {e}")
                    raise
        except Exception as e:
            logger.error(f"Error deleting table: {e}")
            raise

    def col_info(self):
        """
        Get information about the table.

        Returns:
            Dict[str, Any]: Table information.
        """
        return self._table.stats()

    def list(self, filters: dict = None, limit: int = 100) -> list:
        """
        List all vectors in the table.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        projections = ["id", "metadata"]
        list_filter = self._create_filter(filters) if filters else None
        result = self._table.select(filter=list_filter, projections=projections, limit=limit)

        memories = []
        for row in result.rows:
            obj = OutputData(id=row.get("id"), score=None, payload=row.get("metadata", {}))
            memories.append(obj)

        return [memories]

    def reset(self):
        """Reset the table by deleting and recreating it."""
        logger.warning(f"Resetting table {self.table_name}...")
        try:
            self.delete_col()
            self.create_col(
                name=self.table_name,
                vector_size=self.embedding_model_dims,
                distance=self.metric_type,
            )
        except Exception as e:
            logger.warning(f"Error resetting table: {e}")
            raise

    def _create_filter(self, filters: dict) -> str:
        """
        Create filter expression for queries.

        Args:
            filters (dict): Filter conditions.

        Returns:
            str: Filter expression.
        """
        conditions = []
        for key, value in filters.items():
            if isinstance(value, str):
                conditions.append(f'metadata["{key}"] = "{value}"')
            else:
                conditions.append(f'metadata["{key}"] = {value}')
        return " AND ".join(conditions)
