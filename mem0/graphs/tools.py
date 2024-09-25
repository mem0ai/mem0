UPDATE_MEMORY_TOOL_GRAPH = {
    "type": "function",
    "function": {
        "name": "update_graph_memory",
        "description": "Update the relationship key of an existing graph memory based on new information. This function should be called when there's a need to modify an existing relationship in the knowledge graph. The update should only be performed if the new information is more recent, more accurate, or provides additional context compared to the existing information. The source and destination nodes of the relationship must remain the same as in the existing graph memory; only the relationship itself can be updated.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The identifier of the source node in the relationship to be updated. This should match an existing node in the graph.",
                },
                "destination": {
                    "type": "string",
                    "description": "The identifier of the destination node in the relationship to be updated. This should match an existing node in the graph.",
                },
                "relationship": {
                    "type": "string",
                    "description": "The new or updated relationship between the source and destination nodes. This should be a concise, clear description of how the two nodes are connected.",
                },
            },
            "required": ["source", "destination", "relationship"],
            "additionalProperties": False,
        },
    },
}

ADD_MEMORY_TOOL_GRAPH = {
    "type": "function",
    "function": {
        "name": "add_graph_memory",
        "description": "Add a new graph memory to the knowledge graph. This function creates a new relationship between two nodes, potentially creating new nodes if they don't exist.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The identifier of the source node in the new relationship. This can be an existing node or a new node to be created.",
                },
                "destination": {
                    "type": "string",
                    "description": "The identifier of the destination node in the new relationship. This can be an existing node or a new node to be created.",
                },
                "relationship": {
                    "type": "string",
                    "description": "The type of relationship between the source and destination nodes. This should be a concise, clear description of how the two nodes are connected.",
                },
                "source_type": {
                    "type": "string",
                    "description": "The type or category of the source node. This helps in classifying and organizing nodes in the graph.",
                },
                "destination_type": {
                    "type": "string",
                    "description": "The type or category of the destination node. This helps in classifying and organizing nodes in the graph.",
                },
            },
            "required": [
                "source",
                "destination",
                "relationship",
                "source_type",
                "destination_type",
            ],
            "additionalProperties": False,
        },
    },
}


NOOP_TOOL = {
    "type": "function",
    "function": {
        "name": "noop",
        "description": "No operation should be performed to the graph entities. This function is called when the system determines that no changes or additions are necessary based on the current input or context. It serves as a placeholder action when no other actions are required, ensuring that the system can explicitly acknowledge situations where no modifications to the graph are needed.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}


ADD_MESSAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "add_query",
        "description": "Add new entities and relationships to the graph based on the provided query.",
        "parameters": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_node": {"type": "string"},
                            "source_type": {"type": "string"},
                            "relation": {"type": "string"},
                            "destination_node": {"type": "string"},
                            "destination_type": {"type": "string"},
                        },
                        "required": [
                            "source_node",
                            "source_type",
                            "relation",
                            "destination_node",
                            "destination_type",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entities"],
            "additionalProperties": False,
        },
    },
}


SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search for nodes and relations in the graph.",
        "parameters": {
            "type": "object",
            "properties": {
                "nodes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of nodes to search for.",
                },
                "relations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of relations to search for.",
                },
            },
            "required": ["nodes", "relations"],
            "additionalProperties": False,
        },
    },
}

UPDATE_MEMORY_STRUCT_TOOL_GRAPH = {
    "type": "function",
    "function": {
        "name": "update_graph_memory",
        "description": "Update the relationship key of an existing graph memory based on new information. This function should be called when there's a need to modify an existing relationship in the knowledge graph. The update should only be performed if the new information is more recent, more accurate, or provides additional context compared to the existing information. The source and destination nodes of the relationship must remain the same as in the existing graph memory; only the relationship itself can be updated.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The identifier of the source node in the relationship to be updated. This should match an existing node in the graph.",
                },
                "destination": {
                    "type": "string",
                    "description": "The identifier of the destination node in the relationship to be updated. This should match an existing node in the graph.",
                },
                "relationship": {
                    "type": "string",
                    "description": "The new or updated relationship between the source and destination nodes. This should be a concise, clear description of how the two nodes are connected.",
                },
            },
            "required": ["source", "destination", "relationship"],
            "additionalProperties": False,
        },
    },
}

ADD_MEMORY_STRUCT_TOOL_GRAPH = {
    "type": "function",
    "function": {
        "name": "add_graph_memory",
        "description": "Add a new graph memory to the knowledge graph. This function creates a new relationship between two nodes, potentially creating new nodes if they don't exist.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The identifier of the source node in the new relationship. This can be an existing node or a new node to be created.",
                },
                "destination": {
                    "type": "string",
                    "description": "The identifier of the destination node in the new relationship. This can be an existing node or a new node to be created.",
                },
                "relationship": {
                    "type": "string",
                    "description": "The type of relationship between the source and destination nodes. This should be a concise, clear description of how the two nodes are connected.",
                },
                "source_type": {
                    "type": "string",
                    "description": "The type or category of the source node. This helps in classifying and organizing nodes in the graph.",
                },
                "destination_type": {
                    "type": "string",
                    "description": "The type or category of the destination node. This helps in classifying and organizing nodes in the graph.",
                },
            },
            "required": [
                "source",
                "destination",
                "relationship",
                "source_type",
                "destination_type",
            ],
            "additionalProperties": False,
        },
    },
}


NOOP_STRUCT_TOOL = {
    "type": "function",
    "function": {
        "name": "noop",
        "description": "No operation should be performed to the graph entities. This function is called when the system determines that no changes or additions are necessary based on the current input or context. It serves as a placeholder action when no other actions are required, ensuring that the system can explicitly acknowledge situations where no modifications to the graph are needed.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}


ADD_MESSAGE_STRUCT_TOOL = {
    "type": "function",
    "function": {
        "name": "add_query",
        "description": "Add new entities and relationships to the graph based on the provided query.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_node": {"type": "string"},
                            "source_type": {"type": "string"},
                            "relation": {"type": "string"},
                            "destination_node": {"type": "string"},
                            "destination_type": {"type": "string"},
                        },
                        "required": [
                            "source_node",
                            "source_type",
                            "relation",
                            "destination_node",
                            "destination_type",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["entities"],
            "additionalProperties": False,
        },
    },
}


SEARCH_STRUCT_TOOL = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search for nodes and relations in the graph.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "nodes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of nodes to search for.",
                },
                "relations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of relations to search for.",
                },
            },
            "required": ["nodes", "relations"],
            "additionalProperties": False,
        },
    },
}
