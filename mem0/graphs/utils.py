from mem0.llms.openai import OpenAILLM

UPDATE_GRAPH_PROMPT = """
You are an AI expert specializing in graph memory management and optimization. Your task is to analyze existing graph memories alongside new information, and update the relationships in the memory list to ensure the most accurate, current, and coherent representation of knowledge.

Input:
1. Existing Graph Memories: A list of current graph memories, each containing source, target, and relationship information.
2. New Graph Memory: Fresh information to be integrated into the existing graph structure.

Guidelines:
1. Identification: Use the source and target as primary identifiers when matching existing memories with new information.

2. Conflict Resolution:
   - If new information contradicts an existing memory:
     a) For matching source and target but differing content, update the relationship of the existing memory.
     b) If the new memory provides more recent or accurate information, update the existing memory accordingly.

3. Comprehensive Review: Thoroughly examine each existing graph memory against the new information, updating relationships as necessary. Multiple updates may be required.

4. Consistency: Maintain a uniform and clear style across all memories. Each entry should be concise yet comprehensive.

5. Semantic Coherence: Ensure that updates maintain or improve the overall semantic structure of the graph.

6. Temporal Awareness: If timestamps are available, consider the recency of information when making updates.

7. Relationship Refinement: Look for opportunities to refine relationship descriptions for greater precision or clarity.

8. Redundancy Elimination: Identify and merge any redundant or highly similar relationships that may result from the update.

Task Details:
- Existing Graph Memories:
{existing_memories}

- New Graph Memory: {memory}

Output:
Provide a list of update instructions, each specifying the source, target, and the new relationship to be set. Only include memories that require updates.
"""



UPDATE_MEMORY_TOOL_GRAPH = {
    "type": "function",
    "function": {
        "name": "update_graph_memory",
        "description": "Update the relationship key of an existing graph memory based on new information",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source of the relationship to update"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination of the relationship to update"
                },
                "relationship": {
                    "type": "string",
                    "description": "Updated relationship"
                }
            },
            "required": ["source", "destination", "relationship"]
        }
    }
}

ADD_MEMORY_TOOL_GRAPH = {
    "type": "function",
    "function": {
        "name": "add_graph_memory",
        "description": "Add a new graph memory to the graph",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source of the new relationship to add"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination of the new relationship to add"
                },
                "relationship": {
                    "type": "string",
                    "description": "New relationship"
                },
                "source_type": {
                    "type": "string",
                    "description": "Source type of the new relationship to add"
                },
                "destination_type": {
                    "type": "string",
                    "description": "Destination type of the new relationship to add"
                }
            },
            "required": ["source", "destination", "relationship", "source_type", "destination_type"]
        }
    }
}


def get_update_memory_prompt(existing_memories, memory, template):
    return template.format(existing_memories=existing_memories, memory=memory)

def get_update_memory_messages(existing_memories, memory):
    return [
        {
            "role": "user",
            "content": get_update_memory_prompt(existing_memories, memory, UPDATE_GRAPH_PROMPT),
        },
    ]

def get_search_results(entities, query):

    SEARCH_GRAPH_PROMPT = f"""
You are an expert at searching through graph entity memories. 
When provided with existing graph entities and a query, your task is to search through the provided graph entities to find the most relevant information from the graph entities related to the query.
The output should be from the graph entities only.

Here are the details of the task:
- Existing Graph Entities (source -> relationship -> target):
{entities}

- Query: {query}

The output should be from the graph entities only.
The output should be in the following JSON format:
{{
    "search_results": [
        {{
            "source_node": "source_node",
            "relationship": "relationship",
            "target_node": "target_node"
        }}
    ]
}}
"""

    messages = [
        {
            "role": "user",
            "content": SEARCH_GRAPH_PROMPT,
        }
    ]

    llm = OpenAILLM()

    results = llm.generate_response(messages=messages, response_format={"type": "json_object"})

    return results