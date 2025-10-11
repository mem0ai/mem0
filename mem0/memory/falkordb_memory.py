import logging

from mem0.memory.utils import format_entities

try:
    import falkordb
except ImportError:
    raise ImportError(
        "falkordb is not installed. Please install it using pip install falkordb"
    )

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    raise ImportError(
        "rank_bm25 is not installed. Please install it using pip install rank-bm25"
    )

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

        # Connect to FalkorDB
        self.db = falkordb.FalkorDB(
            host=self.config.graph_store.config.host,
            port=self.config.graph_store.config.port,
            username=self.config.graph_store.config.username,
            password=self.config.graph_store.config.password,
        )
        self.graph = self.db.select_graph(self.config.graph_store.config.graph_name)

        self.node_label = ":Entity"
        self.rel_label = ":CONNECTED_TO"
        self.falkordb_create_schema()

        # Default to openai if no specific provider is configured
        self.llm_provider = "openai"
        if self.config.llm and self.config.llm.provider:
            self.llm_provider = self.config.llm.provider
        if (
            self.config.graph_store
            and self.config.graph_store.llm
            and self.config.graph_store.llm.provider
        ):
            self.llm_provider = self.config.graph_store.llm.provider
        # Get LLM config with proper null checks
        llm_config = None
        if (
            self.config.graph_store
            and self.config.graph_store.llm
            and hasattr(self.config.graph_store.llm, "config")
        ):
            llm_config = self.config.graph_store.llm.config
        elif hasattr(self.config.llm, "config"):
            llm_config = self.config.llm.config
        self.llm = LlmFactory.create(self.llm_provider, llm_config)

        self.user_id = None
        self.threshold = 0.7

    def falkordb_create_schema(self):
        """Create indexes for FalkorDB to optimize queries."""
        # Create vector index for Entity nodes
        try:
            self.graph.create_node_vector_index(
                "Entity",
                "embedding",
                dim=self.embedding_dims,
                similarity_function="cosine",
            )
        except Exception as e:
            # Index might already exist
            logger.debug("Vector index creation warning: %s", e)

        # Create range index for user_id for better performance
        try:
            self.graph.create_node_range_index("Entity", "user_id")
        except Exception as e:
            logger.debug("Range index creation warning: %s", e)

    def falkordb_execute(self, query, parameters=None):
        """Execute a Cypher query on FalkorDB and return results."""
        result = self.graph.query(query, parameters or {})

        if not result.result_set:
            return []

        # Get column names from header
        header = result.header
        results = []

        for row in result.result_set:
            if len(header) == 1 and len(row) == 1:
                col_name = header[0][1]
                # Single scalar value
                if isinstance(row[0], (str, int, float, bool)):
                    results.append({col_name: row[0]})
                else:
                    # For complex objects, try to get properties or return as-is
                    try:
                        results.append(
                            {
                                col_name: (
                                    row[0].properties
                                    if hasattr(row[0], "properties")
                                    else row[0]
                                )
                            }
                        )
                    except (AttributeError, TypeError):
                        results.append({col_name: row[0]})
            else:
                # Multiple columns, zip header with row values
                row_dict = {}
                for col_name, value in zip(header, row):
                    # Handle complex objects (nodes, relationships) by extracting header and value
                    row_dict[col_name[1]] = value
                results.append(row_dict)

        return results

    def add(self, data, filters):
        """
        Adds data to the graph.

        Args:
            data (str): The data to add to the graph.
            filters (dict): A dictionary containing filters to be applied during the addition.
        """
        entity_type_map = self._retrieve_nodes_from_data(data, filters)
        to_be_added = self._establish_nodes_relations_from_data(
            data, filters, entity_type_map
        )
        search_output = self._search_graph_db(
            node_list=list(entity_type_map.keys()), filters=filters
        )
        to_be_deleted = self._get_delete_entities_from_search_output(
            search_output, data, filters
        )

        deleted_entities = self._delete_entities(to_be_deleted, filters)
        added_entities = self._add_entities(to_be_added, filters, entity_type_map)

        return {"deleted_entities": deleted_entities, "added_entities": added_entities}

    def search(self, query, filters, limit=5):
        """
        Search for memories and related graph data.

        Args:
            query (str): Query to search for.
            filters (dict): A dictionary containing filters to be applied during the search.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 5.

        Returns:
            list: List of search results containing graph data based on the query.
        """
        entity_type_map = self._retrieve_nodes_from_data(query, filters)
        search_output = self._search_graph_db(
            node_list=list(entity_type_map.keys()), filters=filters, limit=limit
        )

        if not search_output:
            return []

        search_outputs_sequence = [
            [item["source"], item["relationship"], item["destination"]]
            for item in search_output
        ]
        bm25 = BM25Okapi(search_outputs_sequence)

        tokenized_query = query.split(" ")
        bm25_scores = bm25.get_scores(tokenized_query)

        # Convert to list of "src -- rel -- dst" lines
        formatted_results = format_entities(search_output).splitlines()
        sorted_results = [
            x
            for _, x in sorted(
                zip(bm25_scores, formatted_results), key=lambda x: x[0], reverse=True
            )
        ]
        return sorted_results[:limit]

    def delete_all(self, filters):
        """Delete all nodes and relationships for a user or specific agent."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")
        run_id = filters.get("run_id")

        # Build filter conditions
        conditions = ["user_id: $user_id"]
        params = {"user_id": user_id}

        if agent_id:
            conditions.append("agent_id: $agent_id")
            params["agent_id"] = agent_id
        if run_id:
            conditions.append("run_id: $run_id")
            params["run_id"] = run_id

        conditions_str = ", ".join(conditions)

        cypher_query = f"""
        MATCH (n:Entity {{{conditions_str}}})
        DETACH DELETE n
        """

        return self.falkordb_execute(cypher_query, parameters=params)

    def get_all(self, filters, limit=100):
        """Get all relationships matching the filters."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")
        run_id = filters.get("run_id")

        # Build node properties for filtering
        node_props = ["user_id: $user_id"]
        params = {"user_id": user_id, "limit": limit}

        if agent_id:
            node_props.append("agent_id: $agent_id")
            params["agent_id"] = agent_id
        if run_id:
            node_props.append("run_id: $run_id")
            params["run_id"] = run_id

        node_props_str = ", ".join(node_props)

        query = f"""
        MATCH (source:Entity {{{node_props_str}}})
        -[r:CONNECTED_TO]->(target:Entity {{{node_props_str}}})
        RETURN source.name AS source,
               r.name AS relationship,
               target.name AS target
        LIMIT $limit
        """

        results = self.falkordb_execute(query, parameters=params)

        final_results = []
        for result in results:
            final_results.append(
                {
                    "source": result["source"],
                    "relationship": result["relationship"],
                    "target": result["target"],
                }
            )

        logger.info("Retrieved %d relationships", len(final_results))

        return final_results

    def _retrieve_nodes_from_data(self, data, filters):
        """Extracts all the entities mentioned in the query."""
        _tools = [EXTRACT_ENTITIES_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [EXTRACT_ENTITIES_STRUCT_TOOL]
        # Build the system prompt in multiple shorter string literals to avoid overly long lines
        user_id = filters["user_id"]
        system_content = (
            "You are a smart assistant who understands entities and their types in a given text. "
            "If user message contains self reference such as 'I', 'me', 'my' etc. then use "
            f"{user_id} as the source entity. Extract all the entities from the text. "
            "***DO NOT*** answer the question itself if the given text is a question."
        )

        search_results = self.llm.generate_response(
            messages=[
                {"role": "system", "content": system_content},
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
                "Error in search tool: %s, llm_provider=%s, search_results=%s",
                e, self.llm_provider, search_results
            )

        entity_type_map = {
            k.lower().replace(" ", "_"): v.lower().replace(" ", "_")
            for k, v in entity_type_map.items()
        }
        logger.debug(
            "Entity type map: %s\n search_results=%s",
            entity_type_map, search_results
        )
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
            system_content = system_content.replace(
                "CUSTOM_PROMPT", f"4. {self.config.graph_store.custom_prompt}"
            )
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": data},
            ]
        else:
            system_content = EXTRACT_RELATIONS_PROMPT.replace("USER_ID", user_identity)
            user_content = (
                "List of entities: "
                + str(list(entity_type_map.keys()))
                + ". \n\nText: "
                + data
            )

            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
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
            entities = (
                extracted_entities["tool_calls"][0]
                .get("arguments", {})
                .get("entities", [])
            )

        entities = self._remove_spaces_from_entities(entities)
        logger.debug("Extracted entities: %s", entities)
        return entities

    def _search_graph_db(self, node_list, filters, limit=100, threshold=None):
        """Search similar nodes among and their respective incoming and outgoing relations."""
        result_relations = []

        user_id = filters["user_id"]

        # Build filter conditions for additional filters
        filter_conditions = ["n.user_id = $user_id"]
        params = {"user_id": user_id}

        if filters.get("agent_id"):
            filter_conditions.append("n.agent_id = $agent_id")
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            filter_conditions.append("n.run_id = $run_id")
            params["run_id"] = filters["run_id"]

        filter_where = " AND ".join(filter_conditions)

        for node in node_list:
            n_embedding = self.embedding_model.embed(node)

            # Use FalkorDB's vector index query procedure
            # Query similar nodes and their relationships
            query = f"""
            CALL db.idx.vector.queryNodes('Entity', 'embedding', $limit, vecf32($n_embedding)) YIELD node AS n, score
            WHERE {filter_where}
            MATCH (n)-[r:CONNECTED_TO]-(connected:Entity)
            WHERE connected.user_id = $user_id
            RETURN n.name AS source, r.name AS relationship, connected.name AS target
            """

            params["n_embedding"] = n_embedding
            params["limit"] = limit

            results = self.falkordb_execute(query, parameters=params)

            for result in results:
                result_relations.append(result)

        # Remove duplicates based on the combination of source, relationship, and target
        unique_relations = []
        seen = set()
        for relation in result_relations:
            key = (relation["source"], relation["relationship"], relation["target"])
            if key not in seen:
                seen.add(key)
                final_relation = {
                    "source": relation["source"],
                    "relationship": relation["relationship"],
                    "destination": relation["target"],
                }
                unique_relations.append(final_relation)

        logger.info("Search output: %d unique relations found", len(unique_relations))
        return unique_relations

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """Get the entities to be deleted from the search output."""

        # Compose user identification string for prompt
        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        search_output_string = format_entities(search_output)
        system_prompt, user_message = get_delete_messages(
            search_output_string, data, user_identity
        )

        _tools = [DELETE_MEMORY_TOOL_GRAPH]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [DELETE_MEMORY_STRUCT_TOOL_GRAPH]

        extracted_entities = self.llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            tools=_tools,
        )
        to_be_deleted = []
        if extracted_entities.get("tool_calls"):
            to_be_deleted = (
                extracted_entities["tool_calls"][0]
                .get("arguments", {})
                .get("entities", [])
            )

        to_be_deleted = self._remove_spaces_from_entities(to_be_deleted)
        logger.debug("To be deleted: %s", to_be_deleted)
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
                "relationship_name": relationship,
                "user_id": user_id,
            }
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
            MATCH (n:Entity {{{source_props_str}}})
            -[r:CONNECTED_TO {{name: $relationship_name}}]->
            (m:Entity {{{dest_props_str}}})
            WITH n, r, m, n.name AS source_name, r.name AS relationship_name, m.name AS target_name
            DELETE r
            RETURN
                source_name AS source,
                relationship_name AS relationship,
                target_name AS target
            """

            result = self.falkordb_execute(cypher, parameters=params)
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

            # embeddings
            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            params = {
                "source_name": source,
                "source_embedding": source_embedding,
                "destination_name": destination,
                "destination_embedding": dest_embedding,
                "relationship_name": relationship,
                "user_id": user_id,
                "embedding_dims": self.embedding_dims,
            }

            # Build MERGE properties
            merge_props = ["name: $source_name", "user_id: $user_id"]
            dest_merge_props = ["name: $destination_name", "user_id: $user_id"]
            if agent_id:
                merge_props.append("agent_id: $agent_id")
                dest_merge_props.append("agent_id: $agent_id")
                params["agent_id"] = agent_id
            if run_id:
                merge_props.append("run_id: $run_id")
                dest_merge_props.append("run_id: $run_id")
                params["run_id"] = run_id

            merge_props_str = ", ".join(merge_props)
            dest_merge_props_str = ", ".join(dest_merge_props)

            cypher = f"""
            MERGE (source:Entity {{{merge_props_str}}})
            ON CREATE SET
                source.created = timestamp(),
                source.mentions = 1,
                source.embedding = vecf32($source_embedding)
            ON MATCH SET
                source.mentions = coalesce(source.mentions, 0) + 1,
                source.embedding = vecf32($source_embedding)
            WITH source
            MERGE (destination:Entity {{{dest_merge_props_str}}})
            ON CREATE SET
                destination.created = timestamp(),
                destination.mentions = 1,
                destination.embedding = vecf32($destination_embedding)
            ON MATCH SET
                destination.mentions = coalesce(destination.mentions, 0) + 1,
                destination.embedding = vecf32($destination_embedding)
            WITH source, destination
            MERGE (source)-[r:CONNECTED_TO {{name: $relationship_name}}]->(destination)
            ON CREATE SET
                r.created = timestamp(),
                r.mentions = 1,
                r.updated = timestamp()
            ON MATCH SET
                r.mentions = coalesce(r.mentions, 0) + 1,
                r.updated = timestamp()
            RETURN
                source.name AS source,
                r.name AS relationship,
                destination.name AS target
            """
            result = self.falkordb_execute(cypher, parameters=params)
            results.append(result)

        return results

    def _remove_spaces_from_entities(self, entities):
        """Remove extra spaces from entity names."""
        for entity in entities:
            if "source" in entity:
                entity["source"] = " ".join(entity["source"].split())
            if "destination" in entity:
                entity["destination"] = " ".join(entity["destination"].split())
        return entities

    def _search_source_node(self, embedding, filters, threshold=0.9):
        """Search for source nodes with similar embeddings."""
        params = {
            "embedding": embedding,
            "user_id": filters["user_id"],
        }

        # Build filter conditions
        filter_conditions = ["n.user_id = $user_id"]
        if filters.get("agent_id"):
            filter_conditions.append("n.agent_id = $agent_id")
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            filter_conditions.append("n.run_id = $run_id")
            params["run_id"] = filters["run_id"]

        filter_where = " AND ".join(filter_conditions)

        # Use FalkorDB's vector index query procedure
        query = f"""
        CALL db.idx.vector.queryNodes('Entity', 'embedding', 1, vecf32($embedding)) YIELD node AS n, score
        WHERE {filter_where}
        RETURN n
        LIMIT 1
        """
        return self.falkordb_execute(query, parameters=params)

    def _search_destination_node(self, embedding, filters, threshold=0.9):
        """Search for destination nodes with similar embeddings."""
        return self._search_source_node(embedding, filters, threshold)

    # Reset is not defined in base.py
    def reset(self):
        """Reset the graph by clearing all nodes and relationships."""
        logger.warning("Clearing graph...")
        cypher_query = """
        MATCH (n) DETACH DELETE n
        """
        return self.falkordb_execute(cypher_query)
