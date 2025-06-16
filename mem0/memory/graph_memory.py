import logging
from datetime import datetime
import pytz

from mem0.memory.utils import format_entities

try:
    from langchain_neo4j import Neo4jGraph
except ImportError:
    raise ImportError(
        "langchain_neo4j is not installed. Please install it using pip install langchain-neo4j"
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
        self.graph = Neo4jGraph(
            self.config.graph_store.config.url,
            self.config.graph_store.config.username,
            self.config.graph_store.config.password,
        )
        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider, self.config.embedder.config
        )

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

        # TODO: Batch queries with APOC plugin
        # TODO: Add more filter support
        deleted_entities = self._delete_entities(to_be_deleted, filters["user_id"])
        added_entities = self._add_entities(
            to_be_added, filters["user_id"], entity_type_map
        )

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
        search_output = self._search_graph_db(
            node_list=list(entity_type_map.keys()), filters=filters
        )

        if not search_output:
            return []

        search_outputs_sequence = [
            [item["source"], item["relatationship"], item["destination"]]
            for item in search_output
        ]
        bm25 = BM25Okapi(search_outputs_sequence)

        tokenized_query = query.split(" ")
        reranked_results = bm25.get_top_n(tokenized_query, search_outputs_sequence, n=5)

        search_results = []
        current_time_iso = datetime.now(pytz.utc).isoformat()
        
        for item in reranked_results:
            # Find the original item to retrieve all properties
            for orig_item in search_output:
                if (
                    orig_item["source"] == item[0]
                    and orig_item["relatationship"] == item[1]
                    and orig_item["destination"] == item[2]
                ):

                    result_dict = {
                        "source": item[0],
                        "relationship": item[1],
                        "destination": item[2],
                    }

                    # Add optional parameters if they exist
                    if orig_item.get("weight") is not None:
                        result_dict["weight"] = orig_item["weight"]
                    if orig_item.get("is_uncertain") is not None:
                        result_dict["is_uncertain"] = orig_item["is_uncertain"]
                    if orig_item.get("status") is not None:
                        result_dict["status"] = orig_item["status"]
                    if orig_item.get("start_date") is not None:
                        result_dict["start_date"] = orig_item["start_date"]
                    if orig_item.get("end_date") is not None:
                        result_dict["end_date"] = orig_item["end_date"]
                    if orig_item.get("emotion") is not None:
                        result_dict["emotion"] = orig_item["emotion"]
                    if orig_item.get("last_mentioned") is not None:
                        result_dict["last_mentioned"] = orig_item["last_mentioned"]
                    if orig_item.get("usage_count") is not None:
                        result_dict["usage_count"] = orig_item["usage_count"]

                    # Update mention metadata for this selected relationship
                    self.update_mention_metadata(result_dict, current_time_iso, filters["user_id"])
                    
                    # Update mention metadata for nodes referenced in this relationship
                    self.update_node_mention_metadata(item[0], current_time_iso, filters["user_id"])
                    self.update_node_mention_metadata(item[2], current_time_iso, filters["user_id"])

                    search_results.append(result_dict)
                    break
            else:
                # Fallback if original item not found
                fallback_result = {"source": item[0], "relationship": item[1], "destination": item[2]}
                # Still update metadata even for fallback case
                self.update_mention_metadata(fallback_result, current_time_iso, filters["user_id"])
                self.update_node_mention_metadata(item[0], current_time_iso, filters["user_id"])
                self.update_node_mention_metadata(item[2], current_time_iso, filters["user_id"])
                search_results.append(fallback_result)

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
        RETURN 
            n.name AS source, 
            type(r) AS relationship, 
            m.name AS target,
            r.weight AS weight,
            r.is_uncertain AS is_uncertain,
            r.status AS status,
            r.start_date AS start_date,
            r.end_date AS end_date,
            r.emotion AS emotion,
            r.last_mentioned AS last_mentioned,
            r.usage_count AS usage_count
        LIMIT $limit
        """
        results = self.graph.query(
            query, params={"user_id": filters["user_id"], "limit": limit}
        )

        final_results = []
        current_time_iso = datetime.now(pytz.utc).isoformat()
        
        for result in results:
            result_dict = {
                "source": result["source"],
                "relationship": result["relationship"],
                "target": result["target"],
            }

            # Add optional parameters if they exist in the result
            if result.get("weight") is not None:
                result_dict["weight"] = result["weight"]
            if result.get("is_uncertain") is not None:
                result_dict["is_uncertain"] = result["is_uncertain"]
            if result.get("status") is not None:
                result_dict["status"] = result["status"]
            if result.get("start_date") is not None:
                result_dict["start_date"] = result["start_date"]
            if result.get("end_date") is not None:
                result_dict["end_date"] = result["end_date"]
            if result.get("emotion") is not None:
                result_dict["emotion"] = result["emotion"]
            if result.get("last_mentioned") is not None:
                result_dict["last_mentioned"] = result["last_mentioned"]
            if result.get("usage_count") is not None:
                result_dict["usage_count"] = result["usage_count"]

            # Update mention metadata for this retrieved relationship
            self.update_mention_metadata(result_dict, current_time_iso, filters["user_id"])
            
            # Update mention metadata for nodes referenced in this relationship
            self.update_node_mention_metadata(result["source"], current_time_iso, filters["user_id"])
            self.update_node_mention_metadata(result["target"], current_time_iso, filters["user_id"])

            final_results.append(result_dict)

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
            for item in search_results["tool_calls"][0]["arguments"]["entities"]:
                entity_type_map[item["entity"]] = item["entity_type"]
        except Exception as e:
            logger.error(f"Error in search tool: {e}")

        entity_type_map = {
            k.lower().replace(" ", "_"): v.lower().replace(" ", "_")
            for k, v in entity_type_map.items()
        }
        logger.debug(f"Entity type map: {entity_type_map}")
        return entity_type_map

    def _establish_nodes_relations_from_data(self, data, filters, entity_type_map):
        """Eshtablish relations among the extracted nodes."""
        if self.config.graph_store.custom_prompt:
            messages = [
                {
                    "role": "system",
                    "content": EXTRACT_RELATIONS_PROMPT.replace(
                        "USER_ID", filters["user_id"]
                    ).replace(
                        "CUSTOM_PROMPT", f"4. {self.config.graph_store.custom_prompt}"
                    ),
                },
                {"role": "user", "content": data},
            ]
        else:
            messages = [
                {
                    "role": "system",
                    "content": EXTRACT_RELATIONS_PROMPT.replace(
                        "USER_ID", filters["user_id"]
                    ),
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

        if extracted_entities["tool_calls"]:
            extracted_entities = extracted_entities["tool_calls"][0]["arguments"][
                "entities"
            ]
        else:
            extracted_entities = []

        extracted_entities = self._remove_spaces_from_entities(extracted_entities)
        logger.debug(f"Extracted entities: {extracted_entities}")
        return extracted_entities

    def _search_graph_db(self, node_list, filters, limit=100):
        """Search similar nodes among and their respective incoming and outgoing relations."""
        result_relations = []

        for node in node_list:
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
            RETURN 
                n.name AS source, 
                elementId(n) AS source_id, 
                type(r) AS relatationship, 
                elementId(r) AS relation_id, 
                m.name AS destination, 
                elementId(m) AS destination_id, 
                similarity,
                r.weight AS weight,
                r.is_uncertain AS is_uncertain,
                r.status AS status,
                r.start_date AS start_date,
                r.end_date AS end_date,
                r.emotion AS emotion,
                r.last_mentioned AS last_mentioned,
                r.usage_count AS usage_count
            UNION
            MATCH (n)
            WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
            WITH n,
                round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) /
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) *
                sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
            WHERE similarity >= $threshold
            MATCH (m)-[r]->(n)
            RETURN 
                m.name AS source, 
                elementId(m) AS source_id, 
                type(r) AS relatationship, 
                elementId(r) AS relation_id, 
                n.name AS destination, 
                elementId(n) AS destination_id, 
                similarity,
                r.weight AS weight,
                r.is_uncertain AS is_uncertain,
                r.status AS status,
                r.start_date AS start_date,
                r.end_date AS end_date,
                r.emotion AS emotion,
                r.last_mentioned AS last_mentioned,
                r.usage_count AS usage_count
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
            
            # Update mention metadata for relationships found via similarity search
            current_time_iso = datetime.now(pytz.utc).isoformat()
            for relation in ans:
                # Create a memory object for the metadata update
                memory_obj = {
                    "source": relation["source"],
                    "relationship": relation["relatationship"],  # Note: using original misspelling
                    "destination": relation["destination"],
                    "usage_count": relation.get("usage_count", 0)
                }
                
                # Update metadata for this relationship selected via similarity search
                self.update_mention_metadata(memory_obj, current_time_iso, filters["user_id"])
                
                # Update metadata for nodes involved in this relationship
                self.update_node_mention_metadata(relation["source"], current_time_iso, filters["user_id"])
                self.update_node_mention_metadata(relation["destination"], current_time_iso, filters["user_id"])
            
            result_relations.extend(ans)

        return result_relations

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """Get the entities to be deleted from the search output."""
        search_output_string = format_entities(search_output)
        system_prompt, user_prompt = get_delete_messages(
            search_output_string, data, filters["user_id"]
        )

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
            relationship_type = item["relationship"]

            # Check if the relationship exists first
            check_cypher = """
            MATCH (n {name: $source_name, user_id: $user_id})
            MATCH (m {name: $dest_name, user_id: $user_id})
            WITH n, m
            OPTIONAL MATCH (n)-[r]->(m)
            WHERE type(r) = $relationship_type
            RETURN 
                n.name AS source,
                m.name AS target,
                type(r) AS relationship,
                r.weight AS weight,
                r.is_uncertain AS is_uncertain,
                r.status AS status,
                r.start_date AS start_date,
                r.end_date AS end_date,
                r.emotion AS emotion,
                r.last_mentioned AS last_mentioned,
                r.usage_count AS usage_count
            LIMIT 1
            """
            params = {
                "source_name": source,
                "dest_name": destination,
                "user_id": user_id,
                "relationship_type": relationship_type,
            }

            # First fetch the relationship data
            result_data = self.graph.query(check_cypher, params=params)

            # Only delete if relationship exists
            if result_data and result_data[0]["relationship"] is not None:
                # Now delete the relationship
                delete_cypher = """
                MATCH (n {name: $source_name, user_id: $user_id})
                -[r]->(m {name: $dest_name, user_id: $user_id})
                WHERE type(r) = $relationship_type
                DELETE r
                """
                self.graph.query(delete_cypher, params=params)

                # Process the result data to include optional parameters
                result_dict = {
                    "source": result_data[0]["source"],
                    "relationship": result_data[0]["relationship"],
                    "target": result_data[0]["target"],
                }

                # Add optional parameters if they exist
                if result_data[0].get("weight") is not None:
                    result_dict["weight"] = result_data[0]["weight"]
                if result_data[0].get("is_uncertain") is not None:
                    result_dict["is_uncertain"] = result_data[0]["is_uncertain"]
                if result_data[0].get("status") is not None:
                    result_dict["status"] = result_data[0]["status"]
                if result_data[0].get("start_date") is not None:
                    result_dict["start_date"] = result_data[0]["start_date"]
                if result_data[0].get("end_date") is not None:
                    result_dict["end_date"] = result_data[0]["end_date"]
                if result_data[0].get("emotion") is not None:
                    result_dict["emotion"] = result_data[0]["emotion"]
                if result_data[0].get("last_mentioned") is not None:
                    result_dict["last_mentioned"] = result_data[0]["last_mentioned"]
                if result_data[0].get("usage_count") is not None:
                    result_dict["usage_count"] = result_data[0]["usage_count"]

                results.append(result_dict)
            else:
                # Relationship wasn't found, so just return info that we tried to delete it
                logger.debug(
                    f"Relationship {relationship_type} between {source} and {destination} not found"
                )
                results.append(
                    {
                        "source": source,
                        "relationship": relationship_type,
                        "target": destination,
                        "status": "not_found",  # Add a status to indicate relationship wasn't found
                    }
                )
        return results

    def _add_entities(self, to_be_added, user_id, entity_type_map):
        """Add the new entities to the graph. Merge the nodes if they already exist."""
        results = []
        for item in to_be_added:
            # entities
            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            # types
            source_type = entity_type_map.get(source, "unknown")
            destination_type = entity_type_map.get(destination, "unknown")

            # embeddings
            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            # additional parameters
            weight = item.get("weight")
            is_uncertain = item.get("is_uncertain")
            status = item.get("status")
            start_date = item.get("start_date")
            end_date = item.get("end_date")
            emotion = item.get("emotion")
            last_mentioned = item.get("last_mentioned")
            usage_count = item.get("usage_count")

            # search for the nodes with the closest embeddings
            source_node_search_result = self._search_source_node(
                source_embedding, user_id, threshold=0.9
            )
            destination_node_search_result = self._search_destination_node(
                dest_embedding, user_id, threshold=0.9
            )

            # TODO: Create a cypher query and common params for all the cases
            if not destination_node_search_result and source_node_search_result:
                current_formatted_time = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
                
                # Build SET clauses for relationship properties
                relationship_set_clauses = []
                if weight is not None:
                    relationship_set_clauses.append("r.weight = $weight")
                if is_uncertain is not None:
                    relationship_set_clauses.append("r.is_uncertain = $is_uncertain")
                if status is not None:
                    relationship_set_clauses.append("r.status = $status")
                if start_date is not None:
                    relationship_set_clauses.append("r.start_date = $start_date")
                if end_date is not None:
                    relationship_set_clauses.append("r.end_date = $end_date")
                if emotion is not None:
                    relationship_set_clauses.append("r.emotion = $emotion")
                if last_mentioned is not None:
                    relationship_set_clauses.append("r.last_mentioned = $last_mentioned")
                if usage_count is not None:
                    relationship_set_clauses.append("r.usage_count = $usage_count")
                
                additional_set_properties_str = ""
                if relationship_set_clauses:
                    additional_set_properties_str = ", " + ", ".join(relationship_set_clauses)

                cypher = f"""
                    MATCH (source)
                    WHERE elementId(source) = $source_id
                    MERGE (destination:{destination_type} {{name: $destination_name, user_id: $user_id}})
                    ON CREATE SET
                        destination.created_at = $current_formatted_time,
                        destination.embedding = $destination_embedding
                    ON MATCH SET
                        destination.embedding = $destination_embedding
                    MERGE (source)-[r:{relationship}]->(destination)
                    ON CREATE SET 
                        r.created_at = $current_formatted_time,
                        r.usage_count = 1,
                        r.last_mentioned = $current_formatted_time{additional_set_properties_str}
                    ON MATCH SET
                        r.last_mentioned = $current_formatted_time,
                        r.usage_count = COALESCE(r.usage_count, 0) + 1{additional_set_properties_str}
                    RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                    """

                params = {
                    "source_id": source_node_search_result[0][
                        "elementId(source_candidate)"
                    ],
                    "destination_name": destination,
                    "relationship": relationship,
                    "destination_type": destination_type,
                    "destination_embedding": dest_embedding,
                    "user_id": user_id,
                    "current_formatted_time": current_formatted_time,
                }

                # Add additional parameters to params if they exist
                if weight is not None:
                    params["weight"] = weight
                if is_uncertain is not None:
                    params["is_uncertain"] = is_uncertain
                if status is not None:
                    params["status"] = status
                if start_date is not None:
                    params["start_date"] = start_date
                if end_date is not None:
                    params["end_date"] = end_date
                if emotion is not None:
                    params["emotion"] = emotion
                if last_mentioned is not None:
                    params["last_mentioned"] = last_mentioned
                if usage_count is not None:
                    params["usage_count"] = usage_count

                resp = self.graph.query(cypher, params=params)
                results.append(resp)

            elif destination_node_search_result and not source_node_search_result:
                current_formatted_time = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')

                # Build SET clauses for relationship properties
                relationship_set_clauses = []
                if weight is not None:
                    relationship_set_clauses.append("r.weight = $weight")
                if is_uncertain is not None:
                    relationship_set_clauses.append("r.is_uncertain = $is_uncertain")
                if status is not None:
                    relationship_set_clauses.append("r.status = $status")
                if start_date is not None:
                    relationship_set_clauses.append("r.start_date = $start_date")
                if end_date is not None:
                    relationship_set_clauses.append("r.end_date = $end_date")
                if emotion is not None:
                    relationship_set_clauses.append("r.emotion = $emotion")
                if last_mentioned is not None:
                    relationship_set_clauses.append("r.last_mentioned = $last_mentioned")
                if usage_count is not None:
                    relationship_set_clauses.append("r.usage_count = $usage_count")

                additional_set_properties_str = ""
                if relationship_set_clauses:
                    additional_set_properties_str = ", " + ", ".join(relationship_set_clauses)

                cypher = f"""
                    MATCH (destination)
                    WHERE elementId(destination) = $destination_id
                    MERGE (source:{source_type} {{name: $source_name, user_id: $user_id}})
                    ON CREATE SET
                        source.created_at = $current_formatted_time,
                        source.embedding = $source_embedding
                    ON MATCH SET
                        source.embedding = $source_embedding
                    MERGE (source)-[r:{relationship}]->(destination)
                    ON CREATE SET 
                        r.created_at = $current_formatted_time,
                        r.usage_count = 1,
                        r.last_mentioned = $current_formatted_time{additional_set_properties_str}
                    ON MATCH SET
                        r.last_mentioned = $current_formatted_time,
                        r.usage_count = COALESCE(r.usage_count, 0) + 1{additional_set_properties_str}
                    RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                    """

                params = {
                    "destination_id": destination_node_search_result[0][
                        "elementId(destination_candidate)"
                    ],
                    "source_name": source,
                    "relationship": relationship,
                    "source_type": source_type,
                    "source_embedding": source_embedding,
                    "user_id": user_id,
                    "current_formatted_time": current_formatted_time,
                }

                # Add additional parameters to params if they exist
                if weight is not None:
                    params["weight"] = weight
                if is_uncertain is not None:
                    params["is_uncertain"] = is_uncertain
                if status is not None:
                    params["status"] = status
                if start_date is not None:
                    params["start_date"] = start_date
                if end_date is not None:
                    params["end_date"] = end_date
                if emotion is not None:
                    params["emotion"] = emotion
                if last_mentioned is not None:
                    params["last_mentioned"] = last_mentioned
                if usage_count is not None:
                    params["usage_count"] = usage_count

                resp = self.graph.query(cypher, params=params)
                results.append(resp)

            elif source_node_search_result and destination_node_search_result:
                current_formatted_time = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')

                # Build SET clauses for relationship properties
                relationship_set_clauses = []
                if weight is not None:
                    relationship_set_clauses.append("r.weight = $weight")
                if is_uncertain is not None:
                    relationship_set_clauses.append("r.is_uncertain = $is_uncertain")
                if status is not None:
                    relationship_set_clauses.append("r.status = $status")
                if start_date is not None:
                    relationship_set_clauses.append("r.start_date = $start_date")
                if end_date is not None:
                    relationship_set_clauses.append("r.end_date = $end_date")
                if emotion is not None:
                    relationship_set_clauses.append("r.emotion = $emotion")
                if last_mentioned is not None:
                    relationship_set_clauses.append("r.last_mentioned = $last_mentioned")
                if usage_count is not None:
                    relationship_set_clauses.append("r.usage_count = $usage_count")

                additional_set_properties_str = ""
                # For this case, r.updated_at is also set, so check if relationship_set_clauses is non-empty
                # to decide if a comma is needed before r.updated_at or before the additional properties.
                # However, the original code sets r.created_at and r.updated_at unconditionally on merge.
                # We'll stick to adding optional properties after these.
                if relationship_set_clauses:
                    additional_set_properties_str = ", " + ", ".join(relationship_set_clauses)

                cypher = f"""
                    MATCH (source)
                    WHERE elementId(source) = $source_id
                    MATCH (destination)
                    WHERE elementId(destination) = $destination_id
                    MERGE (source)-[r:{relationship}]->(destination)
                    ON CREATE SET 
                        r.created_at = $current_formatted_time,
                        r.updated_at = $current_formatted_time,
                        r.usage_count = 1,
                        r.last_mentioned = $current_formatted_time{additional_set_properties_str}
                    ON MATCH SET
                        r.updated_at = $current_formatted_time,
                        r.last_mentioned = $current_formatted_time,
                        r.usage_count = COALESCE(r.usage_count, 0) + 1{additional_set_properties_str}
                    RETURN source.name AS source, type(r) AS relationship, destination.name AS target
                    """
                params = {
                    "source_id": source_node_search_result[0][
                        "elementId(source_candidate)"
                    ],
                    "destination_id": destination_node_search_result[0][
                        "elementId(destination_candidate)"
                    ],
                    "user_id": user_id,
                    "relationship": relationship,
                    "current_formatted_time": current_formatted_time,
                }

                # Add additional parameters to params if they exist
                if weight is not None:
                    params["weight"] = weight
                if is_uncertain is not None:
                    params["is_uncertain"] = is_uncertain
                if status is not None:
                    params["status"] = status
                if start_date is not None:
                    params["start_date"] = start_date
                if end_date is not None:
                    params["end_date"] = end_date
                if emotion is not None:
                    params["emotion"] = emotion
                if last_mentioned is not None:
                    params["last_mentioned"] = last_mentioned
                if usage_count is not None:
                    params["usage_count"] = usage_count

                resp = self.graph.query(cypher, params=params)
                results.append(resp)

            elif not source_node_search_result and not destination_node_search_result:
                current_formatted_time = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')

                # Build SET clauses for relationship properties
                relationship_set_clauses = [] # Note: using 'rel' here as per original query
                if weight is not None:
                    relationship_set_clauses.append("rel.weight = $weight")
                if is_uncertain is not None:
                    relationship_set_clauses.append("rel.is_uncertain = $is_uncertain")
                if status is not None:
                    relationship_set_clauses.append("rel.status = $status")
                if start_date is not None:
                    relationship_set_clauses.append("rel.start_date = $start_date")
                if end_date is not None:
                    relationship_set_clauses.append("rel.end_date = $end_date")
                if emotion is not None:
                    relationship_set_clauses.append("rel.emotion = $emotion")
                if last_mentioned is not None:
                    relationship_set_clauses.append("rel.last_mentioned = $last_mentioned")
                if usage_count is not None:
                    relationship_set_clauses.append("rel.usage_count = $usage_count")
                
                additional_set_properties_str = ""
                if relationship_set_clauses:
                    additional_set_properties_str = ", " + ", ".join(relationship_set_clauses)

                cypher = f"""
                    MERGE (n:{source_type} {{name: $source_name, user_id: $user_id}})
                    ON CREATE SET 
                        n.created_at = $current_formatted_time, 
                        n.embedding = $source_embedding
                    ON MATCH SET 
                        n.embedding = $source_embedding
                    MERGE (m:{destination_type} {{name: $dest_name, user_id: $user_id}})
                    ON CREATE SET 
                        m.created_at = $current_formatted_time, 
                        m.embedding = $dest_embedding
                    ON MATCH SET 
                        m.embedding = $dest_embedding
                    MERGE (n)-[rel:{relationship}]->(m)
                    ON CREATE SET 
                        rel.created_at = $current_formatted_time,
                        rel.usage_count = 1,
                        rel.last_mentioned = $current_formatted_time{additional_set_properties_str}
                    ON MATCH SET
                        rel.last_mentioned = $current_formatted_time,
                        rel.usage_count = COALESCE(rel.usage_count, 0) + 1{additional_set_properties_str}
                    RETURN n.name AS source, type(rel) AS relationship, m.name AS target
                    """
                params = {
                    "source_name": source,
                    "source_type": source_type,
                    "dest_name": destination,
                    "destination_type": destination_type,
                    "source_embedding": source_embedding,
                    "dest_embedding": dest_embedding,
                    "user_id": user_id,
                    "current_formatted_time": current_formatted_time,
                }

                # Add additional parameters to params if they exist
                if weight is not None:
                    params["weight"] = weight
                if is_uncertain is not None:
                    params["is_uncertain"] = is_uncertain
                if status is not None:
                    params["status"] = status
                if start_date is not None:
                    params["start_date"] = start_date
                if end_date is not None:
                    params["end_date"] = end_date
                if emotion is not None:
                    params["emotion"] = emotion
                if last_mentioned is not None:
                    params["last_mentioned"] = last_mentioned
                if usage_count is not None:
                    params["usage_count"] = usage_count

                resp = self.graph.query(cypher, params=params)
                results.append(resp)
        return results

    def _remove_spaces_from_entities(self, entity_list):
        """
        Process entities by:
        1. Converting entity names to lowercase and replacing spaces with underscores
        2. Ensuring all required parameters are present with default values if missing
        """
        for item in entity_list:
            item["source"] = item["source"].lower().replace(" ", "_")
            item["relationship"] = item["relationship"].lower().replace(" ", "_")
            item["destination"] = item["destination"].lower().replace(" ", "_")

            # Ensure all required parameters are present with default values if missing
            if "weight" not in item or item["weight"] is None:
                item["weight"] = 0.5  # Default medium strength

            if "is_uncertain" not in item or item["is_uncertain"] is None:
                item["is_uncertain"] = False  # Default to certain

            if "status" not in item or item["status"] is None:
                item["status"] = "active"  # Default to active status

            if "emotion" not in item or item["emotion"] is None:
                item["emotion"] = "neutral"  # Default to neutral emotion

            if "last_mentioned" not in item or item["last_mentioned"] is None:
                item["last_mentioned"] = datetime.now(pytz.utc).isoformat()  # Default to current time in ISO format

            if "usage_count" not in item or item["usage_count"] is None:
                item["usage_count"] = 1  # Default to 1

            # Optional date parameters - no defaults for these
            # start_date and end_date can remain null

        return entity_list

    def _search_source_node(self, source_embedding, user_id, threshold=0.9):
        cypher = """
            MATCH (source_candidate)
            WHERE source_candidate.embedding IS NOT NULL 
            AND source_candidate.user_id = $user_id

            WITH source_candidate,
                round(
                    reduce(dot = 0.0, i IN range(0, size(source_candidate.embedding)-1) |
                        dot + source_candidate.embedding[i] * $source_embedding[i]) /
                    (sqrt(reduce(l2 = 0.0, i IN range(0, size(source_candidate.embedding)-1) |
                        l2 + source_candidate.embedding[i] * source_candidate.embedding[i])) *
                    sqrt(reduce(l2 = 0.0, i IN range(0, size($source_embedding)-1) |
                        l2 + $source_embedding[i] * $source_embedding[i])))
                , 4) AS source_similarity
            WHERE source_similarity >= $threshold

            WITH source_candidate, source_similarity
            ORDER BY source_similarity DESC
            LIMIT 1

            RETURN elementId(source_candidate)
            """

        params = {
            "source_embedding": source_embedding,
            "user_id": user_id,
            "threshold": threshold,
        }

        result = self.graph.query(cypher, params=params)
        return result

    def _search_destination_node(self, destination_embedding, user_id, threshold=0.9):
        cypher = """
            MATCH (destination_candidate)
            WHERE destination_candidate.embedding IS NOT NULL 
            AND destination_candidate.user_id = $user_id

            WITH destination_candidate,
                round(
                    reduce(dot = 0.0, i IN range(0, size(destination_candidate.embedding)-1) |
                        dot + destination_candidate.embedding[i] * $destination_embedding[i]) /
                    (sqrt(reduce(l2 = 0.0, i IN range(0, size(destination_candidate.embedding)-1) |
                        l2 + destination_candidate.embedding[i] * destination_candidate.embedding[i])) *
                    sqrt(reduce(l2 = 0.0, i IN range(0, size($destination_embedding)-1) |
                        l2 + $destination_embedding[i] * $destination_embedding[i])))
                , 4) AS destination_similarity
            WHERE destination_similarity >= $threshold

            WITH destination_candidate, destination_similarity
            ORDER BY destination_similarity DESC
            LIMIT 1

            RETURN elementId(destination_candidate)
            """
        params = {
            "destination_embedding": destination_embedding,
            "user_id": user_id,
            "threshold": threshold,
        }

        result = self.graph.query(cypher, params=params)
        return result

    def update_relationship(
        self, source, relationship, destination, user_id, **properties
    ):
        """
        Update a relationship with new properties.

        Args:
            source (str): Source node name
            relationship (str): Relationship type
            destination (str): Destination node name
            user_id (str): User ID
            **properties: Additional properties to update (weight, is_uncertain, status, start_date, end_date, emotion, last_mentioned, usage_count)

        Returns:
            dict: Updated relationship data
        """
        # Build the SET clause dynamically based on provided properties
        current_formatted_time_update = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
        set_clauses = [
            f"r.updated_at = $current_formatted_time_update"
        ]  # Use a distinct param name
        params = {
            "source_name": source,
            "dest_name": destination,
            "user_id": user_id,
            "current_formatted_time_update": current_formatted_time_update,  # Add to params
        }

        # Add each property to the SET clause if provided
        for key, value in properties.items():
            if value is not None:
                set_clauses.append(f"r.{key} = ${key}")
                params[key] = value

        # Create the query with the dynamic SET clause
        set_clause = ", ".join(set_clauses)
        cypher = f"""
        MATCH (n {{name: $source_name, user_id: $user_id}})
        -[r:{relationship}]->
        (m {{name: $dest_name, user_id: $user_id}})
        SET {set_clause}
        RETURN 
            n.name AS source,
            m.name AS target,
            type(r) AS relationship,
            r.weight AS weight,
            r.is_uncertain AS is_uncertain,
            r.status AS status,
            r.start_date AS start_date,
            r.end_date AS end_date,
            r.emotion AS emotion,
            r.last_mentioned AS last_mentioned,
            r.usage_count AS usage_count
        """

        result = self.graph.query(cypher, params=params)

        if result:
            result_dict = {
                "source": result[0]["source"],
                "relationship": result[0]["relationship"],
                "target": result[0]["target"],
            }

            # Add optional parameters if they exist in the result
            if result[0].get("weight") is not None:
                result_dict["weight"] = result[0]["weight"]
            if result[0].get("is_uncertain") is not None:
                result_dict["is_uncertain"] = result[0]["is_uncertain"]
            if result[0].get("status") is not None:
                result_dict["status"] = result[0]["status"]
            if result[0].get("start_date") is not None:
                result_dict["start_date"] = result[0]["start_date"]
            if result[0].get("end_date") is not None:
                result_dict["end_date"] = result[0]["end_date"]
            if result[0].get("emotion") is not None:
                result_dict["emotion"] = result[0]["emotion"]
            if result[0].get("last_mentioned") is not None:
                result_dict["last_mentioned"] = result[0]["last_mentioned"]
            if result[0].get("usage_count") is not None:
                result_dict["usage_count"] = result[0]["usage_count"]

            return result_dict

        return {"source": source, "relationship": relationship, "target": destination}

    def update_mention_metadata(self, memory_object, user_time, user_id, timezone_offset=None):
        """
        Update usage_count and last_mentioned for a memory object (node or relation) when it's selected for use.
        
        Args:
            memory_object (dict): Dictionary representing a node or relation with source, relationship, destination
            user_time (str): Current time in ISO format string (UTC, adjusted to user's local time)
            user_id (str): User ID for filtering
            timezone_offset (float, optional): Offset handling if needed separately
            
        Behavior:
            - If usage_count is not present → initialize to 1
            - If last_mentioned is not present → initialize to user_time
            - If both are present → increment usage_count and overwrite last_mentioned with user_time
        """
        # Extract relationship components
        source = memory_object.get("source")
        relationship = memory_object.get("relationship") or memory_object.get("relatationship")
        destination = memory_object.get("destination") or memory_object.get("target")
        
        if not all([source, relationship, destination]):
            logger.warning(f"Incomplete memory object for update: {memory_object}")
            return
            
        # Get current values or set defaults
        current_usage_count = memory_object.get("usage_count", 0)
        new_usage_count = current_usage_count + 1
        
        # Update the relationship with incremented usage_count and current timestamp
        update_cypher = """
        MATCH (n {name: $source_name, user_id: $user_id})
        -[r]->(m {name: $dest_name, user_id: $user_id})
        WHERE type(r) = $relationship_type
        SET r.usage_count = $new_usage_count,
            r.last_mentioned = $last_mentioned
        RETURN r.usage_count AS updated_count
        """
        
        params = {
            "source_name": source,
            "dest_name": destination,
            "user_id": user_id,
            "relationship_type": relationship,
            "new_usage_count": new_usage_count,
            "last_mentioned": user_time
        }
        
        try:
            result = self.graph.query(update_cypher, params=params)
            if result:
                logger.debug(f"Updated mention metadata: {source} -> {relationship} -> {destination} (count: {new_usage_count})")
            else:
                logger.warning(f"No relationship found to update: {source} -> {relationship} -> {destination}")
        except Exception as e:
            logger.error(f"Error updating mention metadata: {e}")

    def update_node_mention_metadata(self, node_name, user_time, user_id, timezone_offset=None):
        """
        Update usage_count and last_mentioned for a node when it's actively referenced.
        
        Args:
            node_name (str): Name of the node
            user_time (str): Current time in ISO format string (UTC, adjusted to user's local time)  
            user_id (str): User ID for filtering
            timezone_offset (float, optional): Offset handling if needed separately
        """
        # Update node metadata
        update_cypher = """
        MATCH (n {name: $node_name, user_id: $user_id})
        SET n.usage_count = COALESCE(n.usage_count, 0) + 1,
            n.last_mentioned = $last_mentioned
        RETURN n.usage_count AS updated_count
        """
        
        params = {
            "node_name": node_name,
            "user_id": user_id,
            "last_mentioned": user_time
        }
        
        try:
            result = self.graph.query(update_cypher, params=params)
            if result:
                logger.debug(f"Updated node mention metadata: {node_name} (count: {result[0]['updated_count']})")
            else:
                logger.warning(f"No node found to update: {node_name}")
        except Exception as e:
            logger.error(f"Error updating node mention metadata: {e}")
