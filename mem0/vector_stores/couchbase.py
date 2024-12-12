import json
import logging
import time
from typing import Dict, Optional

import couchbase.search as search
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.exceptions import DocumentNotFoundException
from couchbase.management.search import SearchIndex
from couchbase.options import SearchOptions
from couchbase.vector_search import VectorQuery, VectorSearch
from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)  

class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]

class Couchbase(VectorStoreBase):  
    def __init__(  
        self,  
        embedding_model_dims: int,  
        connection_str: str,
        username: str,
        password: str,
        bucket_name: str,
        scope_name: str = "_default",
        collection_name: str = "_default",
        index_name: str | None = None,
        embedding_key: str = "embedding",
    ):  
        """  
        Initialize the Couchbase vector store.  

        Args:  
            bucket_name (str): Name of the Couchbase bucket.  
            embedding_model_dims (int): Dimensions of the embedding model.  
            host (str): Host address for Couchbase server.  
            username (str): Username for Couchbase authentication.  
            password (str): Password for Couchbase authentication.  
            collection_name (str, optional): Name of the collection. Defaults to "_default".  
        """  
        self.cluster = Cluster(connection_str, ClusterOptions(PasswordAuthenticator(username, password)))  
        self.bucket = self.cluster.bucket(bucket_name)
        self.scope = self.bucket.scope(scope_name)
        self.collection = self.scope.collection(collection_name)  
        self.embedding_model_dims = embedding_model_dims  
        self.collection_name = collection_name  
        self.index_name = index_name if index_name else f"{collection_name}_index"
        self.embedding_key = embedding_key

    def create_search_index(self, collection_name: str, search_index_name: str, vector_size: int, distance: str = "dot_product"):
        index_definition = {
            "type": "fulltext-index",
            "name": search_index_name,
            "sourceType": "couchbase",
            "sourceName": self.bucket.name,
            "planParams": {"maxPartitionsPerPIndex": 1024, "indexPartitions": 1},
            "params": {
                "doc_config": {
                    "docid_prefix_delim": "",
                    "docid_regexp": "",
                    "mode": "scope.collection.type_field",
                    "type_field": "type",
                },
                "mapping": {
                    "analysis": {},
                    "default_analyzer": "standard",
                    "default_datetime_parser": "dateTimeOptional",
                    "default_field": "_all",
                    "default_mapping": {"dynamic": True, "enabled": False},
                    "default_type": "_default",
                    "docvalues_dynamic": False,
                    "index_dynamic": True,
                    "store_dynamic": True,
                    "type_field": "_type",
                    "types": {
                        f"{self.scope.name}.{collection_name}": {
                            "dynamic": False,
                            "enabled": True,
                            "properties": {
                                "embedding": {
                                    "dynamic": False,
                                    "enabled": True,
                                    "fields": [
                                        {
                                            "dims": vector_size,
                                            "index": True,
                                            "name": "embedding",
                                            "similarity": distance,
                                            "type": "vector",
                                            "vector_index_optimized_for": "recall",
                                        }
                                    ],
                                },
                                "metadata": {"dynamic": True, "enabled": True},
                                "payload": {
                                    "dynamic": False,
                                    "enabled": True,
                                    "fields": [
                                        {
                                            "include_in_all": True,
                                            "index": True,
                                            "name": "text",
                                            "store": True,
                                            "type": "text",
                                        }
                                    ],
                                },
                            },
                        }
                    },
                },
                "store": {"indexType": "scorch", "segmentVersion": 16},
            },
            "sourceParams": {},
        }
        
        scope_index_manager = self.scope.search_indexes()
        search_index_def = SearchIndex.from_json(json.dumps(index_definition))
        max_attempts = 10
        attempt = 0
        while attempt < max_attempts:
            try:
                scope_index_manager.upsert_index(search_index_def)
                break
            except Exception as e:
                print(f"Attempt {attempt + 1}/{max_attempts}: Error creating search index: {e}")
                time.sleep(3)
                attempt += 1

        if attempt == max_attempts:
            print(f"Error creating search index after {max_attempts} attempts.")
            raise RuntimeError(f"Error creating search index after {max_attempts} attempts.")
        
        print(f"Search index {search_index_name} created successfully.")

    def create_col(self, name: str, vector_size: int, distance: str) -> bool:
        try:
            create_collection_query = f"CREATE COLLECTION {self.bucket.name}.{self.scope.name}.{name}"
            self.cluster.query(create_collection_query)
            logger.info(f"Collection {name} created successfully in scope {self.scope.name}.")
            
            create_index_query = f"CREATE PRIMARY INDEX ON {self.bucket.name}.{self.scope.name}.{name}"
            self.cluster.query(create_index_query)

            # Create a search index
            self.create_search_index(name, f"{name}_index", vector_size, distance)

            return True
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            return False

    def insert(self, vectors: list, payloads: list | None = None, ids: list | None = None):  
        """  
        Insert vectors into the Couchbase collection.  

        Args:  
            vectors (list): List of vectors to insert.  
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.  
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.  
        """  
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        docs = {}
        for idx, vector in enumerate(vectors):  
            doc_id = ids[idx] if ids else f"vector_{idx}"  
            document = {  
                self.embedding_key : vector,  
                "payload": payloads[idx] if payloads else {},  
            }
            docs[doc_id] = document
        self.scope.collection(self.collection_name).upsert_multi(docs)

    def search(self,  query: list, limit: int = 5, filters: dict | None = None) -> list:  
        """  
        Search for similar vectors.  

        Args:  
            query (list): Query vector.  
            limit (int, optional): Number of results to return. Defaults to 5.  
            filters (dict, optional): Filters to apply to the search. Defaults to None.  

        Returns:  
            list: Search results.  
        """  
        logger.info(f"Searching for similar vectors in collection {self.collection_name}")  
        search_req = search.SearchRequest.create(
            VectorSearch.from_vector_query(
                VectorQuery(
                    self.embedding_key,
                    query,
                    limit,
                )
            )
        )
        search_iter = self.scope.search(
            self.index_name,
            search_req,
            SearchOptions(
                limit=limit,
                fields=["*"],
                raw=filters,
            ),
        )
        docs = []

        # Parse the results
        for row in search_iter.rows():
            fields = dict(row.fields)
            payload = {k.split("payload.")[1]: v for k, v in fields.items() if k.startswith("payload.")}
            score = row.score
            doc = OutputData(id=row.id, payload=payload, score=score)
            docs.append(doc)

        return docs


    def delete(self, doc_id: str):  
        """  
        Delete a vector by ID.  

        Args:  
            doc_id (str): ID of the vector to delete.  
        """  
        try:  
            self.collection.remove(doc_id)  
            logger.info(f"Deleted vector with ID {doc_id}")  
        except DocumentNotFoundException:  
            logger.warning(f"Vector with ID {doc_id} not found")  

    def update(self, doc_id: str, vector: list | None = None, payload: dict | None = None):  
        """  
        Update a vector and its payload.  

        Args:  
            doc_id (str): ID of the vector to update.  
            vector (list, optional): Updated vector. Defaults to None.  
            payload (dict, optional): Updated payload. Defaults to None.  
        """  
        try:  
            doc = self.collection.get(doc_id).content_as[dict]  
            if vector:  
                doc[self.embedding_key] = vector  
            if payload:  
                doc["payload"] = payload  
            self.collection.upsert(doc_id, doc)  
            logger.info(f"Updated vector with ID {doc_id}")  
        except DocumentNotFoundException:  
            logger.warning(f"Vector with ID {doc_id} not found")  

    def get(self, doc_id: str) -> dict | None:  
        """  
        Retrieve a vector by ID.  

        Args:  
            doc_id (str): ID of the vector to retrieve.  

        Returns:  
            dict: Retrieved vector.  
        """  
        try:  
            doc = self.collection.get(doc_id).content_as[dict]  
            return doc  
        except DocumentNotFoundException:  
            logger.warning(f"Vector with ID {doc_id} not found")  
            return None  

    def list(self, filters: dict | None = None, limit: int = 100) -> list:  
        """  
        List all vectors in the collection.  

        Args:  
            filters (dict, optional): Filters to apply to the list. Defaults to None.  
            limit (int, optional): Number of vectors to return. Defaults to 100.  

        Returns:  
            list: List of vectors.  
        """  
        logger.info(f"Listing vectors in collection {self.collection.name}")
        query = f"SELECT id, {self.embedding_key}, payload FROM {self.bucket.name}.{self.scope.name}.{self.collection.name} WHERE 1 = 1" 
        results = []
        if filters:
            for filter in filters:
                query += f" AND {filter['field']} = {filter['value']}"
        
        query += f" LIMIT {limit}"

        search_result = self.cluster.query(query)

        for row in search_result.rows():  
            doc_id = row.id
            doc = self.collection.get(doc_id).content_as[dict]  
            results.append({"id": doc_id, **doc})  

        return results
    
    def list_cols(self):
        all_scopes = self.bucket.collections().get_all_scopes()
       
        for current_scope in all_scopes:
            if(current_scope.name == self.scope.name):
                all_collections = current_scope.collections
                return all_collections
        return super().list_cols()
    
    def delete_col(self, name):
        try:
            self.cluster.query(f"DROP COLLECTION {self.bucket.name}.{self.scope.name}.{name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
        return super().delete_col()
    
    def col_info(self, name):
        return self.scope.collection(name)