import logging

from mem0.memory.utils import format_entities

try:
    from langchain_community.graphs import Neo4jGraph
except ImportError:
    raise ImportError("langchain_community is not installed. Please install it using pip install langchain-community")

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    raise ImportError("rank_bm25 is not installed. Please install it using pip install rank-bm25")

from mem0.graphs.tools import (
    ADD_MEMORY_STRUCT_TOOL_GRAPH,
    ADD_MEMORY_TOOL_GRAPH,
    EXTRACT_ENTITIES_STRUCT_TOOL,
    EXTRACT_ENTITIES_TOOL,
    NOOP_STRUCT_TOOL,
    NOOP_TOOL,
    RELATIONS_STRUCT_TOOL,
    RELATIONS_TOOL,
    UPDATE_MEMORY_STRUCT_TOOL_GRAPH,
    UPDATE_MEMORY_TOOL_GRAPH,
)
from mem0.graphs.utils import EXTRACT_RELATIONS_PROMPT, get_update_memory_messages
from mem0.utils.factory import EmbedderFactory, LlmFactory

logger = logging.getLogger(__name__)


class MemoryGraph:
    def __init__(self, config):
        self.config = config
        self.graph = Neo4jGraph(
            self.config.graph_store.config.url,
            self.config.graph_store.config.username,
            self.config.graph_store.config.password,
        )
        self.embedding_model = EmbedderFactory.create(self.config.embedder.provider, self.config.embedder.config)

        self.llm_provider = "openai_structured"
        if self.config.llm.provider:
            self.llm_provider = self.config.llm.provider
        if self.config.graph_store.llm:
            self.llm_provider = self.config.graph_store.llm.provider

        self.llm = LlmFactory.create(self.llm_provider, self.config.llm.config)
        self.user_id = None
        self.threshold = 0.7

    def add(self, data, filters):
        """
        Adds data to the graph.

        Args:
            data (str): The data to add to the graph.
            filters (dict): A dictionary containing filters to be applied during the addition.
        """

        # retrieve the search results
        search_output, entity_type_map = self._search(data, filters)

        # extract relations
        extracted_relations = self._extract_relations(data, filters, entity_type_map)
        
        search_output_string = format_entities(search_output)
        extracted_relations_string = format_entities(extracted_relations)
        update_memory_prompt = get_update_memory_messages(search_output_string, extracted_relations_string)

        _tools = [UPDATE_MEMORY_TOOL_GRAPH, ADD_MEMORY_TOOL_GRAPH, NOOP_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [
                UPDATE_MEMORY_STRUCT_TOOL_GRAPH,
                ADD_MEMORY_STRUCT_TOOL_GRAPH,
                NOOP_STRUCT_TOOL,
            ]

        memory_updates = self.llm.generate_response(
            messages=update_memory_prompt,
            tools=_tools,
        )

        to_be_added = []

        for item in memory_updates["tool_calls"]:
            if item["name"] == "add_graph_memory":
                to_be_added.append(item["arguments"])
            elif item["name"] == "update_graph_memory":
                self._update_relationship(
                    item["arguments"]["source"],
                    item["arguments"]["destination"],
                    item["arguments"]["relationship"],
                    filters,
                )
            elif item["name"] == "noop":
                continue

        returned_entities = []

        for item in to_be_added:
            source = item["source"].lower().replace(" ", "_")
            source_type = item["source_type"].lower().replace(" ", "_")
            relation = item["relationship"].lower().replace(" ", "_")
            destination = item["destination"].lower().replace(" ", "_")
            destination_type = item["destination_type"].lower().replace(" ", "_")

            returned_entities.append({"source": source, "relationship": relation, "target": destination})

            # Create embeddings
            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            # Updated Cypher query to include node types and embeddings
            cypher = f"""
            MERGE (n:{source_type} {{name: $source_name, user_id: $user_id}})
            ON CREATE SET n.created = timestamp(), n.embedding = $source_embedding
            ON MATCH SET n.embedding = $source_embedding
            MERGE (m:{destination_type} {{name: $dest_name, user_id: $user_id}})
            ON CREATE SET m.created = timestamp(), m.embedding = $dest_embedding
            ON MATCH SET m.embedding = $dest_embedding
            MERGE (n)-[rel:{relation}]->(m)
            ON CREATE SET rel.created = timestamp()
            RETURN n, rel, m
            """

            params = {
                "source_name": source,
                "dest_name": destination,
                "source_embedding": source_embedding,
                "dest_embedding": dest_embedding,
                "user_id": filters["user_id"],
            }

            _ = self.graph.query(cypher, params=params)

        logger.info(f"Added {len(to_be_added)} new memories to the graph")

        return returned_entities

    def _search(self, query, filters, limit=100):
        _tools = [EXTRACT_ENTITIES_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [EXTRACT_ENTITIES_STRUCT_TOOL]
        search_results = self.llm.generate_response(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a smart assistant who understands entities and their types in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use {filters['user_id']} as the source entity. Extract all the entities from the text. ***DO NOT*** answer the question itself if the given text is a question.",
                },
                {"role": "user", "content": query},
            ],
            tools=_tools,
        )

        entity_type_map = {}

        try:
            for item in search_results["tool_calls"][0]["arguments"]["entities"]:
                entity_type_map[item["entity"]] = item["entity_type"]
        except Exception as e:
            logger.error(f"Error in search tool: {e}")

        logger.debug(f"Entity type map: {entity_type_map}")

        result_relations = []

        for node in list(entity_type_map.keys()):
            n_embedding = self.embedding_model.embed(node)

            cypher_query = """
            MATCH (n)
            WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
            WITH n,
                round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) /
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) *
                sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
            WHERE similarity >= $threshold
            MATCH (n)-[r]->(m)
            RETURN n.name AS source, elementId(n) AS source_id, type(r) AS relation, elementId(r) AS relation_id, m.name AS destination, elementId(m) AS destination_id, similarity
            UNION
            MATCH (n)
            WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
            WITH n,
                round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) /
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) *
                sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
            WHERE similarity >= $threshold
            MATCH (m)-[r]->(n)
            RETURN m.name AS source, elementId(m) AS source_id, type(r) AS relation, elementId(r) AS relation_id, n.name AS destination, elementId(n) AS destination_id, similarity
            ORDER BY similarity DESC
            LIMIT $limit
            """
            params = {
                "n_embedding": n_embedding,
                "threshold": self.threshold,
                "user_id": filters["user_id"],
                "limit": limit,
            }
            ans = self.graph.query(cypher_query, params=params)
            result_relations.extend(ans)

        return result_relations, entity_type_map

    def search(self, query, filters, limit=100):
        """
        Search for memories and related graph data.

        Args:
            query (str): Query to search for.
            filters (dict): A dictionary containing filters to be applied during the search.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 100.

        Returns:
            dict: A dictionary containing:
                - "contexts": List of search results from the base data store.
                - "entities": List of related graph data based on the query.
        """

        search_output, entity_type_map = self._search(query, filters, limit)

        if not search_output:
            return []

        search_outputs_sequence = [[item["source"], item["relation"], item["destination"]] for item in search_output]
        bm25 = BM25Okapi(search_outputs_sequence)

        tokenized_query = query.split(" ")
        reranked_results = bm25.get_top_n(tokenized_query, search_outputs_sequence, n=5)

        search_results = []
        for item in reranked_results:
            search_results.append({"source": item[0], "relationship": item[1], "target": item[2]})

        logger.info(f"Returned {len(search_results)} search results")

        return search_results

    def delete_all(self, filters):
        cypher = """
        MATCH (n {user_id: $user_id})
        DETACH DELETE n
        """
        params = {"user_id": filters["user_id"]}
        self.graph.query(cypher, params=params)

    def get_all(self, filters, limit=100):
        """
        Retrieves all nodes and relationships from the graph database based on optional filtering criteria.

        Args:
            filters (dict): A dictionary containing filters to be applied during the retrieval.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 100.
        Returns:
            list: A list of dictionaries, each containing:
                - 'contexts': The base data store response for each memory.
                - 'entities': A list of strings representing the nodes and relationships
        """

        # return all nodes and relationships
        query = """
        MATCH (n {user_id: $user_id})-[r]->(m {user_id: $user_id})
        RETURN n.name AS source, type(r) AS relationship, m.name AS target
        LIMIT $limit
        """
        results = self.graph.query(query, params={"user_id": filters["user_id"], "limit": limit})

        final_results = []
        for result in results:
            final_results.append(
                {
                    "source": result["source"],
                    "relationship": result["relationship"],
                    "target": result["target"],
                }
            )

        logger.info(f"Retrieved {len(final_results)} relationships")

        return final_results

    def _extract_relations(self, data, filters, entity_type_map, limit=100):

        if self.config.graph_store.custom_prompt:
            messages = [
                {
                    "role": "system",
                    "content": EXTRACT_RELATIONS_PROMPT.replace("USER_ID", filters["user_id"]).replace(
                        "CUSTOM_PROMPT", f"4. {self.config.graph_store.custom_prompt}"
                    ),
                },
                {"role": "user", "content": data},
            ]
        else:
            messages = [
                {
                    "role": "system",
                    "content": EXTRACT_RELATIONS_PROMPT.replace("USER_ID", filters["user_id"]),
                },
                {"role": "user", "content": f"List of entities: {list(entity_type_map.keys())}. \n\nText: {data}"},
            ]

        _tools = [RELATIONS_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [RELATIONS_STRUCT_TOOL]

        extracted_entities = self.llm.generate_response(
            messages=messages,
            tools=_tools,
        )

        if extracted_entities["tool_calls"]:
            extracted_entities = extracted_entities["tool_calls"][0]["arguments"]["entities"]
        else:
            extracted_entities = []

        logger.debug(f"Extracted entities: {extracted_entities}")
        
        return extracted_entities

    def _update_relationship(self, source, target, relationship, filters):
        """
        Update or create a relationship between two nodes in the graph.

        Args:
            source (str): The name of the source node.
            target (str): The name of the target node.
            relationship (str): The type of the relationship.
            filters (dict): A dictionary containing filters to be applied during the update.

        Raises:
            Exception: If the operation fails.
        """
        logger.info(f"Updating relationship: {source} -{relationship}-> {target}")

        relationship = relationship.lower().replace(" ", "_")

        # Check if nodes exist and create them if they don't
        check_and_create_query = """
        MERGE (n1 {name: $source, user_id: $user_id})
        MERGE (n2 {name: $target, user_id: $user_id})
        """
        self.graph.query(
            check_and_create_query,
            params={"source": source, "target": target, "user_id": filters["user_id"]},
        )

        # Delete any existing relationship between the nodes
        delete_query = """
        MATCH (n1 {name: $source, user_id: $user_id})-[r]->(n2 {name: $target, user_id: $user_id})
        DELETE r
        """
        self.graph.query(
            delete_query,
            params={"source": source, "target": target, "user_id": filters["user_id"]},
        )

        # Create the new relationship
        create_query = f"""
        MATCH (n1 {{name: $source, user_id: $user_id}}), (n2 {{name: $target, user_id: $user_id}})
        CREATE (n1)-[r:{relationship}]->(n2)
        RETURN n1, r, n2
        """
        result = self.graph.query(
            create_query,
            params={"source": source, "target": target, "user_id": filters["user_id"]},
        )

        if not result:
            raise Exception(f"Failed to update or create relationship between {source} and {target}")
