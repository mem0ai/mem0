# TODO: Remove these tools if no issues are found for new memory addition logic

ADD_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "add_memory",
        "description": "Add a memory",
        "parameters": {
            "type": "object",
            "properties": {"data": {"type": "string", "description": "Data to add to memory"}},
            "required": ["data"],
            "additionalProperties": False,
        },
    },
}

UPDATE_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "update_memory",
        "description": "Update memory provided ID and data",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "memory_id of the memory to update",
                },
                "data": {
                    "type": "string",
                    "description": "Updated data for the memory",
                },
            },
            "required": ["memory_id", "data"],
            "additionalProperties": False,
        },
    },
}

DELETE_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "delete_memory",
        "description": "Delete memory by memory_id",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "memory_id of the memory to delete",
                }
            },
            "required": ["memory_id"],
            "additionalProperties": False,
        },
    },
}
