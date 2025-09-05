import logging
import uuid
from datetime import datetime
import pytz

from .base import NeptuneBase

try:
    from langchain_aws import NeptuneGraph
except ImportError:
    raise ImportError("langchain_aws is not installed. Please install it using 'make install_all'.")

logger = logging.getLogger(__name__)

class MemoryGraph(NeptuneBase):
    def __init__(self, config):
        """
        Initialize the Neptune DB memory store.
        """

        self.config = config

        self.graph = None
        endpoint = self.config.graph_store.config.endpoint
        if endpoint and endpoint.startswith("neptune-db://"):
            host = endpoint.replace("neptune-db://", "")
            port = 8182
            self.graph = NeptuneGraph(host, port)

        if not self.graph:
            raise ValueError("Unable to create a Neptune-DB client: missing 'endpoint' in config")

        self.node_label = ":`__Entity__`" if self.config.graph_store.config.base_label else ""

        self.embedding_model = NeptuneBase._create_embedding_model(self.config)

        # Default to openai if no specific provider is configured
        self.llm_provider = "openai"
        if self.config.graph_store.llm:
            self.llm_provider = self.config.graph_store.llm.provider
        elif self.config.llm.provider:
            self.llm_provider = self.config.llm.provider

        # fetch the vector store as a provider
        self.vector_store_provider = self.config.vector_store.provider
        if self.config.graph_store.config.collection_name:
            vector_store_collection_name = self.config.graph_store.config.collection_name
        else:
            vector_store_config = self.config.vector_store.config
            if vector_store_config.collection_name:
                vector_store_collection_name = vector_store_config.collection_name + "_neptune_vector_store"
            else:
                vector_store_collection_name = "mem0_neptune_vector_store"
        self.config.vector_store.config.collection_name = vector_store_collection_name
        self.vector_store = NeptuneBase._create_vector_store(self.vector_store_provider, self.config)

        self.llm = NeptuneBase._create_llm(self.config, self.llm_provider)
        self.user_id = None
        self.threshold = 0.7
        self.vector_store_limit=5

    def _delete_entities_cypher(self, source, destination, relationship, user_id):
        """
        Returns the OpenCypher query and parameters for deleting entities in the graph DB

        :param source: source node
        :param destination: destination node
        :param relationship: relationship label
        :param user_id: user_id to use
        :return: str, dict
        """

        cypher = f"""
            MATCH (n {self.node_label} {{name: $source_name, user_id: $user_id}})
            -[r:{relationship}]->
            (m {self.node_label} {{name: $dest_name, user_id: $user_id}})
            DELETE r
            RETURN 
                n.name AS source,
                m.name AS target,
                type(r) AS relationship
            """
        params = {
            "source_name": source,
            "dest_name": destination,
            "user_id": user_id,
        }
        logger.debug(f"_delete_entities\n  query={cypher}")
        return cypher, params

    def _add_entities_by_source_cypher(
            self,
            source_node_list,
            destination,
            dest_embedding,
            destination_type,
            relationship,
            user_id,
    ):
        """
        Returns the OpenCypher query and parameters for adding entities in the graph DB

        :param source_node_list: list of source nodes
        :param destination: destination name
        :param dest_embedding: destination embedding
        :param destination_type: destination node label
        :param relationship: relationship label
        :param user_id: user id to use
        :return: str, dict
        """
        destination_id = str(uuid.uuid4())
        destination_payload = {
            "name": destination,
            "type": destination_type,
            "user_id": user_id,
            "created_at": datetime.now(pytz.timezone("US/Pacific")).isoformat(),
        }
        self.vector_store.insert(
            vectors=[dest_embedding],
            payloads=[destination_payload],
            ids=[destination_id],
        )

        destination_label = self.node_label if self.node_label else f":`{destination_type}`"
        destination_extra_set = f", destination:`{destination_type}`" if self.node_label else ""

        cypher = f"""
                MATCH (source {{user_id: $user_id}})
                WHERE id(source) = $source_id
                SET source.mentions = coalesce(source.mentions, 0) + 1
                WITH source
                MERGE (destination {destination_label} {{`~id`: $destination_id, name: $destination_name, user_id: $user_id}})
                ON CREATE SET
                    destination.created = timestamp(),
                    destination.updated = timestamp(),
                    destination.mentions = 1
                    {destination_extra_set}
                ON MATCH SET
                    destination.mentions = coalesce(destination.mentions, 0) + 1,
                    destination.updated = timestamp()
                WITH source, destination
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET 
                    r.created = timestamp(),
                    r.updated = timestamp(),
                    r.mentions = 1
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1,
                    r.updated = timestamp()
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target, id(destination) AS destination_id
                """

        params = {
            "source_id": source_node_list[0]["id(source_candidate)"],
            "destination_id": destination_id,
            "destination_name": destination,
            "dest_embedding": dest_embedding,
            "user_id": user_id,
        }

        logger.debug(
            f"_add_entities:\n  source_node_search_result={source_node_list[0]}\n  query={cypher}"
        )
        return cypher, params

    def _add_entities_by_destination_cypher(
            self,
            source,
            source_embedding,
            source_type,
            destination_node_list,
            relationship,
            user_id,
    ):
        """
        Returns the OpenCypher query and parameters for adding entities in the graph DB

        :param source: source node name
        :param source_embedding: source node embedding
        :param source_type: source node label
        :param destination_node_list: list of dest nodes
        :param relationship: relationship label
        :param user_id: user id to use
        :return: str, dict
        """
        source_id = str(uuid.uuid4())
        source_payload = {
            "name": source,
            "type": source_type,
            "user_id": user_id,
            "created_at": datetime.now(pytz.timezone("US/Pacific")).isoformat(),
        }
        self.vector_store.insert(
            vectors=[source_embedding],
            payloads=[source_payload],
            ids=[source_id],
        )

        source_label = self.node_label if self.node_label else f":`{source_type}`"
        source_extra_set = f", source:`{source_type}`" if self.node_label else ""

        cypher = f"""
                MATCH (destination {{user_id: $user_id}})
                WHERE id(destination) = $destination_id
                SET 
                    destination.mentions = coalesce(destination.mentions, 0) + 1,
                    destination.updated = timestamp()
                WITH destination
                MERGE (source {source_label} {{`~id`: $source_id, name: $source_name, user_id: $user_id}})
                ON CREATE SET
                    source.created = timestamp(),
                    source.updated = timestamp(),
                    source.mentions = 1
                    {source_extra_set}
                ON MATCH SET
                    source.mentions = coalesce(source.mentions, 0) + 1,
                    source.updated = timestamp()
                WITH source, destination
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET 
                    r.created = timestamp(),
                    r.updated = timestamp(),
                    r.mentions = 1
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1,
                    r.updated = timestamp()
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                """

        params = {
            "destination_id": destination_node_list[0]["id(destination_candidate)"],
            "source_id": source_id,
            "source_name": source,
            "source_embedding": source_embedding,
            "user_id": user_id,
        }
        logger.debug(
            f"_add_entities:\n  destination_node_search_result={destination_node_list[0]}\n  query={cypher}"
        )
        return cypher, params

    def _add_relationship_entities_cypher(
            self,
            source_node_list,
            destination_node_list,
            relationship,
            user_id,
    ):
        """
        Returns the OpenCypher query and parameters for adding entities in the graph DB

        :param source_node_list: list of source node ids
        :param destination_node_list: list of dest node ids
        :param relationship: relationship label
        :param user_id: user id to use
        :return: str, dict
        """

        cypher = f"""
                MATCH (source {{user_id: $user_id}})
                WHERE id(source) = $source_id
                SET 
                    source.mentions = coalesce(source.mentions, 0) + 1,
                    source.updated = timestamp()
                WITH source
                MATCH (destination {{user_id: $user_id}})
                WHERE id(destination) = $destination_id
                SET 
                    destination.mentions = coalesce(destination.mentions) + 1,
                    destination.updated = timestamp()
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET 
                    r.created_at = timestamp(),
                    r.updated_at = timestamp(),
                    r.mentions = 1
                ON MATCH SET r.mentions = coalesce(r.mentions, 0) + 1
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                """
        params = {
            "source_id": source_node_list[0]["id(source_candidate)"],
            "destination_id": destination_node_list[0]["id(destination_candidate)"],
            "user_id": user_id,
        }
        logger.debug(
            f"_add_entities:\n  destination_node_search_result={destination_node_list[0]}\n  source_node_search_result={source_node_list[0]}\n  query={cypher}"
        )
        return cypher, params

    def _add_new_entities_cypher(
        self,
        source,
        source_embedding,
        source_type,
        destination,
        dest_embedding,
        destination_type,
        relationship,
        user_id,
    ):
        """
        Returns the OpenCypher query and parameters for adding entities in the graph DB

        :param source: source node name
        :param source_embedding: source node embedding
        :param source_type: source node label
        :param destination: destination name
        :param dest_embedding: destination embedding
        :param destination_type: destination node label
        :param relationship: relationship label
        :param user_id: user id to use
        :return: str, dict
        """
        source_id = str(uuid.uuid4())
        source_payload = {
            "name": source,
            "type": source_type,
            "user_id": user_id,
            "created_at": datetime.now(pytz.timezone("US/Pacific")).isoformat(),
        }
        destination_id = str(uuid.uuid4())
        destination_payload = {
            "name": destination,
            "type": destination_type,
            "user_id": user_id,
            "created_at": datetime.now(pytz.timezone("US/Pacific")).isoformat(),
        }
        self.vector_store.insert(
            vectors=[source_embedding, dest_embedding],
            payloads=[source_payload, destination_payload],
            ids=[source_id, destination_id],
        )

        source_label = self.node_label if self.node_label else f":`{source_type}`"
        source_extra_set = f", source:`{source_type}`" if self.node_label else ""
        destination_label = self.node_label if self.node_label else f":`{destination_type}`"
        destination_extra_set = f", destination:`{destination_type}`" if self.node_label else ""

        cypher = f"""
                MERGE (n {source_label} {{name: $source_name, user_id: $user_id, `~id`: $source_id}})
                ON CREATE SET n.created = timestamp(),
                              n.mentions = 1
                              {source_extra_set}
                ON MATCH SET n.mentions = coalesce(n.mentions, 0) + 1
                WITH n
                MERGE (m {destination_label} {{name: $dest_name, user_id: $user_id, `~id`: $dest_id}})
                ON CREATE SET m.created = timestamp(),
                              m.mentions = 1
                              {destination_extra_set}
                ON MATCH SET m.mentions = coalesce(m.mentions, 0) + 1
                WITH n, m
                MERGE (n)-[rel:{relationship}]->(m)
                ON CREATE SET rel.created = timestamp(), rel.mentions = 1
                ON MATCH SET rel.mentions = coalesce(rel.mentions, 0) + 1
                RETURN n.name AS source, type(rel) AS relationship, m.name AS target
                """
        params = {
            "source_id": source_id,
            "dest_id": destination_id,
            "source_name": source,
            "dest_name": destination,
            "source_embedding": source_embedding,
            "dest_embedding": dest_embedding,
            "user_id": user_id,
        }
        logger.debug(
            f"_add_new_entities_cypher:\n  query={cypher}"
        )
        return cypher, params

    def _search_source_node_cypher(self, source_embedding, user_id, threshold):
        """
        Returns the OpenCypher query and parameters to search for source nodes

        :param source_embedding: source vector
        :param user_id: user_id to use
        :param threshold: the threshold for similarity
        :return: str, dict
        """

        source_nodes = self.vector_store.search(
            query="",
            vectors=source_embedding,
            limit=self.vector_store_limit,
            filters={"user_id": user_id},
        )

        ids = [n.id for n in filter(lambda s: s.score > threshold, source_nodes)]

        cypher = f"""
            MATCH (source_candidate {self.node_label})
            WHERE source_candidate.user_id = $user_id AND id(source_candidate) IN $ids
            RETURN id(source_candidate)
            """

        params = {
            "ids": ids,
            "source_embedding": source_embedding,
            "user_id": user_id,
            "threshold": threshold,
        }
        logger.debug(f"_search_source_node\n  query={cypher}")
        return cypher, params

    def _search_destination_node_cypher(self, destination_embedding, user_id, threshold):
        """
        Returns the OpenCypher query and parameters to search for destination nodes

        :param source_embedding: source vector
        :param user_id: user_id to use
        :param threshold: the threshold for similarity
        :return: str, dict
        """
        destination_nodes = self.vector_store.search(
            query="",
            vectors=destination_embedding,
            limit=self.vector_store_limit,
            filters={"user_id": user_id},
        )

        ids = [n.id for n in filter(lambda d: d.score > threshold, destination_nodes)]

        cypher = f"""
            MATCH (destination_candidate {self.node_label})
            WHERE destination_candidate.user_id = $user_id AND id(destination_candidate) IN $ids
            RETURN id(destination_candidate)
            """

        params = {
            "ids": ids,
            "destination_embedding": destination_embedding,
            "user_id": user_id,
        }

        logger.debug(f"_search_destination_node\n  query={cypher}")
        return cypher, params

    def _delete_all_cypher(self, filters):
        """
        Returns the OpenCypher query and parameters to delete all edges/nodes in the memory store

        :param filters: search filters
        :return: str, dict
        """

        # remove the vector store index
        self.vector_store.reset()

        # create a query that: deletes the nodes of the graph_store
        cypher = f"""
        MATCH (n {self.node_label} {{user_id: $user_id}})
        DETACH DELETE n
        """
        params = {"user_id": filters["user_id"]}

        logger.debug(f"delete_all query={cypher}")
        return cypher, params

    def _get_all_cypher(self, filters, limit):
        """
        Returns the OpenCypher query and parameters to get all edges/nodes in the memory store

        :param filters: search filters
        :param limit: return limit
        :return: str, dict
        """

        cypher = f"""
        MATCH (n {self.node_label} {{user_id: $user_id}})-[r]->(m {self.node_label} {{user_id: $user_id}})
        RETURN n.name AS source, type(r) AS relationship, m.name AS target
        LIMIT $limit
        """
        params = {"user_id": filters["user_id"], "limit": limit}
        return cypher, params

    def _search_graph_db_cypher(self, n_embedding, filters, limit):
        """
        Returns the OpenCypher query and parameters to search for similar nodes in the memory store

        :param n_embedding: node vector
        :param filters: search filters
        :param limit: return limit
        :return: str, dict
        """

        # search vector store for applicable nodes using cosine similarity
        search_nodes = self.vector_store.search(
            query="",
            vectors=n_embedding,
            limit=self.vector_store_limit,
            filters=filters,
        )

        ids = [n.id for n in search_nodes]

        cypher_query = f"""
            MATCH (n {self.node_label})-[r]->(m)
            WHERE n.user_id = $user_id AND id(n) IN $n_ids
            RETURN n.name AS source, id(n) AS source_id, type(r) AS relationship, id(r) AS relation_id, m.name AS destination, id(m) AS destination_id
            UNION
            MATCH (m)-[r]->(n {self.node_label}) 
            RETURN m.name AS source, id(m) AS source_id, type(r) AS relationship, id(r) AS relation_id, n.name AS destination, id(n) AS destination_id
            LIMIT $limit
        """
        params = {
            "n_ids": ids,
            "user_id": filters["user_id"],
            "limit": limit,
        }
        logger.debug(f"_search_graph_db\n  query={cypher_query}")

        return cypher_query, params
