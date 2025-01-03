import logging

from mem0.memory.utils import format_entities

try:
    from langchain_community.graphs import Neo4jGraph
except ImportError:
    raise ImportError("langchain_community is not installed. Please install it using pip install langchain-community")

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    raise ImportError("rank_bm25 is not installed. Please install it using 'pip install rank-bm25'")

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

        # We'll store these IDs and use them in queries
        self.user_id = None
        self.agent_id = None
        self.run_id = None
        self.threshold = 0.7

    def add(self, data, filters):
        """
        Adds data to the graph with user_id, agent_id, run_id if provided in filters.
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
        Search for related info in the graph by matching node embeddings
        and also factoring in user_id, agent_id, run_id if present.
        """
        entity_type_map = self._retrieve_nodes_from_data(query, filters)
        search_output = self._search_graph_db(node_list=list(entity_type_map.keys()), filters=filters, limit=limit)

        if not search_output:
            return []

        search_outputs_sequence = [[item["source"], item["relatationship"], item["destination"]] for item in search_output]
        bm25 = BM25Okapi(search_outputs_sequence)

        tokenized_query = query.split(" ")
        reranked_results = bm25.get_top_n(tokenized_query, search_outputs_sequence, n=5)

        search_results = []
        for item in reranked_results:
            search_results.append({"source": item[0], "relationship": item[1], "target": item[2]})

        logger.info(f"Returned {len(search_results)} search results")
        return search_results

    def delete_all(self, filters):
        """
        Delete all nodes (and relationships) matching user_id/agent_id/run_id as needed.
        """
        delete_clause = self._make_filter_clause(filters)
        if delete_clause:
            cypher = f"""
            MATCH (n) 
            WHERE {delete_clause}
            DETACH DELETE n
            """
        else:
            # If no filters, do nothing or delete everything? Usually we want a filter to avoid meltdown.
            raise ValueError("Refusing to delete all nodes in graph without any filter. Provide user_id/agent_id/run_id.")
        params = self._make_filter_params(filters)
        self.graph.query(cypher, params=params)

    def get_all(self, filters, limit=100):
        """
        Retrieves all nodes/relationships matching the filters (user_id, agent_id, run_id).
        """
        filter_clause = self._make_filter_clause(filters, alias="n")
        filter_clause_m = self._make_filter_clause(filters, alias="m")

        cypher = f"""
        MATCH (n)-[r]->(m)
        WHERE {filter_clause} AND {filter_clause_m}
        RETURN n.name AS source, type(r) AS relationship, m.name AS target
        LIMIT $limit
        """
        params = self._make_filter_params(filters)
        params["limit"] = limit

        results = self.graph.query(cypher, params=params)

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
        _tools = [EXTRACT_ENTITIES_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [EXTRACT_ENTITIES_STRUCT_TOOL]
        search_results = self.llm.generate_response(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a smart assistant who understands entities and their types in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use {filters.get('user_id','USER')} as the source entity. Extract all the entities from the text. ***DO NOT*** answer the question itself if the given text is a question.",
                },
                {"role": "user", "content": data},
            ],
            tools=_tools,
        )

        entity_type_map = {}

        try:
            for item in search_results["tool_calls"][0]["arguments"]["entities"]:
                entity_type_map[item["entity"]] = item["entity_type"]
        except Exception as e:
            logger.error(f"Error in search tool: {e}")

        entity_type_map = {k.lower().replace(" ", "_"): v.lower().replace(" ", "_") for k, v in entity_type_map.items()}
        logger.debug(f"Entity type map: {entity_type_map}")
        return entity_type_map

    def _establish_nodes_relations_from_data(self, data, filters, entity_type_map):
        if self.config.graph_store.custom_prompt:
            messages = [
                {
                    "role": "system",
                    "content": EXTRACT_RELATIONS_PROMPT.replace("USER_ID", filters.get("user_id","USER")).replace(
                        "CUSTOM_PROMPT", f"4. {self.config.graph_store.custom_prompt}"
                    ),
                },
                {"role": "user", "content": f"List of entities: {list(entity_type_map.keys())}. \n\nText: {data}"},
            ]
        else:
            messages = [
                {
                    "role": "system",
                    "content": EXTRACT_RELATIONS_PROMPT.replace("USER_ID", filters.get("user_id","USER")),
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

        extracted_entities = self._remove_spaces_from_entities(extracted_entities)
        logger.debug(f"Extracted entities: {extracted_entities}")
        return extracted_entities

    def _search_graph_db(self, node_list, filters, limit=100):
        """
        For each node in node_list, embed it and find close matches. Also filter by user_id/agent_id/run_id if present.
        """
        result_relations = []
        for node in node_list:
            n_embedding = self.embedding_model.embed(node)

            # Build optional filter match using the same approach
            filter_clause = self._make_filter_clause(filters, alias="n")
            filter_clause_other = self._make_filter_clause(filters, alias="m")

            cypher_query = f"""
            MATCH (n)
            WHERE n.embedding IS NOT NULL 
              AND {filter_clause}
            WITH n,
                round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) /
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) *
                sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
            WHERE similarity >= $threshold
            MATCH (n)-[r]->(m)
            WHERE {filter_clause_other}
            RETURN n.name AS source, elementId(n) AS source_id, type(r) AS relatationship,
                   elementId(r) AS relation_id, m.name AS destination, elementId(m) AS destination_id, similarity

            UNION

            MATCH (n)
            WHERE n.embedding IS NOT NULL
              AND {filter_clause}
            WITH n,
                round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) /
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) *
                sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
            WHERE similarity >= $threshold
            MATCH (m)-[r]->(n)
            WHERE {filter_clause_other}
            RETURN m.name AS source, elementId(m) AS source_id, type(r) AS relatationship,
                   elementId(r) AS relation_id, n.name AS destination, elementId(n) AS destination_id, similarity
            ORDER BY similarity DESC
            LIMIT $limit
            """

            params = {
                "n_embedding": n_embedding,
                "threshold": self.threshold,
                "limit": limit,
            }
            params.update(self._make_filter_params(filters))

            ans = self.graph.query(cypher_query, params=params)
            result_relations.extend(ans)

        return result_relations

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """
        Decide which relationships to delete (contradictions).
        """
        search_output_string = format_entities(search_output)
        system_prompt, user_prompt = get_delete_messages(search_output_string, data, filters.get("user_id","USER"))

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
        for item in memory_updates["tool_calls"]:
            if item["name"] == "delete_graph_memory":
                to_be_deleted.append(item["arguments"])
        to_be_deleted = self._remove_spaces_from_entities(to_be_deleted)
        logger.debug(f"Deleted relationships: {to_be_deleted}")
        return to_be_deleted

    def _delete_entities(self, to_be_deleted, filters):
        results = []
        for item in to_be_deleted:
            source = item["source"]
            destination = item["destination"]
            relatationship = item["relationship"]

            # Also require that the user_id/agent_id/run_id match to avoid accidental global deletion
            filter_clause_source = self._make_filter_clause(filters, alias="n", extra="n.name = $source_name")
            filter_clause_dest = self._make_filter_clause(filters, alias="m", extra="m.name = $dest_name")

            cypher = f"""
            MATCH (n)-[r:{relatationship}]->(m)
            WHERE {filter_clause_source}
              AND {filter_clause_dest}
            DELETE r
            RETURN n.name AS source, m.name AS destination, type(r) AS deleted_relationship
            """

            params = {
                "source_name": source,
                "dest_name": destination,
            }
            params.update(self._make_filter_params(filters))

            result = self.graph.query(cypher, params=params)
            results.append(result)
        return results

    def _add_entities(self, to_be_added, filters, entity_type_map):
        """
        Merge or create new entities, set user_id/agent_id/run_id, then create the relationship.
        """
        results = []
        for item in to_be_added:
            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            source_type = entity_type_map.get(source, "unknown")
            destination_type = entity_type_map.get(destination, "unknown")

            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            source_node_search_result = self._search_single_node(source_embedding, filters)
            destination_node_search_result = self._search_single_node(dest_embedding, filters)

            # Build queries to handle each scenario:
            if not destination_node_search_result and source_node_search_result:
                # we have source node, but not destination
                cypher = f"""
                MATCH (source)
                WHERE elementId(source) = $source_id
                MERGE (destination:{destination_type} {{
                    name: $destination_name
                }})
                ON CREATE SET
                    destination.created = timestamp(),
                    destination.embedding = $dest_embedding,
                    destination.user_id = $user_id,
                    destination.agent_id = $agent_id,
                    destination.run_id = $run_id
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET r.created = timestamp()
                RETURN source.name AS source, type(r) AS relationship, destination.name AS destination
                """

                params = {
                    "source_id": source_node_search_result[0]['elementId(node_candidate)'],
                    "destination_name": destination,
                    "dest_embedding": dest_embedding,
                }
                params.update(self._make_filter_params(filters))
                resp = self.graph.query(cypher, params=params)
                results.append(resp)

            elif destination_node_search_result and not source_node_search_result:
                # we have destination node, but not source
                cypher = f"""
                MATCH (destination)
                WHERE elementId(destination) = $destination_id
                MERGE (source:{source_type} {{
                    name: $source_name
                }})
                ON CREATE SET
                    source.created = timestamp(),
                    source.embedding = $source_embedding,
                    source.user_id = $user_id,
                    source.agent_id = $agent_id,
                    source.run_id = $run_id
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET r.created = timestamp()
                RETURN source.name AS source, type(r) AS relationship, destination.name AS destination
                """

                params = {
                    "destination_id": destination_node_search_result[0]['elementId(node_candidate)'],
                    "source_name": source,
                    "source_embedding": source_embedding,
                }
                params.update(self._make_filter_params(filters))
                resp = self.graph.query(cypher, params=params)
                results.append(resp)

            elif source_node_search_result and destination_node_search_result:
                # both exist
                cypher = f"""
                MATCH (source)
                WHERE elementId(source) = $source_id
                MATCH (destination)
                WHERE elementId(destination) = $destination_id
                MERGE (source)-[r:{relationship}]->(destination)
                ON CREATE SET 
                    r.created_at = timestamp()
                RETURN source.name AS source, type(r) AS relationship, destination.name AS destination
                """
                # we won't overwrite the user/agent/run in the existing node
                params = {
                    "source_id": source_node_search_result[0]['elementId(node_candidate)'],
                    "destination_id": destination_node_search_result[0]['elementId(node_candidate)'],
                }
                resp = self.graph.query(cypher, params=params)
                results.append(resp)

            else:
                # neither exist
                cypher = f"""
                MERGE (n:{source_type} {{
                    name: $source_name
                }})
                ON CREATE SET
                    n.created = timestamp(),
                    n.embedding = $source_embedding,
                    n.user_id = $user_id,
                    n.agent_id = $agent_id,
                    n.run_id = $run_id

                MERGE (m:{destination_type} {{
                    name: $dest_name
                }})
                ON CREATE SET
                    m.created = timestamp(),
                    m.embedding = $dest_embedding,
                    m.user_id = $user_id,
                    m.agent_id = $agent_id,
                    m.run_id = $run_id

                MERGE (n)-[rel:{relationship}]->(m)
                ON CREATE SET rel.created = timestamp()
                RETURN n.name AS source, type(rel) AS relationship, m.name AS destination
                """

                params = {
                    "source_name": source,
                    "dest_name": destination,
                    "source_embedding": source_embedding,
                    "dest_embedding": dest_embedding,
                }
                params.update(self._make_filter_params(filters))
                resp = self.graph.query(cypher, params=params)
                results.append(resp)
        return results

    def _search_single_node(self, embedding, filters):
        """
        Search for a single node by embedding, plus user_id, agent_id, run_id filters if any.
        """
        filter_clause = self._make_filter_clause(filters, alias="node_candidate")

        cypher = f"""
            MATCH (node_candidate)
            WHERE node_candidate.embedding IS NOT NULL
              AND {filter_clause}
            WITH node_candidate,
                round(
                    reduce(dot = 0.0, i IN range(0, size(node_candidate.embedding)-1) |
                        dot + node_candidate.embedding[i] * $embedding[i]) /
                    (sqrt(reduce(l2 = 0.0, i IN range(0, size(node_candidate.embedding)-1) |
                        l2 + node_candidate.embedding[i] * node_candidate.embedding[i])) *
                    sqrt(reduce(l2 = 0.0, i IN range(0, size($embedding)-1) |
                        l2 + $embedding[i] * $embedding[i])))
                , 4) AS node_similarity
            WHERE node_similarity >= $threshold
            ORDER BY node_similarity DESC
            LIMIT 1
            RETURN elementId(node_candidate)
        """

        params = {
            "embedding": embedding,
            "threshold": 0.9,
        }
        params.update(self._make_filter_params(filters))
        result = self.graph.query(cypher, params=params)
        return result

    def _remove_spaces_from_entities(self, entity_list):
        for item in entity_list:
            item["source"] = item["source"].lower().replace(" ", "_")
            item["relationship"] = item["relationship"].lower().replace(" ", "_")
            item["destination"] = item["destination"].lower().replace(" ", "_")
        return entity_list

    def _make_filter_clause(self, filters, alias="n", extra=None):
        """
        Build a partial WHERE expression for user_id, agent_id, run_id.
        If none are provided, allow all.
        If some are provided, must match them if not null.
        """
        conditions = []
        if "user_id" in filters:
            conditions.append(f"{alias}.user_id = $user_id")
        if "agent_id" in filters:
            conditions.append(f"({alias}.agent_id = $agent_id)")
        if "run_id" in filters:
            conditions.append(f"({alias}.run_id = $run_id)")

        if extra:
            conditions.append(extra)

        if not conditions:
            # means no filter, so let it be pass-through
            return "TRUE"
        else:
            return " AND ".join(conditions)

    def _make_filter_params(self, filters):
        """
        Always provide user_id, agent_id, run_id as None if not present, to avoid parameter missing errors.
        """
        return {
            "user_id": filters.get("user_id", None),
            "agent_id": filters.get("agent_id", None),
            "run_id": filters.get("run_id", None),
        }
