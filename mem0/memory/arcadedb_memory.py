import json
import logging
import time

import requests

from mem0.graphs.tools import (
    DELETE_MEMORY_STRUCT_TOOL_GRAPH,
    DELETE_MEMORY_TOOL_GRAPH,
    EXTRACT_ENTITIES_STRUCT_TOOL,
    EXTRACT_ENTITIES_TOOL,
    RELATIONS_STRUCT_TOOL,
    RELATIONS_TOOL,
)
from mem0.graphs.utils import EXTRACT_RELATIONS_PROMPT, get_delete_messages
from mem0.memory.utils import format_entities, remove_spaces_from_entities
from mem0.utils.factory import EmbedderFactory, LlmFactory

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    raise ImportError("rank_bm25 is not installed. Please install it using pip install rank-bm25")

logger = logging.getLogger(__name__)


class MemoryGraph:
    """ArcadeDB graph memory backend using the HTTP REST API.

    Uses ArcadeDB's native HNSW vector indexes for similarity search and
    OpenCypher for graph traversal.  Communication happens via ``requests``
    against the ``/api/v1/command/{database}`` endpoint.
    """

    def __init__(self, config):
        self.config = config

        graph_cfg = self.config.graph_store.config
        self.url = graph_cfg.url.rstrip("/")
        self.database = graph_cfg.database
        self.auth = (graph_cfg.username, graph_cfg.password)
        self.enable_gav = graph_cfg.enable_gav
        self.gav_vertex_type = graph_cfg.gav_vertex_type
        self.gav_edge_type = graph_cfg.gav_edge_type

        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider, self.config.embedder.config, self.config.vector_store.config
        )

        # Determine embedding dimensions from the model
        self._embedding_dims = None

        # LLM setup — same pattern as other backends
        self.llm_provider = "openai"
        if self.config.llm and self.config.llm.provider:
            self.llm_provider = self.config.llm.provider
        if self.config.graph_store and self.config.graph_store.llm and self.config.graph_store.llm.provider:
            self.llm_provider = self.config.graph_store.llm.provider

        llm_config = None
        if self.config.graph_store and self.config.graph_store.llm and hasattr(self.config.graph_store.llm, "config"):
            llm_config = self.config.graph_store.llm.config
        elif hasattr(self.config.llm, "config"):
            llm_config = self.config.llm.config
        self.llm = LlmFactory.create(self.llm_provider, llm_config)

        self.user_id = None
        self.threshold = self.config.graph_store.threshold if hasattr(self.config.graph_store, "threshold") else 0.7

        # GAV mutation counter for lazy refresh
        self._mutation_count = 0
        self._gav_refresh_interval = 50
        self._gav_exists = False

        # Ensure schema (vertex type + vector index)
        self._ensure_schema()

    # -- HTTP helpers ----------------------------------------------------------

    def _exec_command(self, language, command, params=None):
        """Execute a command against ArcadeDB's HTTP API.

        Returns the list of result records from the response.
        """
        payload = {"language": language, "command": command}
        if params:
            payload["params"] = params

        resp = requests.post(
            f"{self.url}/api/v1/command/{self.database}",
            json=payload,
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if resp.status_code == 404:
            # Database doesn't exist yet — create it and retry
            self._create_database()
            resp = requests.post(
                f"{self.url}/api/v1/command/{self.database}",
                json=payload,
                auth=self.auth,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])

    def _exec_cypher(self, query, params=None):
        """Execute an OpenCypher query."""
        return self._exec_command("cypher", query, params)

    def _exec_sql(self, query, params=None):
        """Execute a SQL query."""
        return self._exec_command("sql", query, params)

    def _create_database(self):
        """Create the database if it doesn't exist."""
        resp = requests.post(
            f"{self.url}/api/v1/server",
            json={"command": f"create database {self.database}"},
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        # Ignore 400 if database already exists
        if resp.status_code not in (200, 400):
            resp.raise_for_status()

    # -- Schema setup ----------------------------------------------------------

    def _ensure_schema(self):
        """Create the Entity vertex type and HNSW vector index if they don't exist."""
        try:
            self._create_database()
        except Exception:
            pass

        # Create vertex type
        try:
            self._exec_sql("CREATE VERTEX TYPE Entity IF NOT EXISTS")
        except Exception:
            pass

        # Create edge type for relationships
        try:
            self._exec_sql("CREATE EDGE TYPE CONNECTED_TO IF NOT EXISTS")
        except Exception:
            pass

        # Determine embedding dimensions if not known
        if self._embedding_dims is None:
            sample = self.embedding_model.embed("test")
            self._embedding_dims = len(sample)

        # Create HNSW vector index
        try:
            self._exec_sql(
                f"CREATE INDEX ON Entity (embedding) LSM_VECTOR "
                f'METADATA {{"dimensions": {self._embedding_dims}, "similarity": "COSINE"}}'
            )
        except Exception:
            # Index may already exist
            pass

        # Create GAV if enabled
        if self.enable_gav:
            self._ensure_gav()

    def _ensure_gav(self):
        """Create or refresh the Graph Analytics View."""
        try:
            edge_clause = f"EDGE {self.gav_edge_type}" if self.gav_edge_type else "EDGE *"
            self._exec_sql(
                f"CREATE GRAPH ANALYTICS VIEW EntityGAV "
                f"VERTEX {self.gav_vertex_type} "
                f"{edge_clause}"
            )
            self._gav_exists = True
        except Exception:
            # May already exist or not supported in this version
            self._gav_exists = False

    def _maybe_refresh_gav(self):
        """Refresh GAV if mutation threshold reached."""
        if not self.enable_gav or not self._gav_exists:
            return
        if self._mutation_count >= self._gav_refresh_interval:
            try:
                # Drop and recreate
                self._exec_sql("DROP GRAPH ANALYTICS VIEW EntityGAV IF EXISTS")
                self._ensure_gav()
                self._mutation_count = 0
            except Exception as e:
                logger.debug(f"GAV refresh failed: {e}")

    # -- Vector search ---------------------------------------------------------

    def _search_similar_nodes(self, embedding, filters, threshold=None, limit=20):
        """Find similar nodes using ArcadeDB's native HNSW vector index.

        Uses ``vectorNeighbors()`` SQL function, then post-filters by
        user_id/agent_id/run_id in Python.
        """
        if threshold is None:
            threshold = self.threshold

        results = self._exec_sql(
            f"SELECT expand(vectorNeighbors('Entity[embedding]', {json.dumps(embedding)}, {limit}))"
        )

        matches = []
        for record in results:
            props = record if isinstance(record, dict) else {}
            # Filter by scope
            if props.get("user_id") != filters.get("user_id"):
                continue
            if filters.get("agent_id") and props.get("agent_id") != filters["agent_id"]:
                continue
            if filters.get("run_id") and props.get("run_id") != filters["run_id"]:
                continue

            # vectorNeighbors returns a $distance field (cosine distance)
            # Cosine similarity = 1 - cosine distance
            distance = props.get("$distance", 1.0)
            similarity = 1.0 - distance
            if similarity >= threshold:
                matches.append({
                    "name": props.get("name"),
                    "similarity": similarity,
                    "rid": props.get("@rid"),
                    "props": props,
                })

        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches

    # -- Node merge (two-phase) ------------------------------------------------

    def _merge_node(self, user_id, name, embedding, agent_id=None, run_id=None):
        """Create or update an Entity node.

        ArcadeDB's Cypher may not support ``ON CREATE SET / ON MATCH SET``,
        so we use a two-phase approach: MATCH then CREATE/UPDATE.
        """
        # Phase 1: Try to find existing node
        where_parts = ["n.user_id = $user_id", "n.name = $name"]
        params = {"user_id": user_id, "name": name}
        if agent_id:
            where_parts.append("n.agent_id = $agent_id")
            params["agent_id"] = agent_id
        if run_id:
            where_parts.append("n.run_id = $run_id")
            params["run_id"] = run_id
        where_clause = " AND ".join(where_parts)

        existing = self._exec_cypher(
            f"MATCH (n:Entity) WHERE {where_clause} RETURN n",
            params=params,
        )

        if existing:
            # Phase 2a: Update existing node
            update_params = {
                "user_id": user_id,
                "name": name,
                "embedding": embedding,
            }
            if agent_id:
                update_params["agent_id"] = agent_id
            if run_id:
                update_params["run_id"] = run_id

            self._exec_cypher(
                f"MATCH (n:Entity) WHERE {where_clause} "
                f"SET n.mentions = coalesce(n.mentions, 0) + 1, "
                f"n.embedding = $embedding "
                f"RETURN n",
                params=update_params,
            )
        else:
            # Phase 2b: Create new node
            props = {
                "name": name,
                "user_id": user_id,
                "embedding": embedding,
                "mentions": 1,
                "created": int(time.time() * 1000),
            }
            if agent_id:
                props["agent_id"] = agent_id
            if run_id:
                props["run_id"] = run_id

            self._exec_cypher(
                "CREATE (n:Entity $props) RETURN n",
                params={"props": props},
            )

    # -- Public API ------------------------------------------------------------

    def add(self, data, filters):
        """Add data to the graph.

        Args:
            data (str): The data to add to the graph.
            filters (dict): Filters (user_id, agent_id, run_id).
        """
        entity_type_map = self._retrieve_nodes_from_data(data, filters)
        to_be_added = self._establish_nodes_relations_from_data(data, filters, entity_type_map)
        search_output = self._search_graph_db(node_list=list(entity_type_map.keys()), filters=filters)
        to_be_deleted = self._get_delete_entities_from_search_output(search_output, data, filters)

        deleted_entities = self._delete_entities(to_be_deleted, filters)
        added_entities = self._add_entities(to_be_added, filters, entity_type_map)

        self._mutation_count += 1
        self._maybe_refresh_gav()

        return {"deleted_entities": deleted_entities, "added_entities": added_entities}

    def search(self, query, filters, limit=100):
        """Search for memories and related graph data.

        Args:
            query (str): Query to search for.
            filters (dict): Filters (user_id, agent_id, run_id).
            limit (int): Maximum number of relationships to return.

        Returns:
            list: Dicts with keys "source", "relationship", "destination".
        """
        # Lazy GAV refresh before search
        if self.enable_gav and self._gav_exists and self._mutation_count > 0:
            self._maybe_refresh_gav()

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
            result = {"source": item[0], "relationship": item[1], "destination": item[2]}

            # GAV centrality boost if available
            if self.enable_gav and self._gav_exists:
                try:
                    centrality = self._get_pagerank(item[0])
                    if centrality:
                        result["pagerank"] = centrality
                except Exception:
                    pass

            search_results.append(result)

        logger.info(f"Returned {len(search_results)} search results")
        return search_results

    def delete(self, data, filters):
        """Soft-delete graph entities associated with the given memory text.

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
                self._mutation_count += 1
                self._maybe_refresh_gav()
        except Exception as e:
            logger.error(f"Error during graph cleanup for memory delete: {e}")

    def delete_all(self, filters):
        """Delete all nodes and relationships for a user or specific agent."""
        where_parts = ["n.user_id = $user_id"]
        params = {"user_id": filters["user_id"]}
        if filters.get("agent_id"):
            where_parts.append("n.agent_id = $agent_id")
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            where_parts.append("n.run_id = $run_id")
            params["run_id"] = filters["run_id"]
        where_clause = " AND ".join(where_parts)

        self._exec_cypher(
            f"MATCH (n:Entity) WHERE {where_clause} DETACH DELETE n",
            params=params,
        )
        self._mutation_count += 1
        self._maybe_refresh_gav()

    def get_all(self, filters, limit=100):
        """Retrieve all valid relationships for the given scope.

        Args:
            filters (dict): Filters (user_id, agent_id, run_id).
            limit (int): Maximum number of relationships to return.

        Returns:
            list: Dicts with keys "source", "relationship", "target".
        """
        where_parts = ["n.user_id = $user_id", "m.user_id = $user_id"]
        params = {"user_id": filters["user_id"], "limit": limit}
        if filters.get("agent_id"):
            where_parts.extend(["n.agent_id = $agent_id", "m.agent_id = $agent_id"])
            params["agent_id"] = filters["agent_id"]
        if filters.get("run_id"):
            where_parts.extend(["n.run_id = $run_id", "m.run_id = $run_id"])
            params["run_id"] = filters["run_id"]
        where_clause = " AND ".join(where_parts)

        results = self._exec_cypher(
            f"MATCH (n:Entity)-[r]->(m:Entity) "
            f"WHERE {where_clause} AND (r.valid IS NULL OR r.valid = true) "
            f"RETURN n.name AS source, type(r) AS relationship, m.name AS target "
            f"LIMIT $limit",
            params=params,
        )

        final_results = []
        for result in results:
            final_results.append({
                "source": result["source"],
                "relationship": result["relationship"],
                "target": result["target"],
            })

        logger.info(f"Retrieved {len(final_results)} relationships")
        return final_results

    def reset(self):
        """Reset the graph by clearing all nodes and relationships."""
        logger.warning("Clearing graph...")
        self._exec_cypher("MATCH (n) DETACH DELETE n")

    # -- GAV helpers -----------------------------------------------------------

    def _get_pagerank(self, node_name):
        """Get PageRank score for a node from the GAV."""
        try:
            results = self._exec_sql(
                f"SELECT pageRank FROM EntityGAV WHERE name = '{node_name}'"
            )
            if results:
                return results[0].get("pageRank", 0.0)
        except Exception:
            pass
        return None

    # -- LLM-driven extraction -------------------------------------------------

    def _retrieve_nodes_from_data(self, data, filters):
        """Extract entities mentioned in the query using LLM."""
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
        """Establish relations among extracted nodes using LLM."""
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

    # -- Graph DB operations ---------------------------------------------------

    def _search_graph_db(self, node_list, filters, limit=100):
        """Search similar nodes and fetch their relationships."""
        result_relations = []

        for node in node_list:
            n_embedding = self.embedding_model.embed(node)
            similar_nodes = self._search_similar_nodes(n_embedding, filters, limit=limit)

            for sn in similar_nodes[:limit]:
                node_name = sn["name"]
                similarity = sn["similarity"]

                # Build filter params
                params = {"user_id": filters["user_id"], "name": node_name}
                where_parts = ["m.user_id = $user_id"]
                if filters.get("agent_id"):
                    where_parts.append("m.agent_id = $agent_id")
                    params["agent_id"] = filters["agent_id"]
                if filters.get("run_id"):
                    where_parts.append("m.run_id = $run_id")
                    params["run_id"] = filters["run_id"]
                rel_where = " AND ".join(where_parts)

                # Outgoing relationships
                out_results = self._exec_cypher(
                    f"MATCH (n:Entity {{user_id: $user_id, name: $name}})-[r]->(m:Entity) "
                    f"WHERE {rel_where} AND (r.valid IS NULL OR r.valid = true) "
                    f"RETURN n.name AS source, type(r) AS relationship, m.name AS destination",
                    params=params,
                )

                # Incoming relationships
                in_results = self._exec_cypher(
                    f"MATCH (n:Entity {{user_id: $user_id, name: $name}})<-[r]-(m:Entity) "
                    f"WHERE {rel_where} AND (r.valid IS NULL OR r.valid = true) "
                    f"RETURN m.name AS source, type(r) AS relationship, n.name AS destination",
                    params=params,
                )

                for rel in out_results + in_results:
                    rel["similarity"] = similarity
                    result_relations.append(rel)

        return result_relations

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """Use LLM to determine which entities should be deleted."""
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
        """Soft-delete relationships by setting valid=false."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")
        run_id = filters.get("run_id")
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

            result = self._exec_cypher(
                f"MATCH (n:Entity {{{source_props_str}}})"
                f"-[r:{relationship}]->"
                f"(m:Entity {{{dest_props_str}}}) "
                f"WHERE r.valid IS NULL OR r.valid = true "
                f"SET r.valid = false, r.invalidated_at = timestamp() "
                f"RETURN n.name AS source, m.name AS target, type(r) AS relationship",
                params=params,
            )
            results.append(result)

        return results

    def _add_entities(self, to_be_added, filters, entity_type_map):
        """Add new entities to the graph, merging nodes if they already exist."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")
        run_id = filters.get("run_id")
        results = []

        for item in to_be_added:
            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            # Search for similar existing nodes
            source_match = self._search_similar_nodes(source_embedding, filters, threshold=self.threshold, limit=1)
            dest_match = self._search_similar_nodes(dest_embedding, filters, threshold=self.threshold, limit=1)

            effective_source = source_match[0]["name"] if source_match else source
            effective_dest = dest_match[0]["name"] if dest_match else destination

            # Merge source and destination nodes
            self._merge_node(user_id, effective_source, source_embedding, agent_id, run_id)
            self._merge_node(user_id, effective_dest, dest_embedding, agent_id, run_id)

            # Create or update relationship
            rel_params = {
                "source_name": effective_source,
                "dest_name": effective_dest,
                "user_id": user_id,
            }
            if agent_id:
                rel_params["agent_id"] = agent_id
            if run_id:
                rel_params["run_id"] = run_id

            # Check if relationship exists
            existing_rel = self._exec_cypher(
                f"MATCH (s:Entity {{user_id: $user_id, name: $source_name}})"
                f"-[r:{relationship}]->"
                f"(d:Entity {{user_id: $user_id, name: $dest_name}}) "
                f"RETURN r",
                params=rel_params,
            )

            if existing_rel:
                # Update existing relationship
                result = self._exec_cypher(
                    f"MATCH (s:Entity {{user_id: $user_id, name: $source_name}})"
                    f"-[r:{relationship}]->"
                    f"(d:Entity {{user_id: $user_id, name: $dest_name}}) "
                    f"SET r.mentions = coalesce(r.mentions, 0) + 1, "
                    f"r.valid = true, r.updated_at = timestamp(), r.invalidated_at = null "
                    f"RETURN s.name AS source, type(r) AS relationship, d.name AS target",
                    params=rel_params,
                )
            else:
                # Create new relationship via SQL (Cypher CREATE for typed edges)
                # First get RIDs
                source_nodes = self._exec_cypher(
                    "MATCH (s:Entity {user_id: $user_id, name: $source_name}) RETURN s",
                    params={"user_id": user_id, "source_name": effective_source},
                )
                dest_nodes = self._exec_cypher(
                    "MATCH (d:Entity {user_id: $user_id, name: $dest_name}) RETURN d",
                    params={"user_id": user_id, "dest_name": effective_dest},
                )

                if source_nodes and dest_nodes:
                    # Create edge type if needed, then create the edge
                    try:
                        self._exec_sql(f"CREATE EDGE TYPE `{relationship}` IF NOT EXISTS")
                    except Exception:
                        pass

                    source_rid = source_nodes[0].get("@rid") if isinstance(source_nodes[0], dict) else None
                    dest_rid = dest_nodes[0].get("@rid") if isinstance(dest_nodes[0], dict) else None

                    if source_rid and dest_rid:
                        result = self._exec_sql(
                            f"CREATE EDGE `{relationship}` FROM {source_rid} TO {dest_rid} "
                            f"SET valid = true, mentions = 1, "
                            f"created_at = sysdate(), updated_at = sysdate()"
                        )
                    else:
                        # Fallback: use Cypher CREATE
                        result = self._exec_cypher(
                            f"MATCH (s:Entity {{user_id: $user_id, name: $source_name}}), "
                            f"(d:Entity {{user_id: $user_id, name: $dest_name}}) "
                            f"CREATE (s)-[r:{relationship} {{valid: true, mentions: 1}}]->(d) "
                            f"RETURN s.name AS source, type(r) AS relationship, d.name AS target",
                            params=rel_params,
                        )
                else:
                    result = []

            results.append(result)

        return results

    def _remove_spaces_from_entities(self, entity_list):
        return remove_spaces_from_entities(entity_list, sanitize_relationship=True)
