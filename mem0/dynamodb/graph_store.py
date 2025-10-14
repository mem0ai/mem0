"""
DynamoDB implementation for graph database functionality in mem0.
"""

import json
import uuid
from typing import Any, Dict, List, Optional

import boto3

from mem0.dynamodb.utils import get_utc_timestamp


class DynamoDBMemoryGraph:
    """
    DynamoDB implementation of memory graph storage.

    This implementation models graph relationships in DynamoDB using a flexible
    schema that supports nodes, edges, and properties.
    """

    def __init__(self, config):
        """
        Initialize DynamoDB graph store.

        Args:
            config: Configuration containing AWS region, table name, etc.
        """
        self.config = config
        self.table_name = config.table_name
        self.region = config.region

        # Initialize LLM for entity extraction
        from mem0.utils.factory import LlmFactory

        if hasattr(config, "llm") and config.llm:
            self.llm = LlmFactory.create(config.llm.provider, config.llm.config)
            self.llm_provider = config.llm.provider
        else:
            self.llm = None
            self.llm_provider = None

        # Initialize DynamoDB client
        kwargs = {"region_name": self.region}
        if config.endpoint_url:
            kwargs["endpoint_url"] = config.endpoint_url
        if not config.use_iam_role:
            if config.aws_access_key_id and config.aws_secret_access_key:
                kwargs["aws_access_key_id"] = config.aws_access_key_id
                kwargs["aws_secret_access_key"] = config.aws_secret_access_key

        self.dynamodb = boto3.resource("dynamodb", **kwargs)
        self.table = self.dynamodb.Table(self.table_name)

    def create_memory_node(self, memory_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a memory node in the graph.

        Args:
            memory_id: Unique identifier for the memory
            content: Memory content
            metadata: Optional metadata for the memory

        Returns:
            node_id: Identifier for the created node
        """
        node_id = memory_id or str(uuid.uuid4())
        timestamp = get_utc_timestamp()

        item = {
            "node_id": node_id,
            "edge_id": "META",  # Special edge_id value for node metadata
            "content": content,
            "type": "memory_node",
            "created_at": timestamp,
        }

        if metadata:
            item["metadata"] = json.dumps(metadata)

        self.table.put_item(Item=item)
        return node_id

    def create_relationship(
        self, source_id: str, target_id: str, relationship_type: str, properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a relationship between two memory nodes.

        Args:
            source_id: Source node identifier
            target_id: Target node identifier
            relationship_type: Type of relationship
            properties: Optional properties for the relationship

        Returns:
            edge_id: Identifier for the created edge
        """
        edge_id = str(uuid.uuid4())
        timestamp = get_utc_timestamp()

        # Store the outgoing edge
        outgoing_item = {
            "node_id": source_id,
            "edge_id": f"OUT#{edge_id}",
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            "direction": "outgoing",
            "created_at": timestamp,
        }

        # Store the incoming edge (for bidirectional traversal)
        incoming_item = {
            "node_id": target_id,
            "edge_id": f"IN#{edge_id}",
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            "direction": "incoming",
            "created_at": timestamp,
        }

        if properties:
            property_json = json.dumps(properties)
            outgoing_item["properties"] = property_json
            incoming_item["properties"] = property_json

        # Use a transaction to ensure both edges are created atomically
        self.dynamodb.meta.client.transact_write_items(
            TransactItems=[
                {"Put": {"TableName": self.table_name, "Item": outgoing_item}},
                {"Put": {"TableName": self.table_name, "Item": incoming_item}},
            ]
        )

        # If GSI is enabled, add an entry to the relationship type index
        if self.config.enable_gsi:
            gsi_item = {
                "relationship_type": relationship_type,
                "created_at": timestamp,
                "node_id": relationship_type,  # Using relationship_type as node_id for GSI
                "edge_id": f"REL#{edge_id}",
                "source_id": source_id,
                "target_id": target_id,
            }

            if properties:
                gsi_item["properties"] = property_json

            self.table.put_item(Item=gsi_item)

        return edge_id

    def get_related_memories(
        self, node_id: str, relationship_types: Optional[List[str]] = None, direction: str = "outgoing", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get memories related to a given node.

        Args:
            node_id: Node identifier
            relationship_types: Optional list of relationship types to filter by
            direction: 'outgoing', 'incoming', or 'both'
            limit: Maximum number of related memories to return

        Returns:
            related_memories: List of related memory dictionaries
        """
        related_memories = []

        # Define which edge types to query based on direction
        edge_prefixes = []
        if direction in ["outgoing", "both"]:
            edge_prefixes.append("OUT#")
        if direction in ["incoming", "both"]:
            edge_prefixes.append("IN#")

        # Query for each edge prefix
        for edge_prefix in edge_prefixes:
            # Query for edges with the specified prefix
            query_params = {
                "KeyConditionExpression": "node_id = :node_id AND begins_with(edge_id, :edge_prefix)",
                "ExpressionAttributeValues": {":node_id": node_id, ":edge_prefix": edge_prefix},
                "Limit": limit,
            }

            response = self.table.query(**query_params)

            # Process edges
            for edge in response.get("Items", []):
                # Skip if filtering by relationship type and this edge doesn't match
                if relationship_types and edge["relationship_type"] not in relationship_types:
                    continue

                # Get the related node ID (source or target, depending on direction)
                related_id = edge["target_id"] if edge_prefix == "OUT#" else edge["source_id"]

                # Get the related node's data
                node_response = self.table.get_item(Key={"node_id": related_id, "edge_id": "META"})

                if "Item" in node_response:
                    node = node_response["Item"]
                    related_memories.append(
                        {
                            "node_id": node["node_id"],
                            "content": node["content"],
                            "relationship": edge["relationship_type"],
                            "metadata": json.loads(node.get("metadata", "{}")),
                            "edge_properties": json.loads(edge.get("properties", "{}")),
                        }
                    )

                # Stop if we've reached the limit
                if len(related_memories) >= limit:
                    break

            # Stop if we've reached the limit
            if len(related_memories) >= limit:
                break

        return related_memories

    def get_memories_by_relationship_type(self, relationship_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get memories connected by a specific relationship type.

        Args:
            relationship_type: Type of relationship to query
            limit: Maximum number of memories to return

        Returns:
            memories: List of memory dictionaries
        """
        if not self.config.enable_gsi:
            raise ValueError("This method requires GSI to be enabled in the configuration")

        memories = []

        # Query the relationship type index
        response = self.table.query(
            IndexName=self.config.gsi_name,
            KeyConditionExpression="relationship_type = :rel_type",
            ExpressionAttributeValues={":rel_type": relationship_type},
            Limit=limit,
        )

        # Process results
        for edge in response.get("Items", []):
            source_response = self.table.get_item(Key={"node_id": edge["source_id"], "edge_id": "META"})

            target_response = self.table.get_item(Key={"node_id": edge["target_id"], "edge_id": "META"})

            if "Item" in source_response and "Item" in target_response:
                source = source_response["Item"]
                target = target_response["Item"]

                # Extract edge_id from the edge_id field (format: "REL#{edge_id}")
                edge_id_parts = edge["edge_id"].split("#", 1)
                edge_id = edge_id_parts[1] if len(edge_id_parts) > 1 else edge["edge_id"]

                memories.append(
                    {
                        "edge_id": edge_id,
                        "relationship_type": edge["relationship_type"],
                        "source": {
                            "node_id": source["node_id"],
                            "content": source["content"],
                            "metadata": json.loads(source.get("metadata", "{}")),
                        },
                        "target": {
                            "node_id": target["node_id"],
                            "content": target["content"],
                            "metadata": json.loads(target.get("metadata", "{}")),
                        },
                        "properties": json.loads(edge.get("properties", "{}")),
                    }
                )

        return memories

    def update_node(
        self, node_id: str, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update a memory node.

        Args:
            node_id: Node identifier
            content: Optional updated content
            metadata: Optional updated metadata

        Returns:
            success: True if update was successful
        """
        update_parts = []
        expression_values = {}

        if content is not None:
            update_parts.append("content = :content")
            expression_values[":content"] = content

        if metadata is not None:
            update_parts.append("metadata = :metadata")
            expression_values[":metadata"] = json.dumps(metadata)

        if not update_parts:
            return True  # Nothing to update

        update_parts.append("updated_at = :updated_at")
        expression_values[":updated_at"] = get_utc_timestamp()

        update_expression = "SET " + ", ".join(update_parts)

        try:
            self.table.update_item(
                Key={"node_id": node_id, "edge_id": "META"},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
            )
            return True
        except Exception as e:
            print(f"Error updating node: {e}")
            return False

    def delete_node(self, node_id: str) -> bool:
        """
        Delete a memory node and all its relationships.

        Args:
            node_id: Node identifier

        Returns:
            success: True if deletion was successful
        """
        try:
            # Get all outgoing edges
            outgoing_response = self.table.query(
                KeyConditionExpression="node_id = :node_id AND begins_with(edge_id, :edge_prefix)",
                ExpressionAttributeValues={":node_id": node_id, ":edge_prefix": "OUT#"},
            )

            # Get all incoming edges
            incoming_response = self.table.query(
                KeyConditionExpression="node_id = :node_id AND begins_with(edge_id, :edge_prefix)",
                ExpressionAttributeValues={":node_id": node_id, ":edge_prefix": "IN#"},
            )

            # Collect all edges to delete
            edges_to_delete = []

            # Process outgoing edges
            for edge in outgoing_response.get("Items", []):
                # Extract edge_id from the edge_id field (format: "OUT#{edge_id}")
                edge_id_parts = edge["edge_id"].split("#", 1)
                edge_id = edge_id_parts[1] if len(edge_id_parts) > 1 else edge["edge_id"]

                edges_to_delete.append(
                    {
                        "edge_id": edge_id,
                        "source_id": edge["source_id"],
                        "target_id": edge["target_id"],
                        "relationship_type": edge["relationship_type"],
                    }
                )

            # Process incoming edges
            for edge in incoming_response.get("Items", []):
                # Extract edge_id from the edge_id field (format: "IN#{edge_id}")
                edge_id_parts = edge["edge_id"].split("#", 1)
                edge_id = edge_id_parts[1] if len(edge_id_parts) > 1 else edge["edge_id"]

                edges_to_delete.append(
                    {
                        "edge_id": edge_id,
                        "source_id": edge["source_id"],
                        "target_id": edge["target_id"],
                        "relationship_type": edge["relationship_type"],
                    }
                )

            # Delete all edges
            for edge in edges_to_delete:
                # Delete outgoing edge
                self.table.delete_item(Key={"node_id": edge["source_id"], "edge_id": f"OUT#{edge['edge_id']}"})

                # Delete incoming edge
                self.table.delete_item(Key={"node_id": edge["target_id"], "edge_id": f"IN#{edge['edge_id']}"})

                # Delete from GSI if enabled
                if self.config.enable_gsi:
                    self.table.delete_item(
                        Key={"node_id": edge["relationship_type"], "edge_id": f"REL#{edge['edge_id']}"}
                    )

            # Finally, delete the node itself
            self.table.delete_item(Key={"node_id": node_id, "edge_id": "META"})

            return True
        except Exception as e:
            print(f"Error deleting node: {e}")
            return False

    def add(self, data, filters):
        """
        Adds data to the graph by extracting entities and relationships.

        Args:
            data (str): The data to add to the graph.
            filters (dict): A dictionary containing filters to be applied during the addition.

        Returns:
            dict: A dictionary containing deleted_entities and added_entities lists.
        """
        if not self.llm:
            # Fallback: create simple memory node
            node_id = self.create_memory_node(memory_id=None, content=data, metadata=filters)
            return {"deleted_entities": [], "added_entities": [node_id]}

        try:
            # Extract entities and relationships using LLM
            entity_type_map = self._retrieve_nodes_from_data(data, filters)
            relationships = self._establish_nodes_relations_from_data(data, filters, entity_type_map)

            added_entities = []

            # Create memory nodes for entities
            for entity, entity_type in entity_type_map.items():
                node_id = self.create_memory_node(
                    memory_id=None,
                    content=f"{entity} ({entity_type})",
                    metadata={**filters, "entity_type": entity_type, "source_data": data},
                )
                added_entities.append(node_id)

            # Create relationships
            for rel in relationships:
                if rel.get("source") and rel.get("target"):
                    rel_id = self.create_relationship(
                        source_id=rel["source"],
                        target_id=rel["target"],
                        relationship_type=rel.get("relationship", "RELATED"),
                        properties={**filters, "source_data": data},
                    )
                    added_entities.append(rel_id)

            return {"deleted_entities": [], "added_entities": added_entities}

        except Exception as e:
            print(f"Error adding to graph: {e}")
            # Fallback: create simple memory node
            node_id = self.create_memory_node(memory_id=None, content=data, metadata=filters)
            return {"deleted_entities": [], "added_entities": [node_id]}

    def search(self, query, filters, limit=100):
        """
        Search for relevant memories in the graph.

        Args:
            query (str): The search query.
            filters (dict): A dictionary containing filters to be applied during the search.
            limit (int): Maximum number of results to return.

        Returns:
            list: A list of search results with contexts and entities.
        """
        try:
            # Extract entities from query
            entity_type_map = self._retrieve_nodes_from_data(query, filters) if self.llm else {}

            results = []

            # Search by entities if found
            if entity_type_map:
                for entity in entity_type_map.keys():
                    # Get related memories for this entity
                    related = self.get_related_memories(entity, limit=limit // len(entity_type_map) + 1)
                    for memory in related:
                        results.append({"contexts": [memory.get("content", "")], "entities": [entity]})

            # Fallback: search all memories for user
            if not results:
                all_memories = self.get_all(filters, limit)
                results = all_memories

            return results[:limit]

        except Exception as e:
            print(f"Error searching graph: {e}")
            return []

    def get_all(self, filters, limit=100):
        """
        Get all memories from the graph.

        Args:
            filters (dict): A dictionary containing filters (user_id, agent_id, run_id).
            limit (int): Maximum number of results to return.

        Returns:
            list: A list of all memories with contexts and entities.
        """
        try:
            # Query all memory nodes for the user
            user_id = filters.get("user_id")
            if not user_id:
                return []

            # Build query parameters
            filter_expression = "user_id = :user_id"
            expression_values = {":user_id": user_id}

            # Add optional filters
            if filters.get("agent_id"):
                filter_expression += " AND agent_id = :agent_id"
                expression_values[":agent_id"] = filters["agent_id"]

            if filters.get("run_id"):
                filter_expression += " AND run_id = :run_id"
                expression_values[":run_id"] = filters["run_id"]

            # Query memory nodes
            response = self.table.scan(
                FilterExpression=filter_expression, ExpressionAttributeValues=expression_values, Limit=limit
            )

            # Convert to expected format
            results = []
            for item in response.get("Items", []):
                if item.get("edge_id") == "META":  # Only memory nodes, not edges
                    results.append({"contexts": [item.get("content", "")], "entities": [item.get("node_id", "")]})

            return results

        except Exception as e:
            print(f"Error getting all memories: {e}")
            return []

    def _retrieve_nodes_from_data(self, data, filters):
        """Extracts all the entities mentioned in the query."""
        if not self.llm:
            return {}

        from mem0.graphs.tools import EXTRACT_ENTITIES_TOOL, EXTRACT_ENTITIES_STRUCT_TOOL

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
            print(f"Error extracting entities: {e}")

        return entity_type_map

    def _establish_nodes_relations_from_data(self, data, filters, entity_type_map):
        """Establish relations among the extracted nodes."""
        if not self.llm or not entity_type_map:
            return []

        from mem0.graphs.tools import EXTRACT_RELATIONS_TOOL, EXTRACT_RELATIONS_STRUCT_TOOL
        from mem0.graphs.prompts import EXTRACT_RELATIONS_PROMPT

        # Compose user identification string for prompt
        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        _tools = [EXTRACT_RELATIONS_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [EXTRACT_RELATIONS_STRUCT_TOOL]

        system_content = EXTRACT_RELATIONS_PROMPT.replace("USER_ID", user_identity)
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"List of entities: {list(entity_type_map.keys())}. \n\nText: {data}"},
        ]

        try:
            search_results = self.llm.generate_response(messages=messages, tools=_tools)
            relations = []
            for tool_call in search_results["tool_calls"]:
                if tool_call["name"] != "extract_relations":
                    continue
                for item in tool_call["arguments"]["relations"]:
                    relations.append(item)
            return relations
        except Exception as e:
            print(f"Error extracting relations: {e}")
            return []
