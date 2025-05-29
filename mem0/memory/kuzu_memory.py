import logging
import re

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
            self.config.embedder.provider, self.config.embedder.config, self.config.vector_store.config
        )
        self.embedding_dims = self.embedding_model.config.embedding_dims

        self.db = kuzu.Database(self.config.graph_store.config.db)
        self.graph = kuzu.Connection(self.db)
        self.node_labels = set()
        self.rel_labels = set()

        # Always use the same node table.
        self.node_label = ":Entity"
        self.kuzu_create_node_table(self.node_label)

        self.llm_provider = "openai_structured"
        if self.config.llm.provider:
            self.llm_provider = self.config.llm.provider
        if self.config.graph_store.llm:
            self.llm_provider = self.config.graph_store.llm.provider

        self.llm = LlmFactory.create(self.llm_provider, self.config.llm.config)
        self.user_id = None
        self.threshold = 0.7

    def kuzu_sanitize_table_name(self, table_str):
        return re.sub(r"[^a-z0-9_]", "_", table_str.lower())

    def kuzu_create_node_table(self, node_label):
        assert node_label[0] == ":", f"Node label does not beging with colon: {node_label}"
        assert len(node_label) > 1, "Node label is empty"

        if node_label not in self.node_labels:
            self.kuzu_execute(
                f"CREATE NODE TABLE {node_label[1:]}(id SERIAL PRIMARY KEY, user_id STRING, name STRING, mentions INT64, created TIMESTAMP, embedding FLOAT[{self.embedding_dims}]);"
            )
            self.node_labels.add(node_label)

    def kuzu_create_rel_table(self, rel_label, src_table, dst_table):
        assert len(rel_label) > 0, "Rel label is empty"
        assert src_table[0] == ":", f"Src label does not beging with colon: {dst_table}"
        assert len(src_table) > 1, "Src label is empty"
        assert dst_table[0] == ":", f"Dst label does not beging with colon: {dst_table}"
        assert len(dst_table) > 1, "Dst label is empty"

        if rel_label not in self.rel_labels:
            self.kuzu_execute(
                f"CREATE REL TABLE {rel_label}(FROM {src_table[1:]} TO {dst_table[1:]}, mentions INT64, created TIMESTAMP, updated TIMESTAMP);"
            )
            self.rel_labels.add(rel_label)

    def kuzu_execute(self, query, parameters=None):
        results_obj = self.graph.execute(query, parameters)

        results = []
        col_names = results_obj.get_column_names()
        while results_obj.has_next():
            results.append({key: val for key, val in zip(col_names, results_obj.get_next())})

        return results

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

        # TODO: Batch queries
        # TODO: Add more filter support
        deleted_entities = self._delete_entities(to_be_deleted, filters["user_id"])
        added_entities = self._add_entities(to_be_added, filters["user_id"], entity_type_map)

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

        return search_results

    def delete_all(self, filters):
        cypher = f"""
        MATCH (n {self.node_label} {{user_id: $user_id}})
        DETACH DELETE n
        """
        params = {"user_id": filters["user_id"]}
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
        # return all nodes and relationships
        query = f"""
        MATCH (n {self.node_label} {{user_id: $user_id}})-[r]->(m {self.node_label} {{user_id: $user_id}})
        RETURN n.name AS source, label(r) AS relationship, m.name AS target
        LIMIT $limit
        """
        results = self.kuzu_execute(query, parameters={"user_id": filters["user_id"], "limit": limit})

        final_results = []
        for result in results:
            final_results.append(
                {
                    "source": result["source"],
                    "relationship": result["relationship"],
                    "target": result["target"],
                }
            )

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
        """Eshtablish relations among the extracted nodes."""
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

        entities = []
        if extracted_entities["tool_calls"]:
            entities = extracted_entities["tool_calls"][0]["arguments"]["entities"]

        entities = self._remove_spaces_from_entities(entities)
        logger.debug(f"Extracted entities: {entities}")

        return entities

    def _search_graph_db(self, node_list, filters, limit=100):
        """Search similar nodes among and their respective incoming and outgoing relations."""
        result_relations = []
        for node in node_list:
            n_embedding = self.embedding_model.embed(node)

            results = []
            params = {
                "n_embedding": n_embedding,
                "threshold": self.threshold,
                "user_id": filters["user_id"],
                "limit": limit,
            }
            for cypher in [
                f"""
                MATCH (n {self.node_label})
                WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
                WITH n, round(2 * array_cosine_similarity(n.embedding, CAST($n_embedding,'FLOAT[{self.embedding_dims}]')) - 1, 4) AS similarity // denormalize for backward compatibility
                WHERE similarity >= CAST($threshold, 'DOUBLE')
                MATCH (n)-[r]->(m)
                RETURN n.name AS source, id(n) AS source_id, label(r) AS relationship, id(r) AS relation_id, m.name AS destination, id(m) AS destination_id, similarity
                LIMIT $limit
                """,
                f"""
                MATCH (n {self.node_label})
                WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
                WITH n, round(2 * array_cosine_similarity(n.embedding, CAST($n_embedding,'FLOAT[{self.embedding_dims}]')) - 1, 4) AS similarity // denormalize for backward compatibility
                WHERE similarity >= CAST($threshold, 'DOUBLE')
                MATCH (m)-[r]->(n)
                RETURN n.name AS source, id(n) AS source_id, label(r) AS relationship, id(r) AS relation_id, m.name AS destination, id(m) AS destination_id, similarity
                LIMIT $limit                
                """,
            ]:
                results.extend(self.kuzu_execute(cypher, parameters=params))

            # Kuzu does not support sort/limit over unions. Do it manually for now.
            result_relations.extend(sorted(results, key=lambda x: x["similarity"], reverse=True)[:limit])

        return result_relations

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """Get the entities to be deleted from the search output."""
        search_output_string = format_entities(search_output)
        system_prompt, user_prompt = get_delete_messages(search_output_string, data, filters["user_id"])

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
        # in case if it is not in the correct format
        to_be_deleted = self._remove_spaces_from_entities(to_be_deleted)
        logger.debug(f"Deleted relationships: {to_be_deleted}")

        return to_be_deleted

    def _delete_entities(self, to_be_deleted, user_id):
        """Delete the entities from the graph."""
        results = []
        for item in to_be_deleted:
            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            if relationship not in self.rel_labels:
                logger.debug(f"Tried to delete rel type that does not exist: {relationship}")
                continue

            # Delete the specific relationship between nodes
            cypher = f"""
            MATCH (n {self.node_label} {{name: $source_name, user_id: $user_id}})
            -[r:{relationship}]->
            (m {self.node_label} {{name: $dest_name, user_id: $user_id}})
            DELETE r
            RETURN 
                n.name AS source,
                m.name AS target,
                label(r) AS relationship
            """
            params = {
                "source_name": source,
                "dest_name": destination,
                "user_id": user_id,
            }
            result = self.kuzu_execute(cypher, parameters=params)

            results.append(result)

        return results

    def _add_entities(self, to_be_added, user_id, entity_type_map):
        """Add the new entities to the graph. Merge the nodes if they already exist."""
        results = []
        for item in to_be_added:
            # entities
            source = item["source"]
            source_label = self.node_label

            destination = item["destination"]
            destination_label = self.node_label

            relationship = self.kuzu_sanitize_table_name(item["relationship"])
            self.kuzu_create_rel_table(relationship, source_label, destination_label)

            # embeddings
            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            # search for the nodes with the closest embeddings
            source_node_search_result = self._search_source_node(source_embedding, user_id, threshold=0.9)
            destination_node_search_result = self._search_destination_node(dest_embedding, user_id, threshold=0.9)

            # TODO: Create a cypher query and common params for all the cases
            if not destination_node_search_result and source_node_search_result:
                cypher = f"""
                    MATCH (source)
                    WHERE id(source) = internal_id($table_id, $offset_id)
                    SET source.mentions = coalesce(source.mentions, 0) + 1
                    WITH source
                    MERGE (destination {destination_label} {{name: $destination_name, user_id: $user_id}})
                    ON CREATE SET
                        destination.created = current_timestamp(),
                        destination.mentions = 1,
                        destination.embedding = CAST($destination_embedding,'FLOAT[{self.embedding_dims}]')
                    ON MATCH SET
                        destination.mentions = coalesce(destination.mentions, 0) + 1,
                        destination.embedding = CAST($destination_embedding,'FLOAT[{self.embedding_dims}]')
                    WITH source, destination
                    MERGE (source)-[r:{relationship}]->(destination)
                    ON CREATE SET
                        r.created = current_timestamp(),
                        r.mentions = 1
                    ON MATCH SET
                        r.mentions = coalesce(r.mentions, 0) + 1
                    RETURN source.name AS source, label(r) AS relationship, destination.name AS target
                    """

                params = {
                    "table_id": source_node_search_result[0]["id"]["table"],
                    "offset_id": source_node_search_result[0]["id"]["offset"],
                    "destination_name": destination,
                    "destination_embedding": dest_embedding,
                    "user_id": user_id,
                }
            elif destination_node_search_result and not source_node_search_result:
                cypher = f"""
                    MATCH (destination)
                    WHERE id(destination) = internal_id($table_id, $offset_id)
                    SET destination.mentions = coalesce(destination.mentions, 0) + 1
                    WITH destination
                    MERGE (source {source_label} {{name: $source_name, user_id: $user_id}})
                    ON CREATE SET
                        source.created = current_timestamp(),
                        source.mentions = 1,
                        source.embedding = CAST($source_embedding,'FLOAT[{self.embedding_dims}]')
                    ON MATCH SET
                        source.mentions = coalesce(source.mentions, 0) + 1,
                        source.embedding = CAST($source_embedding,'FLOAT[{self.embedding_dims}]')
                    WITH source, destination
                    MERGE (source)-[r:{relationship}]->(destination)
                    ON CREATE SET 
                        r.created = current_timestamp(),
                        r.mentions = 1
                    ON MATCH SET
                        r.mentions = coalesce(r.mentions, 0) + 1
                    RETURN source.name AS source, label(r) AS relationship, destination.name AS target
                    """

                params = {
                    "table_id": destination_node_search_result[0]["id"]["table"],
                    "offset_id": destination_node_search_result[0]["id"]["offset"],
                    "source_name": source,
                    "source_embedding": source_embedding,
                    "user_id": user_id,
                }
            elif source_node_search_result and destination_node_search_result:
                cypher = f"""
                    MATCH (source)
                    WHERE id(source) = internal_id($src_table, $src_offset)
                    SET source.mentions = coalesce(source.mentions, 0) + 1
                    WITH source
                    MATCH (destination)
                    WHERE id(destination) = internal_id($dst_table, $dst_offset)
                    SET destination.mentions = coalesce(destination.mentions) + 1
                    MERGE (source)-[r:{relationship}]->(destination)
                    ON CREATE SET 
                        r.created = current_timestamp(),
                        r.updated = current_timestamp(),
                        r.mentions = 1
                    ON MATCH SET r.mentions = coalesce(r.mentions, 0) + 1
                    RETURN source.name AS source, label(r) AS relationship, destination.name AS target
                    """
                params = {
                    "src_table": source_node_search_result[0]["id"]["table"],
                    "src_offset": source_node_search_result[0]["id"]["offset"],
                    "dst_table": destination_node_search_result[0]["id"]["table"],
                    "dst_offset": destination_node_search_result[0]["id"]["offset"],
                }
            else:
                cypher = f"""
                    MERGE (source {source_label} {{name: $source_name, user_id: $user_id}})
                    ON CREATE SET
                        source.created = current_timestamp(),
                        source.mentions = 1,
                        source.embedding = CAST($source_embedding,'FLOAT[{self.embedding_dims}]')
                    ON MATCH SET
                        source.mentions = coalesce(source.mentions, 0) + 1,
                        source.embedding = CAST($source_embedding,'FLOAT[{self.embedding_dims}]')
                    WITH source
                    MERGE (destination {destination_label} {{name: $dest_name, user_id: $user_id}})
                    ON CREATE SET
                        destination.created = current_timestamp(),
                        destination.mentions = 1,
                        destination.embedding = CAST($dest_embedding,'FLOAT[{self.embedding_dims}]')
                    ON MATCH SET
                        destination.mentions = coalesce(destination.mentions, 0) + 1,
                        destination.embedding = CAST($dest_embedding,'FLOAT[{self.embedding_dims}]')
                    WITH source, destination
                    MERGE (source)-[rel:{relationship}]->(destination)
                    ON CREATE SET
                        rel.created = current_timestamp(),
                        rel.mentions = 1
                    ON MATCH SET
                        rel.mentions = coalesce(rel.mentions, 0) + 1
                    RETURN source.name AS source, label(rel) AS relationship, destination.name AS target
                    """
                params = {
                    "source_name": source,
                    "dest_name": destination,
                    "source_embedding": source_embedding,
                    "dest_embedding": dest_embedding,
                    "user_id": user_id,
                }
            result = self.kuzu_execute(cypher, parameters=params)

            results.append(result)
        return results

    def _remove_spaces_from_entities(self, entity_list):
        for item in entity_list:
            item["source"] = item["source"].lower().replace(" ", "_")
            item["relationship"] = item["relationship"].lower().replace(" ", "_")
            item["destination"] = item["destination"].lower().replace(" ", "_")
        return entity_list

    def _search_source_node(self, source_embedding, user_id, threshold=0.9):
        cypher = f"""
            MATCH (source_candidate {self.node_label})
            WHERE source_candidate.embedding IS NOT NULL 
            AND source_candidate.user_id = $user_id

            WITH source_candidate,
            round(2 * array_cosine_similarity(source_candidate.embedding, CAST($source_embedding,'FLOAT[{self.embedding_dims}]')) - 1, 4) AS source_similarity // denormalize for backward compatibility
            WHERE source_similarity >= $threshold

            WITH source_candidate, source_similarity
            ORDER BY source_similarity DESC
            LIMIT 1

            RETURN id(source_candidate) as id
            """

        params = {
            "source_embedding": source_embedding,
            "user_id": user_id,
            "threshold": threshold,
        }

        return self.kuzu_execute(cypher, parameters=params)

    def _search_destination_node(self, destination_embedding, user_id, threshold=0.9):
        cypher = f"""
            MATCH (destination_candidate {self.node_label})
            WHERE destination_candidate.embedding IS NOT NULL 
            AND destination_candidate.user_id = $user_id

            WITH destination_candidate,
            round(2 * array_cosine_similarity(destination_candidate.embedding, CAST($destination_embedding,'FLOAT[{self.embedding_dims}]')) - 1, 4) AS destination_similarity // denormalize for backward compatibility

            WHERE destination_similarity >= $threshold

            WITH destination_candidate, destination_similarity
            ORDER BY destination_similarity DESC
            LIMIT 1

            RETURN id(destination_candidate) as id
            """
        params = {
            "destination_embedding": destination_embedding,
            "user_id": user_id,
            "threshold": threshold,
        }

        return self.kuzu_execute(cypher, parameters=params)
