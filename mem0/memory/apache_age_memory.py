import logging
import json
from typing import List, Dict, Any, Optional

from mem0.memory.utils import format_entities, sanitize_relationship_for_cypher

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    raise ImportError("psycopg2 is not installed. Please install it using pip install psycopg2-binary")

try:
    import age
except ImportError:
    raise ImportError("apache-age-python is not installed. Please install it using pip install apache-age-python")

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    raise ImportError("rank_bm25 is not installed. Please install it using pip install rank-bm25")

from mem0.graphs.tools import (
    DELETE_MEMORY_STRUCT_TOOL_GRAPH,
    DELETE_MEMORY_TOOL_GRAPH,
    EXTRACT_ENTITIES_STRUCT_TOOL,
    EXTRACT_ENTITIES_TOOL,
    RELATIONS_STRUCT_TOOL,
    RELATIONS_TOOL,
)
from mem0.graphs.utils import EXTRACT_RELATIONS_PROMPT, get_delete_messages
from mem0.utils.factory import EmbedderFactory, LlmFactory

logger = logging.getLogger(__name__)


class MemoryGraph:
    def __init__(self, config):
        self.config = config
        
        # Initialize PostgreSQL connection for Apache AGE
        self.connection = psycopg2.connect(
            host=self.config.graph_store.config.host,
            port=self.config.graph_store.config.port,
            database=self.config.graph_store.config.database,
            user=self.config.graph_store.config.username,
            password=self.config.graph_store.config.password
        )
        self.connection.autocommit = True
        
        # Initialize Apache AGE
        age.setUpAge(self.connection, self.config.graph_store.config.graph_name)
        
        self.graph_name = self.config.graph_store.config.graph_name
        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider, self.config.embedder.config, self.config.vector_store.config
        )
        self.node_label = "__Entity__" if self.config.graph_store.config.base_label else ""
        
        # Initialize graph schema
        self._initialize_schema()
        
        # Default to openai if no specific provider is configured
        self.llm_provider = "openai"
        if self.config.llm and self.config.llm.provider:
            self.llm_provider = self.config.llm.provider
        if self.config.graph_store and self.config.graph_store.llm and self.config.graph_store.llm.provider:
            self.llm_provider = self.config.graph_store.llm.provider

        # Get LLM config with proper null checks
        llm_config = None
        if self.config.graph_store and self.config.graph_store.llm and hasattr(self.config.graph_store.llm, "config"):
            llm_config = self.config.graph_store.llm.config
        elif hasattr(self.config.llm, "config"):
            llm_config = self.config.llm.config
        self.llm = LlmFactory.create(self.llm_provider, llm_config)
        self.user_id = None
        self.threshold = 0.7

    def _initialize_schema(self):
        """Initialize the Apache AGE graph schema."""
        try:
            with self.connection.cursor() as cursor:
                # Create the graph if it doesn't exist
                cursor.execute(f"SELECT create_graph('{self.graph_name}');")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                logger.error(f"Error creating graph: {e}")
                raise

    def _execute_cypher(self, cypher_query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query using Apache AGE."""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Convert parameters to AGE format if provided
                if parameters:
                    # Convert parameters to JSON string for AGE
                    param_str = json.dumps(parameters)
                    query = f"SELECT * FROM cypher('{self.graph_name}', $$ {cypher_query} $$, '{param_str}') as (result agtype);"
                else:
                    query = f"SELECT * FROM cypher('{self.graph_name}', $$ {cypher_query} $$) as (result agtype);"
                
                cursor.execute(query)
                results = cursor.fetchall()
                
                # Convert AGE results to standard format
                converted_results = []
                for row in results:
                    if row['result']:
                        # Parse AGE result
                        result_data = age.age_to_dict(row['result'])
                        converted_results.append(result_data)
                
                return converted_results
        except Exception as e:
            logger.error(f"Error executing Cypher query: {e}")
            logger.error(f"Query: {cypher_query}")
            logger.error(f"Parameters: {parameters}")
            raise

    def add(self, data, filters):
        """
        Adds data to the graph.

        Args:
            data (str): The data to add to the graph.
            filters (dict): A dictionary containing filters to be applied during the addition.
        """
        entity_type_map = self._retrieve_nodes_from_data(data, filters)
        to_be_added = self._establish_nodes_relations_from_data(data, filters, entity_type_map)
        search_output = self._search_graph_db(node_list=list(entity_type_map.keys()), filters=filters)
        to_be_deleted = self._get_delete_entities_from_search_output(search_output, data, filters)

        deleted_entities = self._delete_entities(to_be_deleted, filters)
        added_entities = self._add_entities(to_be_added, filters, entity_type_map)

        return {"deleted_entities": deleted_entities, "added_entities": added_entities}

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
        entity_type_map = self._retrieve_nodes_from_data(query, filters)
        search_output = self._search_graph_db(node_list=list(entity_type_map.keys()), filters=filters)

        if not search_output:
            return []

        search_outputs_sequence = [
            [item["source"], item["relationship"], item["destination"]] for item in search_output
        ]
        bm25 = BM25Okapi(search_outputs_sequence)

        tokenized_query = query.split(" ")
        reranked_results = bm25.get_top_n(tokenized_query, search_outputs_sequence, n=5)

        search_results = []
        for item in reranked_results:
            search_results.append({"source": item[0], "relationship": item[1], "destination": item[2]})

        logger.info(f"Returned {len(search_results)} search results")

        return search_results

    def delete_all(self, filters):
        """Delete all nodes and relationships for a user or specific agent."""
        # Build node properties for filtering
        where_conditions = ["n.user_id = $user_id"]
        if filters.get("agent_id"):
            where_conditions.append("n.agent_id = $agent_id")
        if filters.get("run_id"):
            where_conditions.append("n.run_id = $run_id")
        where_clause = " AND ".join(where_conditions)

        if self.node_label:
            cypher = f"""
            MATCH (n:{self.node_label})
            WHERE {where_clause}
            DETACH DELETE n
            """
        else:
            cypher = f"""
            MATCH (n)
            WHERE {where_clause}
            DETACH DELETE n
            """
        
        params = {"user_id": filters["user_id"]}
        if filters.get("agent_id"):
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            params["run_id"] = filters["run_id"]
            
        self._execute_cypher(cypher, params)

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
        params = {"user_id": filters["user_id"], "limit": limit}

        # Build node properties based on filters
        where_conditions = ["n.user_id = $user_id", "m.user_id = $user_id"]
        if filters.get("agent_id"):
            where_conditions.extend(["n.agent_id = $agent_id", "m.agent_id = $agent_id"])
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            where_conditions.extend(["n.run_id = $run_id", "m.run_id = $run_id"])
            params["run_id"] = filters["run_id"]
        where_clause = " AND ".join(where_conditions)

        if self.node_label:
            query = f"""
            MATCH (n:{self.node_label})-[r]->(m:{self.node_label})
            WHERE {where_clause}
            RETURN n.name AS source, type(r) AS relationship, m.name AS target
            LIMIT $limit
            """
        else:
            query = f"""
            MATCH (n)-[r]->(m)
            WHERE {where_clause}
            RETURN n.name AS source, type(r) AS relationship, m.name AS target
            LIMIT $limit
            """
        
        results = self._execute_cypher(query, params)

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

    def _retrieve_nodes_from_data(self, data, filters):
        """Extracts all the entities mentioned in the query."""
        _tools = [EXTRACT_ENTITIES_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [EXTRACT_ENTITIES_STRUCT_TOOL]
        search_results = self.llm.generate_response(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a smart assistant who understands entities and their types in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use {filters['user_id']} as the source entity. Extract all the entities from the text. ***DO NOT*** answer the question itself if the given text is a question.",
                },
                {"role": "user", "content": data},
            ],
            tools=_tools,
        )

        entity_type_map = {}

        try:
            for tool_call in search_results["tool_calls"]:
                if tool_call["name"] != "extract_entities":
                    continue
                for item in tool_call["arguments"]["entities"]:
                    entity_type_map[item["entity"]] = item["entity_type"]
        except Exception as e:
            logger.exception(
                f"Error in search tool: {e}, llm_provider={self.llm_provider}, search_results={search_results}"
            )

        entity_type_map = {k.lower().replace(" ", "_"): v.lower().replace(" ", "_") for k, v in entity_type_map.items()}
        logger.debug(f"Entity type map: {entity_type_map}\n search_results={search_results}")
        return entity_type_map

    def _establish_nodes_relations_from_data(self, data, filters, entity_type_map):
        """Establish relations among the extracted nodes."""

        # Compose user identification string for prompt
        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        if self.config.graph_store.custom_prompt:
            system_content = EXTRACT_RELATIONS_PROMPT.replace("USER_ID", user_identity)
            # Add the custom prompt line if configured
            system_content = system_content.replace("CUSTOM_PROMPT", f"4. {self.config.graph_store.custom_prompt}")
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": data},
            ]
        else:
            system_content = EXTRACT_RELATIONS_PROMPT.replace("USER_ID", user_identity)
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"List of entities: {list(entity_type_map.keys())}. \n\nText: {data}"},
            ]

        _tools = [RELATIONS_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [RELATIONS_STRUCT_TOOL]

        extracted_entities = self.llm.generate_response(
            messages=messages,
            tools=_tools,
        )

        entities = []
        if extracted_entities.get("tool_calls"):
            entities = extracted_entities["tool_calls"][0].get("arguments", {}).get("entities", [])

        entities = self._remove_spaces_from_entities(entities)
        logger.debug(f"Extracted entities: {entities}")
        return entities

    def _search_graph_db(self, node_list, filters, limit=100):
        """Search similar nodes among and their respective incoming and outgoing relations."""
        result_relations = []

        # Build node properties for filtering
        where_conditions = ["n.user_id = $user_id"]
        if filters.get("agent_id"):
            where_conditions.append("n.agent_id = $agent_id")
        if filters.get("run_id"):
            where_conditions.append("n.run_id = $run_id")
        where_clause = " AND ".join(where_conditions)

        for node in node_list:
            n_embedding = self.embedding_model.embed(node)

            # Apache AGE doesn't have built-in vector similarity functions like Neo4j
            # We'll need to implement a workaround by fetching nodes and computing similarity in Python
            if self.node_label:
                cypher_query = f"""
                MATCH (n:{self.node_label})
                WHERE {where_clause} AND n.embedding IS NOT NULL
                RETURN n, id(n) as node_id
                """
            else:
                cypher_query = f"""
                MATCH (n)
                WHERE {where_clause} AND n.embedding IS NOT NULL
                RETURN n, id(n) as node_id
                """

            params = {
                "user_id": filters["user_id"],
            }
            if filters.get("agent_id"):
                params["agent_id"] = filters["agent_id"]
            if filters.get("run_id"):
                params["run_id"] = filters["run_id"]

            nodes = self._execute_cypher(cypher_query, params)

            # Compute similarity in Python and filter
            similar_nodes = []
            for node_result in nodes:
                node_data = node_result["n"]
                if "embedding" in node_data:
                    # Compute cosine similarity
                    similarity = self._compute_cosine_similarity(n_embedding, node_data["embedding"])
                    if similarity >= self.threshold:
                        similar_nodes.append({
                            "node": node_data,
                            "node_id": node_result["node_id"],
                            "similarity": similarity
                        })

            # Sort by similarity and get relationships
            similar_nodes.sort(key=lambda x: x["similarity"], reverse=True)

            for similar_node in similar_nodes[:limit]:
                node_id = similar_node["node_id"]

                # Get outgoing relationships
                if self.node_label:
                    rel_query = f"""
                    MATCH (n:{self.node_label})-[r]->(m:{self.node_label})
                    WHERE id(n) = $node_id AND m.user_id = $user_id
                    RETURN n.name AS source, id(n) AS source_id, type(r) AS relationship,
                           id(r) AS relation_id, m.name AS destination, id(m) AS destination_id
                    UNION
                    MATCH (n:{self.node_label})<-[r]-(m:{self.node_label})
                    WHERE id(n) = $node_id AND m.user_id = $user_id
                    RETURN m.name AS source, id(m) AS source_id, type(r) AS relationship,
                           id(r) AS relation_id, n.name AS destination, id(n) AS destination_id
                    """
                else:
                    rel_query = f"""
                    MATCH (n)-[r]->(m)
                    WHERE id(n) = $node_id AND m.user_id = $user_id
                    RETURN n.name AS source, id(n) AS source_id, type(r) AS relationship,
                           id(r) AS relation_id, m.name AS destination, id(m) AS destination_id
                    UNION
                    MATCH (n)<-[r]-(m)
                    WHERE id(n) = $node_id AND m.user_id = $user_id
                    RETURN m.name AS source, id(m) AS source_id, type(r) AS relationship,
                           id(r) AS relation_id, n.name AS destination, id(n) AS destination_id
                    """

                rel_params = {
                    "node_id": node_id,
                    "user_id": filters["user_id"]
                }
                if filters.get("agent_id"):
                    rel_params["agent_id"] = filters["agent_id"]
                if filters.get("run_id"):
                    rel_params["run_id"] = filters["run_id"]

                relationships = self._execute_cypher(rel_query, rel_params)

                for rel in relationships:
                    rel["similarity"] = similar_node["similarity"]
                    result_relations.append(rel)

        return result_relations

    def _compute_cosine_similarity(self, vec1, vec2):
        """Compute cosine similarity between two vectors."""
        import numpy as np

        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0

        return dot_product / (norm1 * norm2)

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """Get the entities to be deleted from the search output."""
        search_output_string = format_entities(search_output)

        # Compose user identification string for prompt
        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        system_prompt, user_prompt = get_delete_messages(search_output_string, data, user_identity)

        _tools = [DELETE_MEMORY_TOOL_GRAPH]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [
                DELETE_MEMORY_STRUCT_TOOL_GRAPH,
            ]

        memory_updates = self.llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=_tools,
        )

        to_be_deleted = []
        for item in memory_updates.get("tool_calls", []):
            if item.get("name") == "delete_graph_memory":
                to_be_deleted.append(item.get("arguments"))
        # Clean entities formatting
        to_be_deleted = self._remove_spaces_from_entities(to_be_deleted)
        logger.debug(f"Deleted relationships: {to_be_deleted}")
        return to_be_deleted

    def _delete_entities(self, to_be_deleted, filters):
        """Delete the entities from the graph."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id", None)
        run_id = filters.get("run_id", None)
        results = []

        for item in to_be_deleted:
            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            params = {
                "source_name": source,
                "dest_name": destination,
                "user_id": user_id,
            }

            if agent_id:
                params["agent_id"] = agent_id
            if run_id:
                params["run_id"] = run_id

            # Build node properties for filtering
            source_conditions = ["n.name = $source_name", "n.user_id = $user_id"]
            dest_conditions = ["m.name = $dest_name", "m.user_id = $user_id"]
            if agent_id:
                source_conditions.append("n.agent_id = $agent_id")
                dest_conditions.append("m.agent_id = $agent_id")
            if run_id:
                source_conditions.append("n.run_id = $run_id")
                dest_conditions.append("m.run_id = $run_id")
            source_where = " AND ".join(source_conditions)
            dest_where = " AND ".join(dest_conditions)

            # Delete the specific relationship between nodes
            if self.node_label:
                cypher = f"""
                MATCH (n:{self.node_label})-[r:{relationship}]->(m:{self.node_label})
                WHERE {source_where} AND {dest_where}
                DELETE r
                RETURN n.name AS source, m.name AS target, type(r) AS relationship
                """
            else:
                cypher = f"""
                MATCH (n)-[r:{relationship}]->(m)
                WHERE {source_where} AND {dest_where}
                DELETE r
                RETURN n.name AS source, m.name AS target, type(r) AS relationship
                """

            result = self._execute_cypher(cypher, params)
            results.append(result)

        return results

    def _add_entities(self, to_be_added, filters, entity_type_map):
        """Add the new entities to the graph. Merge the nodes if they already exist."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id", None)
        run_id = filters.get("run_id", None)
        results = []

        for item in to_be_added:
            # entities
            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            # types
            source_type = entity_type_map.get(source, "__User__")
            destination_type = entity_type_map.get(destination, "__User__")

            # embeddings
            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            # search for the nodes with the closest embeddings
            source_node_search_result = self._search_source_node(source_embedding, filters, threshold=0.9)
            destination_node_search_result = self._search_destination_node(dest_embedding, filters, threshold=0.9)

            # Build dynamic properties for nodes
            source_props = ["name: $source_name", "user_id: $user_id"]
            dest_props = ["name: $dest_name", "user_id: $user_id"]
            if agent_id:
                source_props.append("agent_id: $agent_id")
                dest_props.append("agent_id: $agent_id")
            if run_id:
                source_props.append("run_id: $run_id")
                dest_props.append("run_id: $run_id")
            source_props_str = ", ".join(source_props)
            dest_props_str = ", ".join(dest_props)

            # Determine node labels
            if self.node_label:
                source_label = f":{self.node_label}"
                destination_label = f":{self.node_label}"
                source_extra_set = f", source:`{source_type}`"
                destination_extra_set = f", destination:`{destination_type}`"
            else:
                source_label = f":`{source_type}`"
                destination_label = f":`{destination_type}`"
                source_extra_set = ""
                destination_extra_set = ""

            # Create the Cypher query based on existing nodes
            if not destination_node_search_result and source_node_search_result:
                # Source exists, create destination
                cypher = f"""
                MATCH (source)
                WHERE id(source) = $source_id
                SET source.mentions = coalesce(source.mentions, 0) + 1
                WITH source
                MERGE (destination{destination_label} {{{dest_props_str}}})
                ON CREATE SET
                    destination.created = timestamp(),
                    destination.mentions = 1,
                    destination.embedding = $destination_embedding
                    {destination_extra_set}
                ON MATCH SET
                    destination.mentions = coalesce(destination.mentions, 0) + 1
                WITH source, destination
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET
                    r.created = timestamp(),
                    r.mentions = 1
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                """

                params = {
                    "source_id": source_node_search_result[0]["node_id"],
                    "dest_name": destination,
                    "destination_embedding": dest_embedding,
                    "user_id": user_id,
                }
                if agent_id:
                    params["agent_id"] = agent_id
                if run_id:
                    params["run_id"] = run_id

            elif destination_node_search_result and not source_node_search_result:
                # Destination exists, create source
                cypher = f"""
                MATCH (destination)
                WHERE id(destination) = $destination_id
                SET destination.mentions = coalesce(destination.mentions, 0) + 1
                WITH destination
                MERGE (source{source_label} {{{source_props_str}}})
                ON CREATE SET
                    source.created = timestamp(),
                    source.mentions = 1,
                    source.embedding = $source_embedding
                    {source_extra_set}
                ON MATCH SET
                    source.mentions = coalesce(source.mentions, 0) + 1
                WITH source, destination
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET
                    r.created = timestamp(),
                    r.mentions = 1
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                """

                params = {
                    "destination_id": destination_node_search_result[0]["node_id"],
                    "source_name": source,
                    "source_embedding": source_embedding,
                    "user_id": user_id,
                }
                if agent_id:
                    params["agent_id"] = agent_id
                if run_id:
                    params["run_id"] = run_id

            elif source_node_search_result and destination_node_search_result:
                # Both exist, just create relationship
                cypher = f"""
                MATCH (source)
                WHERE id(source) = $source_id
                SET source.mentions = coalesce(source.mentions, 0) + 1
                WITH source
                MATCH (destination)
                WHERE id(destination) = $destination_id
                SET destination.mentions = coalesce(destination.mentions, 0) + 1
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET
                    r.created_at = timestamp(),
                    r.updated_at = timestamp(),
                    r.mentions = 1
                ON MATCH SET r.mentions = coalesce(r.mentions, 0) + 1
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                """

                params = {
                    "source_id": source_node_search_result[0]["node_id"],
                    "destination_id": destination_node_search_result[0]["node_id"],
                    "user_id": user_id,
                }
                if agent_id:
                    params["agent_id"] = agent_id
                if run_id:
                    params["run_id"] = run_id

            else:
                # Neither exists, create both
                cypher = f"""
                MERGE (source{source_label} {{{source_props_str}}})
                ON CREATE SET source.created = timestamp(),
                            source.mentions = 1,
                            source.embedding = $source_embedding
                            {source_extra_set}
                ON MATCH SET source.mentions = coalesce(source.mentions, 0) + 1
                WITH source
                MERGE (destination{destination_label} {{{dest_props_str}}})
                ON CREATE SET destination.created = timestamp(),
                            destination.mentions = 1,
                            destination.embedding = $dest_embedding
                            {destination_extra_set}
                ON MATCH SET destination.mentions = coalesce(destination.mentions, 0) + 1
                WITH source, destination
                MERGE (source)-[rel:{relationship}]->(destination)
                ON CREATE SET rel.created = timestamp(), rel.mentions = 1
                ON MATCH SET rel.mentions = coalesce(rel.mentions, 0) + 1
                RETURN source.name AS source, type(rel) AS relationship, destination.name AS target
                """

                params = {
                    "source_name": source,
                    "dest_name": destination,
                    "source_embedding": source_embedding,
                    "dest_embedding": dest_embedding,
                    "user_id": user_id,
                }
                if agent_id:
                    params["agent_id"] = agent_id
                if run_id:
                    params["run_id"] = run_id

            result = self._execute_cypher(cypher, params)
            results.append(result)

        return results

    def _remove_spaces_from_entities(self, entity_list):
        for item in entity_list:
            item["source"] = item["source"].lower().replace(" ", "_")
            # Use the sanitization function for relationships to handle special characters
            item["relationship"] = sanitize_relationship_for_cypher(item["relationship"].lower().replace(" ", "_"))
            item["destination"] = item["destination"].lower().replace(" ", "_")
        return entity_list

    def _search_source_node(self, source_embedding, filters, threshold=0.9):
        # Build WHERE conditions
        where_conditions = ["source_candidate.embedding IS NOT NULL", "source_candidate.user_id = $user_id"]
        if filters.get("agent_id"):
            where_conditions.append("source_candidate.agent_id = $agent_id")
        if filters.get("run_id"):
            where_conditions.append("source_candidate.run_id = $run_id")
        where_clause = " AND ".join(where_conditions)

        if self.node_label:
            cypher = f"""
                MATCH (source_candidate:{self.node_label})
                WHERE {where_clause}
                RETURN source_candidate, id(source_candidate) as node_id
                """
        else:
            cypher = f"""
                MATCH (source_candidate)
                WHERE {where_clause}
                RETURN source_candidate, id(source_candidate) as node_id
                """

        params = {
            "user_id": filters["user_id"],
        }
        if filters.get("agent_id"):
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            params["run_id"] = filters["run_id"]

        candidates = self._execute_cypher(cypher, params)

        # Compute similarity and filter
        best_match = None
        best_similarity = 0

        for candidate in candidates:
            node_data = candidate["source_candidate"]
            if "embedding" in node_data:
                similarity = self._compute_cosine_similarity(source_embedding, node_data["embedding"])
                if similarity >= threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = candidate

        return [best_match] if best_match else []

    def _search_destination_node(self, destination_embedding, filters, threshold=0.9):
        # Build WHERE conditions
        where_conditions = ["destination_candidate.embedding IS NOT NULL", "destination_candidate.user_id = $user_id"]
        if filters.get("agent_id"):
            where_conditions.append("destination_candidate.agent_id = $agent_id")
        if filters.get("run_id"):
            where_conditions.append("destination_candidate.run_id = $run_id")
        where_clause = " AND ".join(where_conditions)

        if self.node_label:
            cypher = f"""
                MATCH (destination_candidate:{self.node_label})
                WHERE {where_clause}
                RETURN destination_candidate, id(destination_candidate) as node_id
                """
        else:
            cypher = f"""
                MATCH (destination_candidate)
                WHERE {where_clause}
                RETURN destination_candidate, id(destination_candidate) as node_id
                """

        params = {
            "user_id": filters["user_id"],
        }
        if filters.get("agent_id"):
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            params["run_id"] = filters["run_id"]

        candidates = self._execute_cypher(cypher, params)

        # Compute similarity and filter
        best_match = None
        best_similarity = 0

        for candidate in candidates:
            node_data = candidate["destination_candidate"]
            if "embedding" in node_data:
                similarity = self._compute_cosine_similarity(destination_embedding, node_data["embedding"])
                if similarity >= threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = candidate

        return [best_match] if best_match else []

    def reset(self):
        """Reset the graph by clearing all nodes and relationships."""
        logger.warning("Clearing graph...")
        cypher_query = """
        MATCH (n) DETACH DELETE n
        """
        return self._execute_cypher(cypher_query)

    def __del__(self):
        """Close the database connection when the object is destroyed."""
        if hasattr(self, 'connection') and self.connection:
            self.connection.close()
