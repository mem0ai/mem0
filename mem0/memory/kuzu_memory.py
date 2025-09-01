import logging

from mem0.memory.utils import format_entities

try:
    import kuzu
except ImportError:
    raise ImportError("kuzu is not installed. Please install it using pip install kuzu")

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

        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider,
            self.config.embedder.config,
            self.config.vector_store.config,
        )
        self.embedding_dims = self.embedding_model.config.embedding_dims

        self.db = kuzu.Database(self.config.graph_store.config.db)
        self.graph = kuzu.Connection(self.db)

        self.node_label = ":Entity"
        self.rel_label = ":CONNECTED_TO"
        self.kuzu_create_schema()

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

    def kuzu_create_schema(self):
        self.kuzu_execute(
            """
            CREATE NODE TABLE IF NOT EXISTS Entity(
                id SERIAL PRIMARY KEY,
                user_id STRING,
                agent_id STRING,
                run_id STRING,
                name STRING,
                mentions INT64,
                created TIMESTAMP,
                embedding FLOAT[]);
            """
        )
        self.kuzu_execute(
            """
            CREATE REL TABLE IF NOT EXISTS CONNECTED_TO(
                FROM Entity TO Entity,
                name STRING,
                mentions INT64,
                created TIMESTAMP,
                updated TIMESTAMP
            );
            """
        )

    def kuzu_execute(self, query, parameters=None):
        results = self.graph.execute(query, parameters)
        return list(results.rows_as_dict())

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

    def search(self, query, filters, limit=5):
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
        reranked_results = bm25.get_top_n(tokenized_query, search_outputs_sequence, n=limit)

        search_results = []
        for item in reranked_results:
            search_results.append({"source": item[0], "relationship": item[1], "destination": item[2]})

        logger.info(f"Returned {len(search_results)} search results")

        return search_results

    def delete_all(self, filters):
        # Build node properties for filtering
        node_props = ["user_id: $user_id"]
        if filters.get("agent_id"):
            node_props.append("agent_id: $agent_id")
        if filters.get("run_id"):
            node_props.append("run_id: $run_id")
        node_props_str = ", ".join(node_props)

        cypher = f"""
        MATCH (n {self.node_label} {{{node_props_str}}})
        DETACH DELETE n
        """
        params = {"user_id": filters["user_id"]}
        if filters.get("agent_id"):
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            params["run_id"] = filters["run_id"]
        self.kuzu_execute(cypher, parameters=params)

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

        params = {
            "user_id": filters["user_id"],
            "limit": limit,
        }
        # Build node properties based on filters
        node_props = ["user_id: $user_id"]
        if filters.get("agent_id"):
            node_props.append("agent_id: $agent_id")
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            node_props.append("run_id: $run_id")
            params["run_id"] = filters["run_id"]
        node_props_str = ", ".join(node_props)

        query = f"""
        MATCH (n {self.node_label} {{{node_props_str}}})-[r]->(m {self.node_label} {{{node_props_str}}})
        RETURN
            n.name AS source,
            r.name AS relationship,
            m.name AS target
        LIMIT $limit
        """
        results = self.kuzu_execute(query, parameters=params)

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

    def _search_graph_db(self, node_list, filters, limit=100, threshold=None):
        """Search similar nodes among and their respective incoming and outgoing relations."""
        result_relations = []

        params = {
            "threshold": threshold if threshold else self.threshold,
            "user_id": filters["user_id"],
            "limit": limit,
        }
        # Build node properties for filtering
        node_props = ["user_id: $user_id"]
        if filters.get("agent_id"):
            node_props.append("agent_id: $agent_id")
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            node_props.append("run_id: $run_id")
            params["run_id"] = filters["run_id"]
        node_props_str = ", ".join(node_props)

        for node in node_list:
            n_embedding = self.embedding_model.embed(node)
            params["n_embedding"] = n_embedding

            results = []
            for match_fragment in [
                f"(n)-[r]->(m {self.node_label} {{{node_props_str}}}) WITH n as src, r, m as dst, similarity",
                f"(m {self.node_label} {{{node_props_str}}})-[r]->(n) WITH m as src, r, n as dst, similarity"
            ]:
                results.extend(self.kuzu_execute(
                    f"""
                    MATCH (n {self.node_label} {{{node_props_str}}})
                    WHERE n.embedding IS NOT NULL
                    WITH n, array_cosine_similarity(n.embedding, CAST($n_embedding,'FLOAT[{self.embedding_dims}]')) AS similarity
                    WHERE similarity >= CAST($threshold, 'DOUBLE')
                    MATCH {match_fragment}
                    RETURN
                        src.name AS source,
                        id(src) AS source_id,
                        r.name AS relationship,
                        id(r) AS relation_id,
                        dst.name AS destination,
                        id(dst) AS destination_id,
                        similarity
                    LIMIT $limit
                    """,
                    parameters=params))

            # Kuzu does not support sort/limit over unions. Do it manually for now.
            result_relations.extend(sorted(results, key=lambda x: x["similarity"], reverse=True)[:limit])

        return result_relations

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
                "relationship_name": relationship,
            }
            # Build node properties for filtering
            source_props = ["name: $source_name", "user_id: $user_id"]
            dest_props = ["name: $dest_name", "user_id: $user_id"]
            if agent_id:
                source_props.append("agent_id: $agent_id")
                dest_props.append("agent_id: $agent_id")
                params["agent_id"] = agent_id
            if run_id:
                source_props.append("run_id: $run_id")
                dest_props.append("run_id: $run_id")
                params["run_id"] = run_id
            source_props_str = ", ".join(source_props)
            dest_props_str = ", ".join(dest_props)

            # Delete the specific relationship between nodes
            cypher = f"""
            MATCH (n {self.node_label} {{{source_props_str}}})
            -[r {self.rel_label} {{name: $relationship_name}}]->
            (m {self.node_label} {{{dest_props_str}}})
            DELETE r
            RETURN
                n.name AS source,
                r.name AS relationship,
                m.name AS target
            """

            result = self.kuzu_execute(cypher, parameters=params)
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
            source_label = self.node_label

            destination = item["destination"]
            destination_label = self.node_label

            relationship = item["relationship"]
            relationship_label = self.rel_label

            # embeddings
            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            # search for the nodes with the closest embeddings
            source_node_search_result = self._search_source_node(source_embedding, filters, threshold=0.9)
            destination_node_search_result = self._search_destination_node(dest_embedding, filters, threshold=0.9)

            if not destination_node_search_result and source_node_search_result:
                params = {
                    "table_id": source_node_search_result[0]["id"]["table"],
                    "offset_id": source_node_search_result[0]["id"]["offset"],
                    "destination_name": destination,
                    "destination_embedding": dest_embedding,
                    "relationship_name": relationship,
                    "user_id": user_id,
                }
                # Build source MERGE properties
                merge_props = ["name: $destination_name", "user_id: $user_id"]
                if agent_id:
                    merge_props.append("agent_id: $agent_id")
                    params["agent_id"] = agent_id
                if run_id:
                    merge_props.append("run_id: $run_id")
                    params["run_id"] = run_id
                merge_props_str = ", ".join(merge_props)

                cypher = f"""
                MATCH (source)
                WHERE id(source) = internal_id($table_id, $offset_id)
                SET source.mentions = coalesce(source.mentions, 0) + 1
                WITH source
                MERGE (destination {destination_label} {{{merge_props_str}}})
                ON CREATE SET
                    destination.created = current_timestamp(),
                    destination.mentions = 1,
                    destination.embedding = CAST($destination_embedding,'FLOAT[{self.embedding_dims}]')
                ON MATCH SET
                    destination.mentions = coalesce(destination.mentions, 0) + 1,
                    destination.embedding = CAST($destination_embedding,'FLOAT[{self.embedding_dims}]')
                WITH source, destination
                MERGE (source)-[r {relationship_label} {{name: $relationship_name}}]->(destination)
                ON CREATE SET
                    r.created = current_timestamp(),
                    r.mentions = 1
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1
                RETURN
                    source.name AS source,
                    r.name AS relationship,
                    destination.name AS target
                """
            elif destination_node_search_result and not source_node_search_result:
                params = {
                    "table_id": destination_node_search_result[0]["id"]["table"],
                    "offset_id": destination_node_search_result[0]["id"]["offset"],
                    "source_name": source,
                    "source_embedding": source_embedding,
                    "user_id": user_id,
                    "relationship_name": relationship,
                }
                # Build source MERGE properties
                merge_props = ["name: $source_name", "user_id: $user_id"]
                if agent_id:
                    merge_props.append("agent_id: $agent_id")
                    params["agent_id"] = agent_id
                if run_id:
                    merge_props.append("run_id: $run_id")
                    params["run_id"] = run_id
                merge_props_str = ", ".join(merge_props)

                cypher = f"""
                MATCH (destination)
                WHERE id(destination) = internal_id($table_id, $offset_id)
                SET destination.mentions = coalesce(destination.mentions, 0) + 1
                WITH destination
                MERGE (source {source_label} {{{merge_props_str}}})
                ON CREATE SET
                source.created = current_timestamp(),
                source.mentions = 1,
                source.embedding = CAST($source_embedding,'FLOAT[{self.embedding_dims}]')
                ON MATCH SET
                source.mentions = coalesce(source.mentions, 0) + 1,
                source.embedding = CAST($source_embedding,'FLOAT[{self.embedding_dims}]')
                WITH source, destination
                MERGE (source)-[r {relationship_label} {{name: $relationship_name}}]->(destination)
                ON CREATE SET
                    r.created = current_timestamp(),
                    r.mentions = 1
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1
                RETURN
                    source.name AS source,
                    r.name AS relationship,
                    destination.name AS target
                """
            elif source_node_search_result and destination_node_search_result:
                cypher = f"""
                MATCH (source)
                WHERE id(source) = internal_id($src_table, $src_offset)
                SET source.mentions = coalesce(source.mentions, 0) + 1
                WITH source
                MATCH (destination)
                WHERE id(destination) = internal_id($dst_table, $dst_offset)
                SET destination.mentions = coalesce(destination.mentions, 0) + 1
                MERGE (source)-[r {relationship_label} {{name: $relationship_name}}]->(destination)
                ON CREATE SET
                    r.created = current_timestamp(),
                    r.updated = current_timestamp(),
                    r.mentions = 1
                ON MATCH SET r.mentions = coalesce(r.mentions, 0) + 1
                RETURN
                    source.name AS source,
                    r.name AS relationship,
                    destination.name AS target
                """

                params = {
                    "src_table": source_node_search_result[0]["id"]["table"],
                    "src_offset": source_node_search_result[0]["id"]["offset"],
                    "dst_table": destination_node_search_result[0]["id"]["table"],
                    "dst_offset": destination_node_search_result[0]["id"]["offset"],
                    "relationship_name": relationship,
                }
            else:
                params = {
                    "source_name": source,
                    "dest_name": destination,
                    "relationship_name": relationship,
                    "source_embedding": source_embedding,
                    "dest_embedding": dest_embedding,
                    "user_id": user_id,
                }
                # Build dynamic MERGE props for both source and destination
                source_props = ["name: $source_name", "user_id: $user_id"]
                dest_props = ["name: $dest_name", "user_id: $user_id"]
                if agent_id:
                    source_props.append("agent_id: $agent_id")
                    dest_props.append("agent_id: $agent_id")
                    params["agent_id"] = agent_id
                if run_id:
                    source_props.append("run_id: $run_id")
                    dest_props.append("run_id: $run_id")
                    params["run_id"] = run_id
                source_props_str = ", ".join(source_props)
                dest_props_str = ", ".join(dest_props)

                cypher = f"""
                MERGE (source {source_label} {{{source_props_str}}})
                ON CREATE SET
                    source.created = current_timestamp(),
                    source.mentions = 1,
                    source.embedding = CAST($source_embedding,'FLOAT[{self.embedding_dims}]')
                ON MATCH SET
                    source.mentions = coalesce(source.mentions, 0) + 1,
                    source.embedding = CAST($source_embedding,'FLOAT[{self.embedding_dims}]')
                WITH source
                MERGE (destination {destination_label} {{{dest_props_str}}})
                ON CREATE SET
                    destination.created = current_timestamp(),
                    destination.mentions = 1,
                    destination.embedding = CAST($dest_embedding,'FLOAT[{self.embedding_dims}]')
                ON MATCH SET
                    destination.mentions = coalesce(destination.mentions, 0) + 1,
                    destination.embedding = CAST($dest_embedding,'FLOAT[{self.embedding_dims}]')
                WITH source, destination
                MERGE (source)-[rel {relationship_label} {{name: $relationship_name}}]->(destination)
                ON CREATE SET
                    rel.created = current_timestamp(),
                    rel.mentions = 1
                ON MATCH SET
                    rel.mentions = coalesce(rel.mentions, 0) + 1
                RETURN
                    source.name AS source,
                    rel.name AS relationship,
                    destination.name AS target
                """

            result = self.kuzu_execute(cypher, parameters=params)
            results.append(result)

        return results

    def _remove_spaces_from_entities(self, entity_list):
        for item in entity_list:
            item["source"] = item["source"].lower().replace(" ", "_")
            item["relationship"] = item["relationship"].lower().replace(" ", "_")
            item["destination"] = item["destination"].lower().replace(" ", "_")
        return entity_list

    def _search_source_node(self, source_embedding, filters, threshold=0.9):
        params = {
            "source_embedding": source_embedding,
            "user_id": filters["user_id"],
            "threshold": threshold,
        }
        where_conditions = ["source_candidate.embedding IS NOT NULL", "source_candidate.user_id = $user_id"]
        if filters.get("agent_id"):
            where_conditions.append("source_candidate.agent_id = $agent_id")
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            where_conditions.append("source_candidate.run_id = $run_id")
            params["run_id"] = filters["run_id"]
        where_clause = " AND ".join(where_conditions)

        cypher = f"""
            MATCH (source_candidate {self.node_label})
            WHERE {where_clause}

            WITH source_candidate,
            array_cosine_similarity(source_candidate.embedding, CAST($source_embedding,'FLOAT[{self.embedding_dims}]')) AS source_similarity

            WHERE source_similarity >= $threshold

            WITH source_candidate, source_similarity
            ORDER BY source_similarity DESC
            LIMIT 2

            RETURN id(source_candidate) as id, source_similarity
            """

        return self.kuzu_execute(cypher, parameters=params)

    def _search_destination_node(self, destination_embedding, filters, threshold=0.9):
        params = {
            "destination_embedding": destination_embedding,
            "user_id": filters["user_id"],
            "threshold": threshold,
        }
        where_conditions = ["destination_candidate.embedding IS NOT NULL", "destination_candidate.user_id = $user_id"]
        if filters.get("agent_id"):
            where_conditions.append("destination_candidate.agent_id = $agent_id")
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            where_conditions.append("destination_candidate.run_id = $run_id")
            params["run_id"] = filters["run_id"]
        where_clause = " AND ".join(where_conditions)

        cypher = f"""
            MATCH (destination_candidate {self.node_label})
            WHERE {where_clause}

            WITH destination_candidate,
            array_cosine_similarity(destination_candidate.embedding, CAST($destination_embedding,'FLOAT[{self.embedding_dims}]')) AS destination_similarity

            WHERE destination_similarity >= $threshold

            WITH destination_candidate, destination_similarity
            ORDER BY destination_similarity DESC
            LIMIT 2

            RETURN id(destination_candidate) as id, destination_similarity
            """

        return self.kuzu_execute(cypher, parameters=params)

    # Reset is not defined in base.py
    def reset(self):
        """Reset the graph by clearing all nodes and relationships."""
        logger.warning("Clearing graph...")
        cypher_query = """
        MATCH (n) DETACH DELETE n
        """
        return self.kuzu_execute(cypher_query)
