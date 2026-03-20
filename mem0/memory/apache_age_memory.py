import json
import logging
import time

from mem0.memory.utils import format_entities, sanitize_relationship_for_cypher

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


def _cosine_similarity(vec1, vec2):
    """Compute cosine similarity between two vectors without numpy."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _get_similar_nodes(nodes, query_embedding, filters, threshold):
    """Find nodes above the similarity threshold from a fetched node list.

    Shared by ``_find_similar_node`` and ``_search_graph_db`` to avoid
    duplicating the client-side cosine similarity logic.
    """
    matches = []
    for node in nodes:
        props = node if isinstance(node, dict) else {}
        stored_emb = props.get("embedding")
        if not stored_emb:
            continue
        if isinstance(stored_emb, str):
            stored_emb = json.loads(stored_emb)

        if filters.get("agent_id") and props.get("agent_id") != filters["agent_id"]:
            continue
        if filters.get("run_id") and props.get("run_id") != filters["run_id"]:
            continue

        sim = _cosine_similarity(query_embedding, stored_emb)
        if sim >= threshold:
            matches.append({"name": props.get("name"), "similarity": sim, "props": props})

    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return matches


class MemoryGraph:
    def __init__(self, config):
        self.config = config

        graph_cfg = self.config.graph_store.config
        self.graph_name = graph_cfg.graph_name

        # Connect using the Apache AGE Python driver (psycopg2-based)
        self.ag = age.connect(
            graph=self.graph_name,
            host=graph_cfg.host,
            port=graph_cfg.port,
            dbname=graph_cfg.database,
            user=graph_cfg.username,
            password=graph_cfg.password,
        )

        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider, self.config.embedder.config, self.config.vector_store.config
        )

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
        self.threshold = self.config.graph_store.threshold if hasattr(self.config.graph_store, "threshold") else 0.7

    # -- helpers ---------------------------------------------------------------

    def _exec_cypher(self, cypher_stmt, cols=None, params=None):
        """Execute a Cypher query via the AGE driver and return results.

        Uses ``ag.execCypher`` which delegates to psycopg2's safe parameter
        substitution (``%s`` placeholders).  The *cols* argument specifies the
        column names in the ``AS (…)`` clause — when ``None`` the driver
        defaults to a single ``v agtype`` column.

        When *cols* are provided, returns a list of dicts keyed by column name.
        When *cols* is ``None``, returns vertex/edge property dicts or raw values.
        """
        cursor = self.ag.execCypher(cypher_stmt, cols=cols, params=params)
        rows = cursor.fetchall()
        if not rows:
            return []

        col_names = [desc[0] for desc in cursor.description] if cursor.description else None
        results = []
        for row in rows:
            if col_names and len(col_names) > 1:
                record = {}
                for i, col_name in enumerate(col_names):
                    val = row[i]
                    if hasattr(val, "properties"):
                        record[col_name] = val.properties
                    else:
                        record[col_name] = val
                results.append(record)
            else:
                val = row[0] if len(row) == 1 else row
                if hasattr(val, "properties"):
                    results.append(val.properties)
                else:
                    results.append(val)
        return results

    def _fetch_user_nodes_with_embeddings(self, user_id):
        """Fetch all nodes with embeddings for a given user_id."""
        return self._exec_cypher(
            "MATCH (n {user_id: %s}) WHERE n.embedding IS NOT NULL RETURN n",
            params=(user_id,),
        )

    def _find_similar_node(self, embedding, filters, threshold=0.9):
        """Find the most similar existing node by cosine similarity.

        Apache AGE does not have a built-in vector index, so we fetch all
        node embeddings matching the filters and compute cosine similarity
        on the client side.  This is adequate for moderate graph sizes; for
        very large graphs consider pairing AGE with pgvector.
        """
        nodes = self._fetch_user_nodes_with_embeddings(filters["user_id"])
        matches = _get_similar_nodes(nodes, embedding, filters, threshold)
        return matches[0]["props"] if matches else None

    def _merge_node(self, user_id, name, embedding, agent_id=None, run_id=None):
        """Create a node if it doesn't exist, or update mentions if it does.

        Apache AGE does not support ``ON CREATE SET`` / ``ON MATCH SET``, so
        we use ``MERGE … SET`` which always applies the SET clause.  Embeddings
        and optional filter properties are set in a single query.
        """
        set_parts = [
            "n.embedding = %s",
            "n.mentions = coalesce(n.mentions, 0) + 1",
            "n.created = coalesce(n.created, %s)",
        ]
        params = [user_id, name, json.dumps(embedding), int(time.time() * 1000)]

        if agent_id:
            set_parts.append("n.agent_id = %s")
            params.append(agent_id)
        if run_id:
            set_parts.append("n.run_id = %s")
            params.append(run_id)

        set_clause = ", ".join(set_parts)
        self._exec_cypher(
            f"MERGE (n {{user_id: %s, name: %s}}) SET {set_clause}",
            params=tuple(params),
        )

    def close(self):
        """Close the underlying database connection."""
        if self.ag:
            self.ag.close()

    # -- public API ------------------------------------------------------------

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
            list: A list of dicts with keys "source", "relationship", "destination".
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
        where_parts = ["n.user_id = %s"]
        params = [filters["user_id"]]
        if filters.get("agent_id"):
            where_parts.append("n.agent_id = %s")
            params.append(filters["agent_id"])
        if filters.get("run_id"):
            where_parts.append("n.run_id = %s")
            params.append(filters["run_id"])
        where_clause = " AND ".join(where_parts)

        self._exec_cypher(
            f"MATCH (n) WHERE {where_clause} DETACH DELETE n",
            params=tuple(params),
        )
        self.ag.commit()

    def get_all(self, filters, limit=100):
        """
        Retrieves all nodes and relationships from the graph database based on optional filtering criteria.

        Args:
            filters (dict): A dictionary containing filters to be applied during the retrieval.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 100.
        Returns:
            list: A list of dictionaries, each containing:
                - 'source': The source node name.
                - 'relationship': The relationship type.
                - 'target': The target node name.
        """
        where_parts = ["n.user_id = %s", "m.user_id = %s"]
        params = [filters["user_id"], filters["user_id"]]
        if filters.get("agent_id"):
            where_parts.extend(["n.agent_id = %s", "m.agent_id = %s"])
            params.extend([filters["agent_id"], filters["agent_id"]])
        if filters.get("run_id"):
            where_parts.extend(["n.run_id = %s", "m.run_id = %s"])
            params.extend([filters["run_id"], filters["run_id"]])
        where_clause = " AND ".join(where_parts)
        params.append(limit)

        results = self._exec_cypher(
            f"MATCH (n)-[r]->(m) WHERE {where_clause} "
            f"RETURN n.name, type(r), m.name LIMIT %s",
            cols=["source", "relationship", "target"],
            params=tuple(params),
        )

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

    # -- LLM-driven extraction -------------------------------------------------

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
                for item in tool_call.get("arguments", {}).get("entities", []):
                    if "entity" in item and "entity_type" in item:
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

        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        if self.config.graph_store.custom_prompt:
            system_content = EXTRACT_RELATIONS_PROMPT.replace("USER_ID", user_identity)
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
        if extracted_entities and extracted_entities.get("tool_calls"):
            entities = extracted_entities["tool_calls"][0].get("arguments", {}).get("entities", [])

        entities = self._remove_spaces_from_entities(entities)
        logger.debug(f"Extracted entities: {entities}")
        return entities

    # -- graph DB operations ---------------------------------------------------

    def _search_graph_db(self, node_list, filters, limit=100):
        """Search similar nodes and their respective incoming and outgoing relations."""
        result_relations = []

        for node in node_list:
            n_embedding = self.embedding_model.embed(node)

            nodes = self._fetch_user_nodes_with_embeddings(filters["user_id"])
            similar_nodes = _get_similar_nodes(nodes, n_embedding, filters, self.threshold)

            # Build WHERE clause for relationship target filtering
            rel_where_parts = ["m.user_id = %s"]
            rel_params_suffix = [filters["user_id"]]
            if filters.get("agent_id"):
                rel_where_parts.append("m.agent_id = %s")
                rel_params_suffix.append(filters["agent_id"])
            if filters.get("run_id"):
                rel_where_parts.append("m.run_id = %s")
                rel_params_suffix.append(filters["run_id"])
            rel_where = " AND ".join(rel_where_parts)

            # For each similar node, fetch its relationships
            for sn in similar_nodes[:limit]:
                node_name = sn["name"]
                similarity = sn["similarity"]

                out_params = (filters["user_id"], node_name) + tuple(rel_params_suffix)
                out_results = self._exec_cypher(
                    f"MATCH (n {{user_id: %s, name: %s}})-[r]->(m) "
                    f"WHERE {rel_where} "
                    f"RETURN n.name, type(r), m.name",
                    cols=["source", "relationship", "destination"],
                    params=out_params,
                )

                in_params = (filters["user_id"], node_name) + tuple(rel_params_suffix)
                in_results = self._exec_cypher(
                    f"MATCH (n {{user_id: %s, name: %s}})<-[r]-(m) "
                    f"WHERE {rel_where} "
                    f"RETURN m.name, type(r), n.name",
                    cols=["source", "relationship", "destination"],
                    params=in_params,
                )

                for rel in out_results + in_results:
                    rel["similarity"] = similarity
                    result_relations.append(rel)

        return result_relations

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """Get the entities to be deleted from the search output."""
        search_output_string = format_entities(search_output)

        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        system_prompt, user_prompt = get_delete_messages(search_output_string, data, user_identity)

        _tools = [DELETE_MEMORY_TOOL_GRAPH]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [DELETE_MEMORY_STRUCT_TOOL_GRAPH]

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
        to_be_deleted = self._remove_spaces_from_entities(to_be_deleted)
        logger.debug(f"Deleted relationships: {to_be_deleted}")
        return to_be_deleted

    def _delete_entities(self, to_be_deleted, filters):
        """Delete the entities from the graph."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")
        run_id = filters.get("run_id")
        results = []

        try:
            for item in to_be_deleted:
                source = item["source"]
                destination = item["destination"]
                relationship = item["relationship"]

                where_parts = [
                    "n.user_id = %s", "n.name = %s",
                    "m.user_id = %s", "m.name = %s",
                ]
                params = [user_id, source, user_id, destination]
                if agent_id:
                    where_parts.extend(["n.agent_id = %s", "m.agent_id = %s"])
                    params.extend([agent_id, agent_id])
                if run_id:
                    where_parts.extend(["n.run_id = %s", "m.run_id = %s"])
                    params.extend([run_id, run_id])
                where_clause = " AND ".join(where_parts)

                result = self._exec_cypher(
                    f"MATCH (n)-[r:{relationship}]->(m) "
                    f"WHERE {where_clause} "
                    f"DELETE r "
                    f"RETURN n.name, type(r), m.name",
                    cols=["source", "relationship", "target"],
                    params=tuple(params),
                )
                results.append(result)

            self.ag.commit()
        except Exception:
            self.ag.rollback()
            raise

        return results

    def _add_entities(self, to_be_added, filters, entity_type_map):
        """Add new entities to the graph. Merge nodes if they already exist.

        Apache AGE does not support ``ON CREATE SET`` / ``ON MATCH SET``, so we
        use ``MERGE … SET`` which always applies.  The ``coalesce`` pattern
        ensures ``created`` is only set on the first merge.
        """
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")
        run_id = filters.get("run_id")
        results = []

        try:
            for item in to_be_added:
                source = item["source"]
                destination = item["destination"]
                relationship = item["relationship"]

                source_embedding = self.embedding_model.embed(source)
                dest_embedding = self.embedding_model.embed(destination)

                source_match = self._find_similar_node(source_embedding, filters, threshold=self.threshold)
                dest_match = self._find_similar_node(dest_embedding, filters, threshold=self.threshold)

                effective_source = source_match["name"] if source_match else source
                effective_dest = dest_match["name"] if dest_match else destination

                # Merge source and destination nodes
                self._merge_node(user_id, effective_source, source_embedding, agent_id, run_id)
                self._merge_node(user_id, effective_dest, dest_embedding, agent_id, run_id)

                # Merge relationship
                result = self._exec_cypher(
                    f"MATCH (s {{user_id: %s, name: %s}}), (d {{user_id: %s, name: %s}}) "
                    f"MERGE (s)-[r:{relationship}]->(d) "
                    f"RETURN s.name, type(r), d.name",
                    cols=["source", "relationship", "target"],
                    params=(user_id, effective_source, user_id, effective_dest),
                )
                results.append(result)

            self.ag.commit()
        except Exception:
            self.ag.rollback()
            raise

        return results

    def _remove_spaces_from_entities(self, entity_list):
        for item in entity_list:
            item["source"] = item["source"].lower().replace(" ", "_")
            item["relationship"] = sanitize_relationship_for_cypher(item["relationship"].lower().replace(" ", "_"))
            item["destination"] = item["destination"].lower().replace(" ", "_")
        return entity_list

    def reset(self):
        """Reset the graph by clearing all nodes and relationships."""
        logger.warning("Clearing graph...")
        self._exec_cypher("MATCH (n) DETACH DELETE n")
        self.ag.commit()
