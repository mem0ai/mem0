"""FalkorDB graph memory implementation for Mem0.

Based on mem0-falkordb plugin (v0.4.1) by FalkorDB team.
Integrated natively into mem0ai fork to avoid monkey-patching.

Key features over Neo4j MemoryGraph:
- Per-user graph isolation ({database}_{user_id})
- Typed relationships (WORKS_AT, KNOWS) instead of generic CONNECTED_TO
- Embedding-based node deduplication before MERGE
- BM25 re-ranking on search results
- FalkorDB native vector index (db.idx.vector.queryNodes)
"""

import logging
from collections import OrderedDict

from mem0.memory.utils import format_entities, sanitize_relationship_for_cypher

# Required keys for a valid entity/relation from LLM tool calls
_ENTITY_REQUIRED_KEYS = {"source", "relationship", "destination"}

try:
    from falkordb import FalkorDB
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


_MAX_GRAPH_CACHE = 256


class _FalkorDBGraphWrapper:
    """Thin wrapper around the FalkorDB client to provide a .query() interface
    consistent with what the MemoryGraph methods expect (list-of-dict results).

    Each user_id gets a separate FalkorDB graph for natural data isolation.
    """

    def __init__(self, host, port, database, username=None, password=None):
        connect_kwargs = {"host": host, "port": port}
        if username and password:
            connect_kwargs["username"] = username
            connect_kwargs["password"] = password
        self._db = FalkorDB(**connect_kwargs)
        self._database = database
        self._graph_cache = OrderedDict()

    def _get_graph(self, user_id):
        """Get the FalkorDB graph object for the given user_id."""
        if user_id in self._graph_cache:
            self._graph_cache.move_to_end(user_id)
            return self._graph_cache[user_id]
        graph_name = f"{self._database}_{user_id}"
        graph = self._db.select_graph(graph_name)
        self._graph_cache[user_id] = graph
        if len(self._graph_cache) > _MAX_GRAPH_CACHE:
            self._graph_cache.popitem(last=False)
        return graph

    def query(self, cypher, params=None, user_id=None):
        """Execute a Cypher query and return results as a list of dicts."""
        if user_id is None:
            raise ValueError("user_id is required for per-user graph isolation")
        graph = self._get_graph(user_id)
        result = graph.query(cypher, params=params)
        if not result.result_set:
            return []
        header = [h[1] if isinstance(h, (list, tuple)) else h for h in result.header]
        return [dict(zip(header, row)) for row in result.result_set]

    def delete_graph(self, user_id):
        """Delete an entire user graph."""
        graph_name = f"{self._database}_{user_id}"
        try:
            graph = self._db.select_graph(graph_name)
            graph.delete()
        except Exception:
            logger.debug("Graph %s not found or already deleted", graph_name)
        self._graph_cache.pop(user_id, None)

    def reset_all_graphs(self):
        """Delete all graphs matching the database prefix."""
        prefix = f"{self._database}_"
        try:
            all_graphs = self._db.list_graphs()
        except Exception:
            logger.warning("Failed to list graphs for reset")
            return
        for graph_name in all_graphs:
            if graph_name.startswith(prefix):
                try:
                    self._db.select_graph(graph_name).delete()
                except Exception:
                    logger.debug("Failed to delete graph %s during reset", graph_name)
        self._graph_cache.clear()


class MemoryGraph:
    def __init__(self, config):
        self.config = config
        self.graph_wrapper = _FalkorDBGraphWrapper(
            host=self.config.graph_store.config.host,
            port=self.config.graph_store.config.port,
            database=self.config.graph_store.config.database,
            username=self.config.graph_store.config.username,
            password=self.config.graph_store.config.password,
        )
        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider,
            self.config.embedder.config,
            self.config.vector_store.config,
        )

        self.use_base_label = getattr(
            self.config.graph_store.config, "base_label", True
        )
        self.node_label = ":`__Entity__`" if self.use_base_label else ""

        # Track which user graphs already have indexes created (lazy creation)
        self._indexed_user_graphs = set()

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

        # Fallback LLM: retry entity/relation extraction when primary LLM returns empty or malformed results
        self.fallback_llm = None
        self.fallback_llm_provider = None
        if hasattr(self.config.graph_store, 'fallback_llm') and self.config.graph_store.fallback_llm:
            fb_config = self.config.graph_store.fallback_llm
            if hasattr(fb_config, 'provider') and hasattr(fb_config, 'config'):
                self.fallback_llm = LlmFactory.create(fb_config.provider, fb_config.config)
                self.fallback_llm_provider = fb_config.provider
                logger.info("Graph fallback LLM configured: %s", fb_config.provider)

        self.threshold = (
            self.config.graph_store.threshold
            if hasattr(self.config.graph_store, "threshold")
            else 0.7
        )

    # ------------------------------------------------------------------
    # Index management (lazy, per-user graph)
    # ------------------------------------------------------------------

    def _ensure_indexes(self, user_id):
        """Create range index on __Entity__.name for the user's graph."""
        graph = self.graph_wrapper._get_graph(user_id)
        try:
            graph.create_node_range_index("__Entity__", "name")
        except Exception:
            logger.debug("Range index on name may already exist for user %s", user_id)

    def _ensure_vector_index(self, dim, user_id):
        """Create vector index on the embedding property for the user's graph."""
        graph = self.graph_wrapper._get_graph(user_id)
        try:
            graph.create_node_vector_index(
                "__Entity__", "embedding", dim=dim, similarity_function="cosine"
            )
        except Exception:
            logger.debug("Vector index may already exist for user %s", user_id)

    def _ensure_user_graph_indexes(self, user_id):
        """Ensure indexes exist for a user's graph (idempotent, cached)."""
        if user_id in self._indexed_user_graphs:
            return
        if self.use_base_label:
            self._ensure_indexes(user_id=user_id)
        self._indexed_user_graphs.add(user_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_node_props(self, filters, include_name=False, name_param="name"):
        """Build Cypher property string and params dict from filters.

        Per-user graph mode: user_id is NOT included (graph-level isolation).
        Only agent_id and run_id are included as property filters.
        """
        props = []
        params = {}
        if include_name:
            props.append(f"name: ${name_param}")
        if filters.get("agent_id"):
            props.append("agent_id: $agent_id")
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            props.append("run_id: $run_id")
            params["run_id"] = filters["run_id"]
        return ", ".join(props), params

    @staticmethod
    def _user_id(filters):
        """Extract user_id from filters dict."""
        return filters["user_id"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, data, filters):
        """
        Adds data to the graph.

        Args:
            data (str): The data to add to the graph.
            filters (dict): A dictionary containing filters to be applied during the addition.
        """
        self._ensure_user_graph_indexes(filters["user_id"])
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

    def search(self, query, filters, limit=100):
        """
        Search for memories and related graph data.

        Args:
            query (str): Query to search for.
            filters (dict): A dictionary containing filters to be applied during the search.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 100.

        Returns:
            list: A list of search results with BM25 re-ranking.
        """
        self._ensure_user_graph_indexes(filters["user_id"])
        entity_type_map = self._retrieve_nodes_from_data(query, filters)
        search_output = self._search_graph_db(
            node_list=list(entity_type_map.keys()), filters=filters
        )

        if not search_output:
            return []

        search_outputs_sequence = [
            [item["source"], item["relationship"], item["destination"]]
            for item in search_output
        ]
        bm25 = BM25Okapi(search_outputs_sequence)

        tokenized_query = query.split(" ")
        reranked_results = bm25.get_top_n(tokenized_query, search_outputs_sequence, n=5)

        search_results = []
        for item in reranked_results:
            search_results.append(
                {"source": item[0], "relationship": item[1], "destination": item[2]}
            )

        logger.info(f"Returned {len(search_results)} search results")
        return search_results

    def delete(self, data, filters):
        """
        Delete graph entities associated with the given memory text.

        Extracts entities and relationships from the memory text using the same
        pipeline as add(), then deletes the matching relationships in the graph.

        Args:
            data (str): The memory text whose graph entities should be removed.
            filters (dict): Scope filters (user_id, agent_id, run_id).
        """
        try:
            entity_type_map = self._retrieve_nodes_from_data(data, filters)
            if not entity_type_map:
                logger.debug("No entities found in memory text, skipping graph cleanup")
                return
            to_be_deleted = self._establish_nodes_relations_from_data(data, filters, entity_type_map)
            if to_be_deleted:
                self._delete_entities(to_be_deleted, filters)
        except Exception as e:
            logger.error(f"Error during graph cleanup for memory delete: {e}")

    def delete_all(self, filters):
        """Delete all nodes and relationships for a user.

        If no agent_id/run_id filter, deletes the entire user graph.
        Otherwise, deletes only matching nodes within the user's graph.
        """
        uid = self._user_id(filters)

        if not filters.get("agent_id") and not filters.get("run_id"):
            # No sub-filters: drop the entire user graph
            self.graph_wrapper.delete_graph(uid)
            self._indexed_user_graphs.discard(uid)
            return

        # Sub-filter: delete only matching nodes
        node_props_str, params = self._build_node_props(filters)
        if node_props_str:
            cypher = f"MATCH (n {self.node_label} {{{node_props_str}}}) DETACH DELETE n"
        else:
            cypher = f"MATCH (n {self.node_label}) DETACH DELETE n"
        self.graph_wrapper.query(cypher, params=params, user_id=uid)

    def get_all(self, filters, limit=100):
        """
        Retrieves all nodes and relationships from the graph database based on optional filtering criteria.

        Args:
            filters (dict): A dictionary containing filters to be applied during the retrieval.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 100.

        Returns:
            list: A list of dictionaries, each containing source, relationship, and target.
        """
        uid = self._user_id(filters)
        node_props_str, params = self._build_node_props(filters)
        if node_props_str:
            query = f"""
            MATCH (n {self.node_label} {{{node_props_str}}})-[r]->(m {self.node_label} {{{node_props_str}}})
            WHERE r.valid IS NULL OR r.valid = true
            RETURN n.name AS source, type(r) AS relationship, m.name AS target
            LIMIT {int(limit)}
            """
        else:
            query = f"""
            MATCH (n {self.node_label})-[r]->(m {self.node_label})
            WHERE r.valid IS NULL OR r.valid = true
            RETURN n.name AS source, type(r) AS relationship, m.name AS target
            LIMIT {int(limit)}
            """
        results = self.graph_wrapper.query(query, params=params, user_id=uid)

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

    def reset(self):
        """Reset all graphs by deleting every graph matching the database prefix."""
        logger.warning(
            "Resetting all graphs with prefix '%s_'...", self.graph_wrapper._database
        )
        self.graph_wrapper.reset_all_graphs()
        self._indexed_user_graphs.clear()

    # ------------------------------------------------------------------
    # LLM-based entity extraction
    # ------------------------------------------------------------------

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
        _parse_failed = False

        try:
            for tool_call in search_results["tool_calls"]:
                if tool_call["name"] != "extract_entities":
                    continue
                for item in tool_call.get("arguments", {}).get("entities", []):
                    entity_type_map[item["entity"]] = item["entity_type"]
        except Exception as e:
            _parse_failed = True
            logger.exception(
                f"Error in search tool: {e}, llm_provider={self.llm_provider}, search_results={search_results}"
            )

        # Fallback to backup LLM when primary returns empty or malformed results
        if (not entity_type_map or _parse_failed) and self.fallback_llm:
            logger.warning("Primary LLM entity extraction returned empty/malformed, retrying with fallback LLM")
            try:
                _messages = [
                    {
                        "role": "system",
                        "content": f"You are a smart assistant who understands entities and their types in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use {filters['user_id']} as the source entity. Extract all the entities from the text. ***DO NOT*** answer the question itself if the given text is a question.",
                    },
                    {"role": "user", "content": data},
                ]
                # Select tools matching the fallback LLM provider
                fb_tools = [EXTRACT_ENTITIES_TOOL]
                if self.fallback_llm_provider in ["azure_openai_structured", "openai_structured"]:
                    fb_tools = [EXTRACT_ENTITIES_STRUCT_TOOL]
                fb_results = self.fallback_llm.generate_response(
                    messages=_messages,
                    tools=fb_tools,
                )
                fb_entity_type_map = {}
                for tool_call in fb_results.get("tool_calls", []):
                    if tool_call.get("name") != "extract_entities":
                        continue
                    for item in tool_call.get("arguments", {}).get("entities", []):
                        fb_entity_type_map[item["entity"]] = item["entity_type"]
                if fb_entity_type_map:
                    logger.info("Fallback LLM entity extraction succeeded: %d entities", len(fb_entity_type_map))
                    entity_type_map = fb_entity_type_map
                else:
                    logger.info("Fallback LLM entity extraction also returned empty results")
            except Exception as e:
                logger.exception(f"Fallback LLM entity extraction failed: {e}")

        entity_type_map = {k.lower().replace(" ", "_"): v.lower().replace(" ", "_") for k, v in entity_type_map.items()}
        logger.debug(f"Entity type map: {entity_type_map}")
        return entity_type_map

    def _establish_nodes_relations_from_data(self, data, filters, entity_type_map):
        """Establish relations among the extracted nodes."""

        # Compose user identification string for prompt
        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        system_content = EXTRACT_RELATIONS_PROMPT.replace("USER_ID", user_identity)
        if self.config.graph_store.custom_prompt:
            system_content = system_content.replace(
                "CUSTOM_PROMPT", f"4. {self.config.graph_store.custom_prompt}"
            )
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": data},
            ]
        else:
            system_content = system_content.replace("CUSTOM_PROMPT", "")
            messages = [
                {"role": "system", "content": system_content},
                {
                    "role": "user",
                    "content": f"List of entities: {list(entity_type_map.keys())}. \n\nText: {data}",
                },
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

        # Filter out entities with missing or invalid fields BEFORE _remove_spaces_from_entities
        valid_entities = []
        for entity in entities:
            missing = _ENTITY_REQUIRED_KEYS - entity.keys()
            if missing:
                logger.warning("[_establish_nodes_relations] Skipping entity with missing fields: missing=%s, entity=%s", missing, entity)
            elif not all(isinstance(entity.get(k), str) and entity[k].strip() for k in _ENTITY_REQUIRED_KEYS):
                logger.warning("[_establish_nodes_relations] Skipping entity with empty/non-string values: entity=%s", entity)
            else:
                valid_entities.append(entity)

        # Fallback to backup LLM only when primary returns NO valid entities at all
        if not valid_entities and self.fallback_llm:
            logger.warning(
                "Primary LLM returned 0 valid entities (out of %d raw), retrying with fallback LLM",
                len(entities),
            )
            try:
                fb_tools = [RELATIONS_TOOL]
                if self.fallback_llm_provider in ["azure_openai_structured", "openai_structured"]:
                    fb_tools = [RELATIONS_STRUCT_TOOL]
                fallback_result = self.fallback_llm.generate_response(
                    messages=messages,
                    tools=fb_tools,
                )
                fallback_entities = []
                if fallback_result.get("tool_calls"):
                    fallback_entities = (
                        fallback_result["tool_calls"][0]
                        .get("arguments", {})
                        .get("entities", [])
                    )
                fb_valid = [
                    e for e in fallback_entities
                    if _ENTITY_REQUIRED_KEYS <= e.keys()
                    and all(isinstance(e.get(k), str) and e[k].strip() for k in _ENTITY_REQUIRED_KEYS)
                ]
                fb_valid = self._remove_spaces_from_entities(fb_valid)
                if len(fb_valid) > len(valid_entities):
                    logger.info(
                        "Fallback LLM produced better results: %d valid vs original %d valid",
                        len(fb_valid), len(valid_entities),
                    )
                    entities = fb_valid
                else:
                    entities = valid_entities
                    logger.info(
                        "Fallback LLM did not improve results, using original: %d valid",
                        len(valid_entities),
                    )
            except Exception as e:
                logger.exception(f"Fallback LLM relation extraction failed: {e}")
                entities = valid_entities
        else:
            entities = valid_entities

        # Normalize after validation (safe: all entities have required keys at this point)
        entities = self._remove_spaces_from_entities(entities)
        logger.debug(f"Extracted entities: {entities}")
        return entities

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """Get the entities to be deleted from the search output."""
        search_output_string = format_entities(search_output)

        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        system_prompt, user_prompt = get_delete_messages(
            search_output_string, data, user_identity
        )

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

    # ------------------------------------------------------------------
    # FalkorDB Cypher: graph search with vector similarity
    # ------------------------------------------------------------------

    def _search_graph_db(self, node_list, filters, limit=100):
        """Search similar nodes and their respective incoming and outgoing relations."""
        result_relations = []
        uid = self._user_id(filters)
        node_props_str, base_params = self._build_node_props(filters)

        for node in node_list:
            n_embedding = self.embedding_model.embed(node)
            self._ensure_vector_index(len(n_embedding), user_id=uid)

            label = "__Entity__" if self.use_base_label else "Node"

            where_clauses = ["score >= $threshold"]
            if filters.get("agent_id"):
                where_clauses.append("node.agent_id = $agent_id")
            if filters.get("run_id"):
                where_clauses.append("node.run_id = $run_id")
            where_str = " AND ".join(where_clauses)

            vector_query = f"""
            CALL db.idx.vector.queryNodes('{label}', 'embedding', {int(limit)}, vecf32($n_embedding))
            YIELD node, score
            WITH node, score
            WHERE {where_str}
            RETURN id(node) AS node_id, node.name AS node_name, score
            LIMIT {int(limit)}
            """

            params = {
                "n_embedding": n_embedding,
                "threshold": self.threshold,
                **base_params,
            }

            similar_nodes = self.graph_wrapper.query(vector_query, params=params, user_id=uid)

            for sn in similar_nodes:
                node_id = sn["node_id"]
                rel_params = {"node_id": node_id, **base_params}

                match_props = f" {{{node_props_str}}}" if node_props_str else ""
                out_query = f"""
                MATCH (n {self.node_label})-[r]->(m {self.node_label}{match_props})
                WHERE id(n) = $node_id AND (r.valid IS NULL OR r.valid = true)
                RETURN n.name AS source, id(n) AS source_id, type(r) AS relationship,
                       id(r) AS relation_id, m.name AS destination, id(m) AS destination_id
                """
                in_query = f"""
                MATCH (n {self.node_label})<-[r]-(m {self.node_label}{match_props})
                WHERE id(n) = $node_id AND (r.valid IS NULL OR r.valid = true)
                RETURN m.name AS source, id(m) AS source_id, type(r) AS relationship,
                       id(r) AS relation_id, n.name AS destination, id(n) AS destination_id
                """

                out_results = self.graph_wrapper.query(
                    out_query, params=rel_params, user_id=uid
                )
                in_results = self.graph_wrapper.query(in_query, params=rel_params, user_id=uid)

                result_relations.extend(out_results)
                result_relations.extend(in_results)

        # Deduplicate by relation_id
        seen = set()
        unique_results = []
        for r in result_relations:
            rid = r.get("relation_id")
            if rid not in seen:
                seen.add(rid)
                unique_results.append(r)

        return unique_results

    # ------------------------------------------------------------------
    # FalkorDB Cypher: entity deletion
    # ------------------------------------------------------------------

    def _delete_entities(self, to_be_deleted, filters):
        uid = self._user_id(filters)
        results = []

        for item in to_be_deleted:
            # Defensive: skip items with missing or invalid fields
            missing = _ENTITY_REQUIRED_KEYS - item.keys()
            if missing:
                logger.warning("[_delete_entities] Skipping item with missing fields: missing=%s, item=%s", missing, item)
                continue
            if not all(isinstance(item.get(k), str) and item[k].strip() for k in _ENTITY_REQUIRED_KEYS):
                logger.warning("[_delete_entities] Skipping item with empty/non-string values: item=%s", item)
                continue

            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            source_props_str, params = self._build_node_props(
                filters, include_name=True, name_param="source_name"
            )
            dest_props_str, _ = self._build_node_props(
                filters, include_name=True, name_param="dest_name"
            )
            params["source_name"] = source
            params["dest_name"] = destination

            cypher = f"""
            MATCH (n {self.node_label} {{{source_props_str}}})
            -[r:`{relationship}`]->
            (m {self.node_label} {{{dest_props_str}}})
            WITH n, r, m, n.name AS source, m.name AS target, type(r) AS rel_type
            DELETE r
            RETURN source, target, rel_type AS relationship
            """
            result = self.graph_wrapper.query(cypher, params=params, user_id=uid)
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # FalkorDB Cypher: entity addition with vector embeddings
    # ------------------------------------------------------------------

    def _get_openai_embed_client(self):
        """Lazy singleton for OpenAI embedding client used by _batch_embed."""
        if not hasattr(self, "_openai_embed_client"):
            from openai import OpenAI
            ecfg = self.config.embedder.config
            if isinstance(ecfg, dict):
                api_key = ecfg.get("api_key")
                base_url = ecfg.get("openai_base_url")
            else:
                api_key = getattr(ecfg, "api_key", None)
                base_url = getattr(ecfg, "openai_base_url", None)
            self._openai_embed_client = OpenAI(api_key=api_key, base_url=base_url)
        return self._openai_embed_client

    def _batch_embed(self, texts):
        """Batch embed multiple texts in a single API call. Returns list of embeddings.

        Only uses native batch for the OpenAI provider.
        Falls back to sequential embed() for all other providers.
        """
        if not texts:
            return []

        provider = self.config.embedder.provider
        if provider != "openai":
            return [self.embedding_model.embed(t) for t in texts]

        try:
            client = self._get_openai_embed_client()
            ecfg = self.config.embedder.config
            model = ecfg.get("model") if isinstance(ecfg, dict) else getattr(ecfg, "model", None)
            dims = ecfg.get("embedding_dims") if isinstance(ecfg, dict) else getattr(ecfg, "embedding_dims", None)

            kwargs = {"input": texts, "model": model}
            if dims is not None:
                kwargs["dimensions"] = dims
            resp = client.embeddings.create(**kwargs)
            # Sort by index to guarantee order matches input
            sorted_data = sorted(resp.data, key=lambda d: d.index)
            return [d.embedding for d in sorted_data]
        except Exception as e:
            logger.warning("Batch embed failed (%s), falling back to sequential", type(e).__name__)
            return [self.embedding_model.embed(t) for t in texts]

    def _add_entities(self, to_be_added, filters, entity_type_map):
        """Add the new entities to the graph. Merge the nodes if they already exist."""
        uid = self._user_id(filters)
        results = []

        if not to_be_added:
            return results

        # --- Batch embed all unique entities upfront ---
        # Defensive: skip items missing source/destination (incomplete LLM tool calls)
        unique_entities = sorted(
            {item["source"] for item in to_be_added if "source" in item}
            | {item["destination"] for item in to_be_added if "destination" in item}
        )
        unique_embeddings = self._batch_embed(unique_entities)
        embedding_cache = dict(zip(unique_entities, unique_embeddings))

        if unique_embeddings:
            self._ensure_vector_index(len(unique_embeddings[0]), user_id=uid)

        # Pre-compute node searches using cached embeddings (unified cache)
        node_cache = {}
        for entity, emb in embedding_cache.items():
            node_cache[entity] = self._search_node_by_embedding(emb, filters)

        logger.debug(f"Batch embedded {len(unique_entities)} unique entities, cached {len(node_cache)} node lookups")

        for item in to_be_added:
            # Defensive: skip items with missing or invalid fields
            missing = _ENTITY_REQUIRED_KEYS - item.keys()
            if missing:
                logger.warning("[_add_entities] Skipping item with missing fields: missing=%s, item=%s", missing, item)
                continue
            if not all(isinstance(item.get(k), str) and item[k].strip() for k in _ENTITY_REQUIRED_KEYS):
                logger.warning("[_add_entities] Skipping item with empty/non-string values: item=%s", item)
                continue

            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            source_type = entity_type_map.get(source, "__User__")
            source_label = self.node_label if self.node_label else f":`{source_type}`"
            source_extra_set = f", source:`{source_type}`" if self.node_label else ""
            destination_type = entity_type_map.get(destination, "__User__")
            destination_label = (
                self.node_label if self.node_label else f":`{destination_type}`"
            )
            destination_extra_set = (
                f", destination:`{destination_type}`" if self.node_label else ""
            )

            source_embedding = embedding_cache.get(source) or self.embedding_model.embed(source)
            dest_embedding = embedding_cache.get(destination) or self.embedding_model.embed(destination)

            source_node = node_cache.get(source)
            dest_node = node_cache.get(destination)

            if not dest_node and source_node:
                dest_merge_str, params = self._build_node_props(
                    filters, include_name=True, name_param="destination_name"
                )
                params["source_id"] = source_node
                params["destination_name"] = destination
                params["destination_embedding"] = dest_embedding

                cypher = f"""
                MATCH (source)
                WHERE id(source) = $source_id
                SET source.mentions = coalesce(source.mentions, 0) + 1
                WITH source
                MERGE (destination {destination_label} {{{dest_merge_str}}})
                ON CREATE SET
                    destination.created = timestamp(),
                    destination.mentions = 1,
                    destination.embedding = vecf32($destination_embedding)
                    {destination_extra_set}
                ON MATCH SET
                    destination.mentions = coalesce(destination.mentions, 0) + 1,
                    destination.embedding = vecf32($destination_embedding)
                WITH source, destination
                MERGE (source)-[r:`{relationship}`]->(destination)
                ON CREATE SET
                    r.created_at = timestamp(),
                    r.updated_at = timestamp(),
                    r.mentions = 1,
                    r.valid = true
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1,
                    r.valid = true,
                    r.updated_at = timestamp(),
                    r.invalidated_at = null
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                """

            elif dest_node and not source_node:
                src_merge_str, params = self._build_node_props(
                    filters, include_name=True, name_param="source_name"
                )
                params["destination_id"] = dest_node
                params["source_name"] = source
                params["source_embedding"] = source_embedding

                cypher = f"""
                MATCH (destination)
                WHERE id(destination) = $destination_id
                SET destination.mentions = coalesce(destination.mentions, 0) + 1
                WITH destination
                MERGE (source {source_label} {{{src_merge_str}}})
                ON CREATE SET
                    source.created = timestamp(),
                    source.mentions = 1,
                    source.embedding = vecf32($source_embedding)
                    {source_extra_set}
                ON MATCH SET
                    source.mentions = coalesce(source.mentions, 0) + 1,
                    source.embedding = vecf32($source_embedding)
                WITH source, destination
                MERGE (source)-[r:`{relationship}`]->(destination)
                ON CREATE SET
                    r.created_at = timestamp(),
                    r.updated_at = timestamp(),
                    r.mentions = 1,
                    r.valid = true
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1,
                    r.valid = true,
                    r.updated_at = timestamp(),
                    r.invalidated_at = null
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                """

            elif source_node and dest_node:
                _, params = self._build_node_props(filters)
                params["source_id"] = source_node
                params["destination_id"] = dest_node

                cypher = f"""
                MATCH (source)
                WHERE id(source) = $source_id
                SET source.mentions = coalesce(source.mentions, 0) + 1
                WITH source
                MATCH (destination)
                WHERE id(destination) = $destination_id
                SET destination.mentions = coalesce(destination.mentions, 0) + 1
                MERGE (source)-[r:`{relationship}`]->(destination)
                ON CREATE SET
                    r.created_at = timestamp(),
                    r.updated_at = timestamp(),
                    r.mentions = 1,
                    r.valid = true
                ON MATCH SET
                    r.mentions = coalesce(r.mentions, 0) + 1,
                    r.valid = true,
                    r.updated_at = timestamp(),
                    r.invalidated_at = null
                RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                """

            else:
                source_props_str, params = self._build_node_props(
                    filters, include_name=True, name_param="source_name"
                )
                dest_props_str, _ = self._build_node_props(
                    filters, include_name=True, name_param="dest_name"
                )
                params["source_name"] = source
                params["dest_name"] = destination
                params["source_embedding"] = source_embedding
                params["dest_embedding"] = dest_embedding

                cypher = f"""
                MERGE (source {source_label} {{{source_props_str}}})
                ON CREATE SET source.created = timestamp(),
                            source.mentions = 1,
                            source.embedding = vecf32($source_embedding)
                            {source_extra_set}
                ON MATCH SET source.mentions = coalesce(source.mentions, 0) + 1,
                            source.embedding = vecf32($source_embedding)
                WITH source
                MERGE (destination {destination_label} {{{dest_props_str}}})
                ON CREATE SET destination.created = timestamp(),
                            destination.mentions = 1,
                            destination.embedding = vecf32($dest_embedding)
                            {destination_extra_set}
                ON MATCH SET destination.mentions = coalesce(destination.mentions, 0) + 1,
                            destination.embedding = vecf32($dest_embedding)
                WITH source, destination
                MERGE (source)-[rel:`{relationship}`]->(destination)
                ON CREATE SET
                    rel.created_at = timestamp(),
                    rel.updated_at = timestamp(),
                    rel.mentions = 1,
                    rel.valid = true
                ON MATCH SET
                    rel.mentions = coalesce(rel.mentions, 0) + 1,
                    rel.valid = true,
                    rel.updated_at = timestamp(),
                    rel.invalidated_at = null
                RETURN source.name AS source, type(rel) AS relationship, destination.name AS target
                """

            result = self.graph_wrapper.query(cypher, params=params, user_id=uid)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # FalkorDB Cypher: node search by embedding similarity
    # ------------------------------------------------------------------

    def _search_node_by_embedding(self, embedding, filters):
        """Search for a node by embedding similarity. Returns node_id (int) or None."""
        uid = self._user_id(filters)
        label = "__Entity__" if self.use_base_label else "Node"

        where_clauses = ["score >= $threshold"]
        if filters.get("agent_id"):
            where_clauses.append("node.agent_id = $agent_id")
        if filters.get("run_id"):
            where_clauses.append("node.run_id = $run_id")
        where_str = " AND ".join(where_clauses)

        cypher = f"""
        CALL db.idx.vector.queryNodes('{label}', 'embedding', 10, vecf32($embedding))
        YIELD node, score
        WITH node, score
        WHERE {where_str}
        RETURN id(node) AS node_id
        LIMIT 1
        """

        params = {
            "embedding": embedding,
            "threshold": self.threshold,
        }
        if filters.get("agent_id"):
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            params["run_id"] = filters["run_id"]

        try:
            result = self.graph_wrapper.query(cypher, params=params, user_id=uid)
            if result:
                return result[0]["node_id"]
        except Exception:
            logger.debug("Vector search failed for user %s (index may not exist yet)", uid)
        return None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _remove_spaces_from_entities(self, entity_list):
        for item in entity_list:
            # Defensive: skip items with missing required fields
            missing = _ENTITY_REQUIRED_KEYS - item.keys()
            if missing:
                logger.warning("[_remove_spaces_from_entities] Skipping item with missing fields: missing=%s, item=%s", missing, item)
                continue
            item["source"] = item["source"].lower().replace(" ", "_")
            item["relationship"] = sanitize_relationship_for_cypher(
                item["relationship"].lower().replace(" ", "_")
            )
            item["destination"] = item["destination"].lower().replace(" ", "_")
        return entity_list
