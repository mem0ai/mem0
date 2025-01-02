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

Memory Format:
source -- RELATIONSHIP -- destination

Task Details:
======= Existing Graph Memories:=======
{existing_memories}

======= New Graph Memory:=======
{new_memories}

Output:
Provide a list of update instructions, each specifying the source, target, and the new relationship to be set. Only include memories that require updates.
"""

EXTRACT_RELATIONS_PROMPT = """

You are an advanced algorithm designed to extract structured information from text to construct knowledge graphs. Your goal is to capture comprehensive and accurate information. Follow these key principles:

1. Extract only explicitly stated information from the text.
2. Establish relationships among the entities provided.
3. Use "USER_ID" as the source entity for any self-references (e.g., "I," "me," "my," etc.) in user messages.
CUSTOM_PROMPT

Relationships:
    - Use consistent, general, and timeless relationship types.
    - Example: Prefer "PROFESSOR" over "BECAME_PROFESSOR."
    - Relationships should only be established among the entities explicitly mentioned in the user message.

Entity Consistency:
    - Ensure that relationships are coherent and logically align with the context of the message.
    - Maintain consistent naming for entities across the extracted data.

Strive to construct a coherent and easily understandable knowledge graph by eshtablishing all the relationships among the entities and adherence to the user’s context.

Adhere strictly to these guidelines to ensure high-quality knowledge graph extraction."""

FALKORDB_QUERY = """
MATCH (n)
WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
WITH n, 
    reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) / 
    (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) * 
    sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))) AS similarity
WHERE similarity >= $threshold
MATCH (n)-[r]->(m)
RETURN n.name AS source, Id(n) AS source_id, type(r) AS relation, Id(r) AS relation_id, m.name AS destination, Id(m) AS destination_id, similarity
UNION
MATCH (n)
WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
WITH n, 
    reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) / 
    (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) * 
    sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))) AS similarity
WHERE similarity >= $threshold
MATCH (m)-[r]->(n)
RETURN m.name AS source, Id(m) AS source_id, type(r) AS relation, Id(r) AS relation_id, n.name AS destination, Id(n) AS destination_id, similarity
ORDER BY similarity DESC
"""
            
            
NEO4J_QUERY = """
MATCH (n)
WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
WITH n, 
    round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) / 
    (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) * 
    sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
WHERE similarity >= $threshold
MATCH (n)-[r]->(m)
RETURN n.name AS source, elementId(n) AS source_id, type(r) AS relation, elementId(r) AS relation_id, m.name AS destination, elementId(m) AS destination_id, similarity
UNION
MATCH (n)
WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
WITH n, 
    round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) / 
    (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) * 
    sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
WHERE similarity >= $threshold
MATCH (m)-[r]->(n)
RETURN m.name AS source, elementId(m) AS source_id, type(r) AS relation, elementId(r) AS relation_id, n.name AS destination, elementId(n) AS destination_id, similarity
ORDER BY similarity DESC
"""

def get_update_memory_prompt(existing_memories, new_memories, template):
    return template.format(existing_memories=existing_memories, new_memories=new_memories)


def get_update_memory_messages(existing_memories, new_memories):
    return [
        {
            "role": "user",
            "content": get_update_memory_prompt(existing_memories, new_memories, UPDATE_GRAPH_PROMPT),
        },
    ]
