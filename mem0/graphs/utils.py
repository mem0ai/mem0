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
9. Relationship Equivalence: Detect and consolidate semantically identical relationships.
    For example: `plans_to_visit`, `plans_to_travel`, and `will_travel_in` must be merged into one (`PLANS_TO_TRAVEL`).
    If two relationships differ but mean the same, keep only the standardized one.

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

You are an advanced algorithm designed to extract structured information from text to construct knowledge graphs. Your goal is to capture comprehensive and accurate information. 
Please notice that the user will provide you the information in Spanish, so you will need to extract the information in Spanish and then normalize it to English. 
The knowledge graph must not contain information in Spanish, it must be in English.

Follow these key principles:

1. Normalize and translate all entity and relationship names to English.
2. Extract only explicitly stated information from the text.
3. Establish relationships among the entities provided.
4. Use "USER_ID" as the source entity for any self-references (e.g., "I," "me," "my," etc.) in user messages.
5. Follow strict rules to ensure graph consistency and coherence.

ENTITY RULES:
1. All nodes must use the label `:Entity`. No other labels are allowed.
2. There must be exactly one user node (with name: USER_ID, user_id: USER_ID).
3. Normalize all entity names:
   - Convert to lowercase.
   - Remove accents and "ñ".
   - Replace spaces with underscores.
   - Remove special characters except underscores.
   - Translate to English if necessary.
4. NEVER create any node without at least one relationship.
5. NEVER create any relationship with nodes that do not exist in the graph.
6. Do not generate empty, partial, or invalid commands.
7. User information goes in ONE node only
8. Normalize age nodes to: `21_yeras`, `22_years`, etc.
    - Avoid plain numbers as node names.
    - Prefer consistent naming like `21_years`, `may_2023`, etc.
9. Translate and normalize all entity names before graph generation.
10. Do NOT create a new node if another normalized (translated) version already exists. For example:
     - `matematicas` → `mathematics`
     - `ingenieria_informatica` → `computer_science`
     Use existing normalized node instead of duplicating it.

11. Do not generate self-loops (e.g., `paciente -- HAS_NAME --> paciente`).
12. Do NOT use nodes without any relationships. Every node must be part of a meaningful connection.
13. Every relationship must come from an allowed list and must include `created: datetime()`.

RELATIONSHIP RULES:
1. Use only normalized, meaningful types like:
   - `:STUDIES_AT`, `:LIVES_IN`, `:LIKES`, `:PLANS_TO_TRAVEL`, `:HAS_SCHEDULED`, `:TRAVELS_WITH`, `:RELATED_TO`
2. NEVER create multiple relationships that mean the same thing (e.g., `plans_to_travel`, `will_travel_in`, `plans_to_visit`)
   → Use only one (`:PLANS_TO_TRAVEL`)
3. All relationships must include `created: datetime()`
4. Relationship types must be ALL_CAPS and use underscores
5. Never use dynamic relationship types. Always use literal relationship names.
6. Relationships should only be established among the entities explicitly mentioned in the user message.
7. DO NOT create any relationship without both source and destination nodes.

STRUCTURE:
1. Always use MERGE to avoid duplicates.
2. Do not repeat existing relationships or entities.
3. Always verify that the entities and relationships you are creating do not already exist in the graph before creating them.
4. If a concept is already represented in the graph, do not create it again.

Entity Consistency:
    - Ensure that relationships are coherent and logically align with the context of the message.
    - Maintain consistent naming for entities across the extracted data.
    - Before establishing a relationship between two nodes, ensure that there is not already a relationship meaning the same thing between them.

Strive to construct a coherent and easily understandable knowledge graph by establishing all the relationships among the entities and adherence to the user’s context.

Adhere strictly to these guidelines to ensure high-quality knowledge graph extraction."""

DELETE_RELATIONS_SYSTEM_PROMPT = """
You are a graph memory manager specializing in identifying, managing, and optimizing relationships within graph-based memories. Your primary task is to analyze a list of existing relationships and determine which ones should be deleted based on the new information provided.
Input:
1. Existing Graph Memories: A list of current graph memories, each containing source, relationship, and destination information.
2. New Text: The new information to be integrated into the existing graph structure.
3. Use "USER_ID" as node for any self-references (e.g., "I," "me," "my," etc.) in user messages.

Guidelines:
1. Identification: Use the new information to evaluate existing relationships in the memory graph.
2. Deletion Criteria: Delete a relationship only if it meets at least one of these conditions:
   - Outdated or Inaccurate: The new information is more recent or accurate.
   - Contradictory: The new information conflicts with or negates the existing information.
3. DO NOT DELETE if their is a possibility of same type of relationship but different destination nodes.
4. Comprehensive Analysis:
   - Thoroughly examine each existing relationship against the new information and delete as necessary.
   - Multiple deletions may be required based on the new information.
5. Semantic Integrity:
   - Ensure that deletions maintain or improve the overall semantic structure of the graph.
   - Avoid deleting relationships that are NOT contradictory/outdated to the new information.
6. Temporal Awareness: Prioritize recency when timestamps are available.
7. Necessity Principle: Only DELETE relationships that must be deleted and are contradictory/outdated to the new information to maintain an accurate and coherent memory graph.

Note: DO NOT DELETE if their is a possibility of same type of relationship but different destination nodes. 

For example: 
Existing Memory: alice -- loves_to_eat -- pizza
New Information: Alice also loves to eat burger.

Do not delete in the above example because there is a possibility that Alice loves to eat both pizza and burger.

Memory Format:
source -- relationship -- destination

Provide a list of deletion instructions, each specifying the relationship to be deleted.
"""


def get_delete_messages(existing_memories_string, data, user_id):
    return DELETE_RELATIONS_SYSTEM_PROMPT.replace(
        "USER_ID", user_id
    ), f"Here are the existing memories: {existing_memories_string} \n\n New Information: {data}"
