ADD_MEMORY_TOOL_CN = {
    "type": "function",
    "function": {
        "name": "add_memory",
        "description": "添加记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "将数据添加到记忆"}
            },
            "required": ["data"],
        },
    },
}

UPDATE_MEMORY_TOOL_CN = {
    "type": "function",
    "function": {
        "name": "update_memory",
        "description": "更新记忆编码和数据",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "要更新记忆的编码",
                },
                "data": {
                    "type": "string",
                    "description": "要更新的数据",
                },
            },
            "required": ["memory_id", "data"],
        },
    },
}

DELETE_MEMORY_TOOL_CN = {
    "type": "function",
    "function": {
        "name": "delete_memory",
        "description": "根据编码删除记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "要删除记忆的编码",
                }
            },
            "required": ["memory_id"],
        },
    },
}
