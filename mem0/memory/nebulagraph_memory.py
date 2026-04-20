import logging
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from mem0.memory.utils import format_entities, sanitize_relationship_for_cypher

try:
    from nebula3.gclient.net.SessionPool import SessionPool
    from nebula3.Config import SessionPoolConfig
except ImportError:
    raise ImportError("nebula3-python is not installed. Please install it using pip install nebula3-python")

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
from mem0.utils.factory import EmbedderFactory, LlmFactory, VectorStoreFactory

logger = logging.getLogger(__name__)


class MemoryGraph:
    def __init__(self, config):
        self.config = config

        # Initialize NebulaGraph connection
        self._init_nebula_connection()

        # Initialize vector store (Elasticsearch or other)
        vector_store_provider = self.config.vector_store.provider
        graph_collection_name = None
        if self.config.graph_store and self.config.graph_store.config:
            graph_collection_name = getattr(self.config.graph_store.config, "collection_name", None)
        if graph_collection_name:
            collection_name = graph_collection_name
        else:
            base_collection = self.config.vector_store.config.collection_name
            if base_collection:
                collection_name = f"{base_collection}_nebulagraph_vectors"
            else:
                collection_name = "mem0_nebulagraph_vectors"

        if hasattr(self.config.vector_store.config, "model_dump"):
            vector_store_config = self.config.vector_store.config.__class__(
                **self.config.vector_store.config.model_dump()
            )
        else:
            vector_store_config = deepcopy(self.config.vector_store.config)
        vector_store_config.collection_name = collection_name

        self.vector_store = VectorStoreFactory.create(vector_store_provider, vector_store_config)

        # Initialize embedding model
        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider,
            self.config.embedder.config,
            {"enable_embeddings": True},
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
        self.vector_store_limit = 5

        # Create NebulaGraph schema
        self._create_schema()

    def _init_nebula_connection(self):
        """Initialize NebulaGraph SessionPool."""
        pool_config = SessionPoolConfig()
        pool_config.min_size = 1
        pool_config.max_size = 10

        self.session_pool = SessionPool(
            self.config.graph_store.config.username,
            self.config.graph_store.config.password,
            self.config.graph_store.config.space,
            self._parse_graph_addresses(self.config.graph_store.config.graph_address),
        )
        ok = self.session_pool.init(pool_config)

        if not ok:
            raise Exception("Failed to initialize NebulaGraph SessionPool")

        # Verify credentials and selected space through the pool.
        self._execute_raw_query("SHOW TAGS")
        logger.info(
            "Successfully connected to NebulaGraph space %s",
            self.config.graph_store.config.space,
        )

    def _parse_graph_addresses(self, graph_address):
        """Parse a comma-separated NebulaGraph graphd address string into SessionPool tuples."""
        if not graph_address:
            raise ValueError("NebulaGraph graph_address is required")

        addresses = []
        for raw_address in graph_address.split(","):
            address = raw_address.strip()
            if not address:
                continue

            host, sep, port_str = address.rpartition(":")
            if not sep or not host or not port_str:
                raise ValueError("Each NebulaGraph graph_address entry must be in 'host:port' format")

            try:
                port = int(port_str)
            except ValueError as exc:
                raise ValueError(f"Invalid NebulaGraph port in graph_address entry '{address}'") from exc

            addresses.append((host.strip(), port))

        if not addresses:
            raise ValueError("NebulaGraph graph_address did not contain any valid host:port entries")

        return addresses

    def _execute_raw_query(self, query, retry_times=3, retry_interval=1):
        """Execute a raw NGQL query through NebulaGraph SessionPool."""
        retry_times = max(0, int(retry_times))
        retry_interval = max(0.0, float(retry_interval))
        total_attempts = retry_times + 1

        for attempt in range(total_attempts):
            try:
                result = self.session_pool.execute(query)
            except Exception as exc:
                if attempt >= retry_times:
                    raise RuntimeError(
                        f"NebulaGraph query failed after {total_attempts} attempts ({retry_times} retries). "
                        f"Query: {query}"
                    ) from exc

                next_retry = attempt + 1
                logger.warning(
                    "NebulaGraph query raised an exception on attempt %d. Retry %d/%d in %ss. Query: %s. Error: %s",
                    attempt + 1,
                    next_retry,
                    retry_times,
                    retry_interval,
                    query,
                    exc,
                )
                time.sleep(retry_interval)
                continue

            if result.is_succeeded():
                return result

            if attempt >= retry_times:
                raise RuntimeError(
                    f"NebulaGraph query failed after {total_attempts} attempts ({retry_times} retries) "
                    f"[code={result.error_code()}]: {result.error_msg()}. Query: {query}"
                )

            next_retry = attempt + 1
            logger.warning(
                "NebulaGraph query failed on attempt %d [code=%s]: %s. Retry %d/%d in %ss. Query: %s",
                attempt + 1,
                result.error_code(),
                result.error_msg(),
                next_retry,
                retry_times,
                retry_interval,
                query,
            )
            time.sleep(retry_interval)

        raise RuntimeError("Unexpected state in __execute_raw_query")

    def _create_schema(self):
        """Create NebulaGraph schema (Tags and Edge Types)"""
        # Create Entity Tag
        create_tag = """
        CREATE TAG IF NOT EXISTS Entity(
            name string,
            entity_type string,
            user_id string,
            agent_id string,
            created timestamp,
            updated timestamp,
            mentions int
        )
        """
        try:
            self._execute_raw_query(create_tag)
        except RuntimeError as exc:
            logger.warning("Failed to create Entity tag: %s", exc)

        # Create CONNECTED_TO Edge Type (dynamic relationship types will be created on-the-fly)
        # NebulaGraph requires edge types to be predefined, but we'll use a generic one
        create_edge = """
        CREATE EDGE IF NOT EXISTS CONNECTED_TO(
            relationship string,
            user_id string,
            agent_id string,
            created timestamp,
            updated timestamp,
            mentions int
        )
        """
        try:
            self._execute_raw_query(create_edge)
        except RuntimeError as exc:
            logger.warning("Failed to create CONNECTED_TO edge: %s", exc)

        # Create indexes
        if not self._index_exists("tag", "entity_user_id"):
            create_index = "CREATE TAG INDEX IF NOT EXISTS entity_user_id ON Entity(user_id(64))"
            try:
                self._execute_raw_query(create_index)
                # Wait for one heartbeat cycle for index synchronization.
                time.sleep(10)
                rebuild_index = "REBUILD TAG INDEX entity_user_id"
                self._execute_raw_query(rebuild_index)
            except RuntimeError as exc:
                logger.warning("Failed to create or rebuild index entity_user_id: %s", exc)

        if not self._index_exists("edge", "connected_to_relationship"):
            create_index = "CREATE EDGE INDEX IF NOT EXISTS connected_to_relationship ON CONNECTED_TO(relationship(64))"
            try:
                self._execute_raw_query(create_index)
                # Wait for one heartbeat cycle for index synchronization.
                time.sleep(10)
                rebuild_index = "REBUILD EDGE INDEX connected_to_relationship"
                self._execute_raw_query(rebuild_index)
            except RuntimeError as exc:
                logger.warning("Failed to create or rebuild index connected_to_relationship: %s", exc)

        if not self._index_exists("edge", "connected_to_user_agent"):
            create_index = (
                "CREATE EDGE INDEX IF NOT EXISTS connected_to_user_agent ON CONNECTED_TO(user_id(64), agent_id(64))"
            )
            try:
                self._execute_raw_query(create_index)
                # Wait for one heartbeat cycle for index synchronization.
                time.sleep(10)
                rebuild_index = "REBUILD EDGE INDEX connected_to_user_agent"
                self._execute_raw_query(rebuild_index)
            except RuntimeError as exc:
                logger.warning("Failed to create or rebuild index connected_to_user_agent: %s", exc)

        logger.info("NebulaGraph schema created successfully")

    def _execute_query(self, query):
        """Execute a query and return parsed results"""
        result = self._execute_raw_query(query)
        if result.is_empty():
            return []

        results = []
        keys = result.keys() if callable(getattr(result, "keys", None)) else result.keys
        for row in result:
            row_dict = {}
            values = row.values() if callable(getattr(row, "values", None)) else row.values
            for i, col_name in enumerate(keys):
                cell = values[i]
                value = cell.cast() if hasattr(cell, "cast") else cell
                row_dict[col_name.decode("utf-8") if isinstance(col_name, bytes) else col_name] = value
            results.append(row_dict)

        return results

    def _format_vid(self, value):
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        return str(value)

    def _index_exists(self, index_type, index_name):
        query = "SHOW TAG INDEXES" if index_type == "tag" else "SHOW EDGE INDEXES"
        result = self._execute_query(query)
        for row in result:
            for value in row.values():
                if isinstance(value, (bytes, bytearray)):
                    try:
                        value = value.decode("utf-8")
                    except Exception:
                        continue
                if value == index_name:
                    return True
        return False

    def add(self, data, filters):
        """
        Adds data to the graph.

        Args:
            data (str): The data to add to the graph.
            filters (dict): A dictionary containing filters to be applied during the addition.
        """
        embedding_cache = {}
        entity_type_map = self._retrieve_nodes_from_data(data, filters)
        to_be_added = self._establish_nodes_relations_from_data(data, filters, entity_type_map)
        search_output = self._search_graph_db(
            node_list=list(entity_type_map.keys()),
            filters=filters,
            embedding_cache=embedding_cache,
        )
        to_be_deleted = self._get_delete_entities_from_search_output(search_output, data, filters)

        deleted_entities = self._delete_entities(to_be_deleted, filters)
        added_entities = self._add_entities(to_be_added, filters, entity_type_map, embedding_cache=embedding_cache)

        return {"deleted_entities": deleted_entities, "added_entities": added_entities}

    def search(self, query, filters, limit=100):
        """
        Search for memories and related graph data.

        Args:
            query (str): Query to search for.
            filters (dict): A dictionary containing filters to be applied during the search.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 100.

        Returns:
            list: List of related graph data based on the query.
        """
        entity_type_map = self._retrieve_nodes_from_data(query, filters)
        search_output = self._search_graph_db(
            node_list=list(entity_type_map.keys()),
            filters=filters,
            embedding_cache={},
        )

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
        # Delete from graph vector store
        try:
            collection_name = getattr(self.vector_store, "collection_name", "graph_vector_store")
            logger.warning("Resetting index %s (graph vectors by filter)", collection_name)
            vectors = self.vector_store.list(filters=filters)
            if isinstance(vectors, (list, tuple)) and vectors and isinstance(vectors[0], (list, tuple)):
                vectors = vectors[0]
            deleted = 0
            for vec in vectors or []:
                try:
                    self.vector_store.delete(vec.id)
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete graph vector {getattr(vec, 'id', None)}: {e}")
            logger.warning("Deleted %d graph vectors for user_id=%s", deleted, filters.get("user_id"))
        except Exception as e:
            logger.warning(f"Failed to delete graph vectors: {e}")

        # Delete from NebulaGraph
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")
        logger.warning(
            "Deleting NebulaGraph data for user_id=%s%s",
            user_id,
            f", agent_id={agent_id}" if agent_id else "",
        )

        if agent_id:
            query = f"""
            LOOKUP on Entity where Entity.user_id == '{user_id}' \
                AND Entity.agent_id = '{agent_id}' \
            YIELD id(vertex) as id \
            | DELETE VERTEX $-.id WITH EDGE
            """
        else:
            query = f"""
            LOOKUP on Entity where Entity.user_id == '{user_id}' \
            YIELD id(vertex) as id \
            | DELETE VERTEX $-.id WITH EDGE
            """

        self._execute_raw_query(query)
        logger.info(f"Deleted all data for user_id: {user_id}")

    def reset(self):
        """Reset NebulaGraph data and the graph vector store."""
        logger.warning("Clearing graph...")

        if hasattr(self.vector_store, "reset"):
            self.vector_store.reset()
        else:
            logger.warning("Graph vector store does not support reset. Recreating collection manually.")
            self.vector_store.delete_col()
            if hasattr(self.vector_store, "create_index"):
                self.vector_store.create_index()
            elif hasattr(self.vector_store, "create_col"):
                self.vector_store.create_col()

        query = """
        LOOKUP on Entity YIELD id(vertex) as id
        | DELETE VERTEX $-.id WITH EDGE
        """
        return self._execute_raw_query(query)

    def get_all(self, filters, limit=100):
        """
        Retrieves all nodes and relationships from the graph database.

        Args:
            filters (dict): A dictionary containing filters to be applied during the retrieval.
            limit (int): The maximum number of relationships to retrieve. Defaults to 100.

        Returns:
            list: A list of dictionaries containing source, relationship, and target.
        """
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")

        if agent_id:
            query = f"""
            MATCH (n:Entity)-[r:CONNECTED_TO]->(m:Entity)
            WHERE n.Entity.user_id == '{user_id}' AND n.Entity.agent_id == '{agent_id}'
              AND m.Entity.user_id == '{user_id}' AND m.Entity.agent_id == '{agent_id}'
            RETURN n.Entity.name AS source, r.relationship AS relationship, m.Entity.name AS target
            LIMIT {limit}
            """
        else:
            query = f"""
            MATCH (n:Entity)-[r:CONNECTED_TO]->(m:Entity)
            WHERE n.Entity.user_id == '{user_id}' AND m.Entity.user_id == '{user_id}'
            RETURN n.Entity.name AS source, r.relationship AS relationship, m.Entity.name AS target
            LIMIT {limit}
            """

        results = self._execute_query(query)

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
        """Extract all entities mentioned in the query."""
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
        logger.debug(f"Entity type map: {entity_type_map}")
        return entity_type_map

    def _establish_nodes_relations_from_data(self, data, filters, entity_type_map):
        """Establish relations among the extracted nodes."""
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
        if extracted_entities["tool_calls"]:
            entities = extracted_entities["tool_calls"][0]["arguments"]["entities"]

        entities = self._remove_spaces_from_entities(entities)
        logger.debug(f"Extracted entities: {entities}")
        return entities

    def _search_graph_db(self, node_list, filters, limit=100, embedding_cache=None):
        """Search similar nodes and their relationships using vector store."""
        result_relations = []

        for node in node_list:
            n_embedding = self._get_cached_embedding(node, embedding_cache)

            # Search in vector store
            search_nodes = self.vector_store.search(
                query="",
                vectors=n_embedding,
                top_k=self.vector_store_limit,
                filters=filters,
            )

            # Get node IDs that meet threshold
            node_ids = [n.id for n in search_nodes if n.score >= self.threshold]

            if not node_ids:
                continue

            # Query NebulaGraph for relationships
            ids_str = "', '".join(node_ids)
            user_id = filters["user_id"]
            agent_filter = (
                f" AND n.Entity.agent_id == '{filters['agent_id']}' AND m.Entity.agent_id == '{filters['agent_id']}'"
                if filters.get("agent_id")
                else ""
            )

            query = f"""
            MATCH (n:Entity)-[r:CONNECTED_TO]->(m:Entity)
            WHERE id(n) IN ['{ids_str}'] AND n.Entity.user_id == '{user_id}'{agent_filter}
            RETURN n.Entity.name AS source, r.relationship AS relationship, m.Entity.name AS destination
            UNION
            MATCH (n:Entity)<-[r:CONNECTED_TO]-(m:Entity)
            WHERE id(n) IN ['{ids_str}'] AND n.Entity.user_id == '{user_id}'{agent_filter}
            RETURN m.Entity.name AS source, r.relationship AS relationship, n.Entity.name AS destination
            LIMIT {limit}
            """

            relations = self._execute_query(query)
            result_relations.extend(relations)

        return result_relations

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """Get the entities to be deleted from the search output."""
        search_output_string = format_entities(search_output)
        system_prompt, user_prompt = get_delete_messages(search_output_string, data, filters["user_id"])

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
        for item in memory_updates["tool_calls"]:
            if item["name"] == "delete_graph_memory":
                to_be_deleted.append(item["arguments"])

        to_be_deleted = self._remove_spaces_from_entities(to_be_deleted)
        logger.debug(f"Deleted relationships: {to_be_deleted}")
        return to_be_deleted

    def _delete_entities(self, to_be_deleted, filters):
        """Delete the entities from the graph."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id")
        results = []

        page_size = getattr(self.config.graph_store.config, "delete_page_size", 1000)

        for item in to_be_deleted:
            source = item["source"]
            destination = item["destination"]
            relationship = sanitize_relationship_for_cypher(item["relationship"])

            agent_filter = (
                f" AND n.Entity.agent_id == '{agent_id}' AND m.Entity.agent_id == '{agent_id}'" if agent_id else ""
            )

            offset = 0
            while True:
                match_query = f"""
                MATCH (n:Entity)-[r:CONNECTED_TO]->(m:Entity)
                WHERE n.Entity.name == '{source}' AND m.Entity.name == '{destination}'
                  AND n.Entity.user_id == '{user_id}' AND m.Entity.user_id == '{user_id}'
                  AND r.relationship == '{relationship}'{agent_filter}
                RETURN n.Entity.name AS source, m.Entity.name AS target, r.relationship AS relationship,
                       src(r) AS src, dst(r) AS dst, rank(r) AS rank
                ORDER BY src, dst, rank
                SKIP {offset} LIMIT {page_size}
                """

                match_results = self._execute_query(match_query)
                if not match_results:
                    break

                delete_edges = []
                for row in match_results:
                    results.append(
                        {
                            "source": row.get("source"),
                            "target": row.get("target"),
                            "relationship": row.get("relationship"),
                        }
                    )
                    src = self._format_vid(row["src"])
                    dst = self._format_vid(row["dst"])
                    rank = row.get("rank", 0)
                    delete_edges.append(f"{src} -> {dst} @ {rank}")

                delete_query = f"DELETE EDGE CONNECTED_TO {', '.join(delete_edges)}"
                self._execute_raw_query(delete_query)

                if len(match_results) < page_size:
                    break
                offset += page_size

        return results

    def _add_entities(self, to_be_added, filters, entity_type_map, embedding_cache=None):
        """Add new entities to the graph."""
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id", "")
        results = []
        for item in to_be_added:
            source = item["source"]
            destination = item["destination"]
            relationship = sanitize_relationship_for_cypher(item["relationship"])

            source_type = entity_type_map.get(source, "__User__")
            destination_type = entity_type_map.get(destination, "__User__")

            # Generate embeddings
            source_embedding = self._get_cached_embedding(source, embedding_cache)
            dest_embedding = self._get_cached_embedding(destination, embedding_cache)

            # Search for existing nodes
            source_node = self._search_node_in_vector_store(source_embedding, filters)
            dest_node = self._search_node_in_vector_store(dest_embedding, filters)

            # Create nodes if they don't exist
            if source_node:
                source_id = source_node
                if not self._node_exists(source_id):
                    self._create_node(
                        source,
                        source_type,
                        source_embedding,
                        filters,
                        node_id=source_id,
                        insert_vector=False,
                    )
            else:
                source_id = self._create_node(source, source_type, source_embedding, filters)

            if dest_node:
                dest_id = dest_node
                if not self._node_exists(dest_id):
                    self._create_node(
                        destination,
                        destination_type,
                        dest_embedding,
                        filters,
                        node_id=dest_id,
                        insert_vector=False,
                    )
            else:
                dest_id = self._create_node(destination, destination_type, dest_embedding, filters)

            # Avoid collapsing distinct entities onto the same vertex ID
            if source_id == dest_id and source != destination:
                dest_id = self._create_node(destination, destination_type, dest_embedding, filters)

            src_vid = self._format_vid(source_id)
            dst_vid = self._format_vid(dest_id)

            fetch_query = f"FETCH PROP ON CONNECTED_TO {src_vid} -> {dst_vid} YIELD edge AS e"
            edge_exists = bool(self._execute_query(fetch_query))

            if edge_exists:
                update_props = f"mentions = mentions + 1, updated = timestamp(), user_id = '{user_id}'"
                if agent_id:
                    update_props += f", agent_id = '{agent_id}'"
                update_query = f"UPDATE EDGE ON CONNECTED_TO {src_vid} -> {dst_vid} SET {update_props}"
                self._execute_raw_query(update_query)
            else:
                agent_value = f", '{agent_id}'" if agent_id else ", ''"
                insert_query = (
                    "INSERT EDGE CONNECTED_TO (relationship, user_id, agent_id, created, updated, mentions) "
                    f"VALUES {src_vid} -> {dst_vid}: ('{relationship}', '{user_id}'{agent_value}, timestamp(), timestamp(), 1)"
                )
                self._execute_raw_query(insert_query)

            results.append(
                {
                    "source": source,
                    "relationship": relationship,
                    "target": destination,
                }
            )

        return results

    def _get_cached_embedding(self, text, embedding_cache):
        if embedding_cache is None:
            return self.embedding_model.embed(text)
        cached = embedding_cache.get(text)
        if cached is not None:
            return cached
        embedding = self.embedding_model.embed(text)
        embedding_cache[text] = embedding
        return embedding

    def _search_node_in_vector_store(self, embedding, filters):
        """Search for a node in the vector store."""
        search_results = self.vector_store.search(
            query="",
            vectors=embedding,
            top_k=self.vector_store_limit,
            filters=filters,
        )

        threshold_matches = sorted(
            (result for result in search_results if result.score is not None and result.score >= self.threshold),
            key=lambda result: result.score,
            reverse=True,
        )

        if threshold_matches:
            return threshold_matches[0].id

        return None

    def _create_node(self, name, entity_type, embedding, filters, node_id=None, insert_vector=True):
        """Create a new node in NebulaGraph and vector store."""
        node_id = node_id or str(uuid.uuid4())
        user_id = filters["user_id"]
        agent_id = filters.get("agent_id", "")

        # Insert into NebulaGraph
        agent_clause = f", agent_id: '{agent_id}'" if agent_id else ""
        vid = self._format_vid(node_id)

        query = f"""
        INSERT VERTEX Entity(name, entity_type, user_id{", agent_id" if agent_id else ""}, created, mentions)
        VALUES {vid}: ('{name}', '{entity_type}', '{user_id}'{agent_clause}, timestamp(), 1)
        """

        try:
            self._execute_raw_query(query)
        except RuntimeError as exc:
            logger.error("Failed to create node: %s", exc)
            raise Exception(f"Failed to create node: {exc}") from exc

        # Insert into vector store
        payload = {
            "name": name,
            "type": entity_type,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if agent_id:
            payload["agent_id"] = agent_id

        if insert_vector:
            self.vector_store.insert(
                vectors=[embedding],
                payloads=[payload],
                ids=[node_id],
            )

        logger.debug(f"Created node: {node_id} ({name})")
        return node_id

    def _node_exists(self, node_id):
        vid = self._format_vid(node_id)
        result = self._execute_query(f"FETCH PROP ON Entity {vid} YIELD vertex AS v")
        return bool(result)

    def _remove_spaces_from_entities(self, entity_list):
        """Remove spaces from entity names and relationships."""
        for item in entity_list:
            item["source"] = item["source"].lower().replace(" ", "_")
            item["relationship"] = sanitize_relationship_for_cypher(item["relationship"].lower().replace(" ", "_"))
            item["destination"] = item["destination"].lower().replace(" ", "_")
        return entity_list

    def __del__(self):
        """Cleanup connection pool on deletion."""
        if hasattr(self, "session_pool") and self.session_pool:
            self.session_pool.close()
