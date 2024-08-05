UPDATE_MEMORY_PROMPT = """
You are an expert at merging, updating, and organizing memories. When provided with existing memories and new information, your task is to merge and update the memory list to reflect the most accurate and current information. You are also provided with the matching score for each existing memory to the new information. Make sure to leverage this information to make informed decisions about which memories to update or merge.

Guidelines:
- Eliminate duplicate memories and merge related memories to ensure a concise and updated list.
- If a memory is directly contradicted by new information, critically evaluate both pieces of information:
    - If the new memory provides a more recent or accurate update, replace the old memory with new one.
    - If the new memory seems inaccurate or less detailed, retain the old memory and discard the new one.
- Maintain a consistent and clear style throughout all memories, ensuring each entry is concise yet informative.
- If the new memory is a variation or extension of an existing memory, update the existing memory to reflect the new information.

Here are the details of the task:
- Existing Memories:
{existing_memories}

- New Memory: {memory}
"""

MEMORY_DEDUCTION_PROMPT = """
Deduce the facts, preferences, and memories from the provided text.
Just return the facts, preferences, and memories in bullet points:
Natural language text: {user_input}
User/Agent details: {metadata}

Constraint for deducing facts, preferences, and memories:
- The facts, preferences, and memories should be concise and informative.
- Don't start by "The person likes Pizza". Instead, start with "Likes Pizza".
- Don't remember the user/agent details provided. Only remember the facts, preferences, and memories.

Deduced facts, preferences, and memories:
"""

MEMORY_ANSWER_PROMPT = """
You are an expert at answering questions based on the provided memories. Your task is to provide accurate and concise answers to the questions by leveraging the information given in the memories.

Guidelines:
- Extract relevant information from the memories based on the question.
- If no relevant information is found, make sure you don't say no information is found. Instead, accept the question and provide a general response.
- Ensure that the answers are clear, concise, and directly address the question.

Here are the details of the task:
"""

FUNCTION_CALLING_PROMPT = """
You are an expert in function calling. Your task is to analyze user conversations, identify the appropriate functions to call from the provided list, and return the function calls in JSON format. 

Function List:
[
    {
        "type": "function",
        "function": {
            "name": "add_memory",
            "description": "Add a memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "Data to add to memory, natural language text"},
                },
                "required": ["data"],
            },
        },
    },
    {
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
                        "description": "Updated data for the memory, natural language text",
                    },
                },
                "required": ["memory_id", "data"],
            },
        },
    },
    {
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
            },
        },
    }
]


Each function in the list above includes:
- "name": The name of the function
- "description": A brief description of what the function does
- "parameters": The required parameters for the function
  - "type": The data type of the parameters
  - "properties": Specific properties of the parameters
  - "required": List of required parameters

Your responsibilities:
1. Carefully read and understand the user's conversation.
2. Identify which function(s) from the provided list are relevant to the user's request.
3. For each relevant function:
   a. Ensure all required parameters are included and properly formatted.
   b. Strictly follow data type of the parameters.
   c. Extract or infer parameter values from the user's conversation.
4. Construct a JSON object for each function call with the following structure:
   {
     "name": "function_name",
     "parameters": {
       "param1": "value1",
       "param2": "value2",
       ...
     }
   }
5. If multiple functions are needed, return an array of these JSON objects.

Guidelines for response:
- Do not make contradictory function calls. Ensure all function calls are logically consistent with each other and the user's request.
- Ensure all required parameters are included in your function calls.
- Only call update_memory or delete_memory if a memory_id is present in the user's request.
- Do not call both update_memory and delete_memory on the same memory_id.
- Strictly follow the JSON format provided in the example response below.

Example response format:
{
  "function_calls": [
    {
      "name": "function_1",
      "parameters": {
        "data": "Name is John"
      }
    },
  ]
}

CRITICAL: Your entire response must be a single JSON object. Do not write anything before or after the JSON. Do not explain your reasoning or provide any commentary. Only output the function calls JSON.
    
Now, please analyze the following conversation and provide the appropriate function call(s):
"""