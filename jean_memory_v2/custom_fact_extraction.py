"""
Jean Memory V2 - Custom Fact Extraction Prompt
==============================================

Custom fact extraction prompt for Mem0 that works with the Jean Memory V2 ontology.
This prompt extracts structured facts about entities and relationships from user input.
"""

# =============================================================================
# CUSTOM FACT EXTRACTION PROMPT
# =============================================================================

CUSTOM_FACT_EXTRACTION_PROMPT = """
Please extract structured facts about entities and their relationships from the provided text.
Focus on extracting entities of types: Person, Place, Event, Topic, Object, Emotion.

Important guidelines:
- Only extract facts that are explicitly mentioned or clearly implied in the text
- Ignore generic or common knowledge
- Focus on personally relevant information
- Extract relationships between entities
- Include emotional context when present
- Preserve temporal information (dates, times, durations)

Entity types to extract:
1. Person: Names, ages, occupations, locations, relationships
2. Place: Locations, addresses, place types, descriptions
3. Event: Activities, meetings, experiences, occurrences
4. Topic: Subjects, interests, categories, themes
5. Object: Items, products, belongings, purchases
6. Emotion: Feelings, moods, emotional states, reactions

Few-shot examples:

Input: "Hi there!"
Output: {"facts": []}

Input: "The weather is nice today."
Output: {"facts": []}

Input: "I had coffee with Sarah at Blue Bottle yesterday. She's a software engineer at Google."
Output: {"facts": [
    "Person: Sarah",
    "Person: Sarah - occupation: software engineer",
    "Person: Sarah - employer: Google",
    "Place: Blue Bottle",
    "Event: coffee meeting",
    "Event: coffee meeting - participants: user, Sarah",
    "Event: coffee meeting - location: Blue Bottle",
    "Event: coffee meeting - date: yesterday"
]}

Input: "My MacBook Pro broke down last week. I need to get it repaired. Feeling frustrated about it."
Output: {"facts": [
    "Object: MacBook Pro",
    "Object: MacBook Pro - condition: broken",
    "Event: MacBook breakdown",
    "Event: MacBook breakdown - date: last week",
    "Topic: device repair",
    "Emotion: frustrated",
    "Emotion: frustrated - trigger: MacBook breakdown"
]}

Input: "I'm planning to visit Tokyo next month for a conference. Really excited about trying authentic sushi."
Output: {"facts": [
    "Place: Tokyo",
    "Event: Tokyo trip",
    "Event: Tokyo trip - date: next month",
    "Event: conference",
    "Event: conference - location: Tokyo",
    "Topic: travel",
    "Topic: sushi",
    "Object: authentic sushi",
    "Emotion: excited",
    "Emotion: excited - trigger: Tokyo trip planning"
]}

Input: "My mom called me today. She's feeling lonely since dad passed away two years ago."
Output: {"facts": [
    "Person: mom",
    "Person: dad",
    "Event: phone call",
    "Event: phone call - participants: user, mom",
    "Event: phone call - date: today",
    "Event: dad's death",
    "Event: dad's death - date: two years ago",
    "Emotion: lonely",
    "Emotion: lonely - person: mom",
    "Emotion: lonely - trigger: dad's death"
]}

Input: "Bought a new guitar at Guitar Center for $800. It's a Fender Stratocaster in blue."
Output: {"facts": [
    "Object: guitar",
    "Object: guitar - brand: Fender",
    "Object: guitar - model: Stratocaster",
    "Object: guitar - color: blue",
    "Object: guitar - price: $800",
    "Place: Guitar Center",
    "Event: guitar purchase",
    "Event: guitar purchase - location: Guitar Center",
    "Topic: music"
]}

Input: "Working from home today. Having a team meeting at 2 PM about the new project launch."
Output: {"facts": [
    "Event: working from home",
    "Event: working from home - date: today",
    "Event: team meeting",
    "Event: team meeting - time: 2 PM",
    "Event: team meeting - date: today",
    "Topic: new project launch",
    "Topic: remote work"
]}

Return the extracted facts in JSON format as shown above. Each fact should be a clear, atomic statement.
"""

# =============================================================================
# ENHANCED FACT EXTRACTION PROMPT (Alternative version)
# =============================================================================

ENHANCED_FACT_EXTRACTION_PROMPT = """
Extract structured facts from the input text, focusing on entities and their relationships.
Prioritize personal, specific, and actionable information over generic statements.

Entity Categories:
- Person: Names, roles, attributes, relationships
- Place: Locations, venues, addresses, geographical entities
- Event: Activities, meetings, experiences, occurrences
- Topic: Subjects, interests, skills, domains
- Object: Items, products, tools, possessions
- Emotion: Feelings, moods, reactions, emotional states

Relationship Types:
- ParticipatedIn: Person participated in Event
- LocatedAt: Entity located at Place
- RelatedTo: General relationships between entities
- Expressed: Person expressed Emotion

Guidelines:
1. Extract only explicitly mentioned or clearly implied facts
2. Preserve temporal information (dates, times, sequences)
3. Include emotional context and reactions
4. Capture relationships between entities
5. Ignore generic knowledge or common facts
6. Focus on personally relevant information

Examples:

Input: "Hello"
Output: {"facts": []}

Input: "It's raining outside"
Output: {"facts": []}

Input: "Met John at Starbucks this morning. He showed me his new iPhone 15. He seemed really proud of it."
Output: {"facts": [
    "Person: John",
    "Place: Starbucks",
    "Object: iPhone 15",
    "Object: iPhone 15 - owner: John",
    "Event: meeting",
    "Event: meeting - participants: user, John",
    "Event: meeting - location: Starbucks",
    "Event: meeting - time: this morning",
    "Emotion: proud",
    "Emotion: proud - person: John",
    "Emotion: proud - trigger: new iPhone 15"
]}

Input: "Started learning Spanish last week using Duolingo. Finding it challenging but rewarding."
Output: {"facts": [
    "Topic: Spanish language",
    "Topic: language learning",
    "Object: Duolingo",
    "Event: started learning Spanish",
    "Event: started learning Spanish - date: last week",
    "Event: started learning Spanish - method: Duolingo",
    "Emotion: challenged",
    "Emotion: challenged - trigger: learning Spanish",
    "Emotion: rewarded",
    "Emotion: rewarded - trigger: learning Spanish"
]}

Return facts in JSON format with clear, atomic statements.
"""

# =============================================================================
# CONFIGURATION
# =============================================================================

# Default prompt to use
DEFAULT_PROMPT = CUSTOM_FACT_EXTRACTION_PROMPT

# Alternative prompts for different use cases
PROMPTS = {
    "default": CUSTOM_FACT_EXTRACTION_PROMPT,
    "enhanced": ENHANCED_FACT_EXTRACTION_PROMPT
}

def get_custom_fact_extraction_prompt(prompt_type: str = "default") -> str:
    """
    Get a custom fact extraction prompt by type.
    
    Args:
        prompt_type (str): Type of prompt to retrieve ("default" or "enhanced")
        
    Returns:
        str: The custom fact extraction prompt
    """
    return PROMPTS.get(prompt_type, DEFAULT_PROMPT)

# =============================================================================
# VALIDATION
# =============================================================================

def validate_prompt_format(prompt: str) -> bool:
    """
    Validate that the prompt follows the expected format.
    
    Args:
        prompt (str): The prompt to validate
        
    Returns:
        bool: True if prompt format is valid, False otherwise
    """
    try:
        # Check if prompt contains required elements
        required_elements = [
            "extract",
            "facts",
            "JSON",
            "Input:",
            "Output:",
            "Person",
            "Place",
            "Event"
        ]
        
        for element in required_elements:
            if element not in prompt:
                print(f"Missing required element: {element}")
                return False
        
        return True
        
    except Exception as e:
        print(f"Prompt validation failed: {e}")
        return False

# Validate prompts on import
if __name__ == "__main__":
    print("Validating custom fact extraction prompts...")
    
    for prompt_name, prompt in PROMPTS.items():
        if validate_prompt_format(prompt):
            print(f"✅ {prompt_name} prompt validation passed")
        else:
            print(f"❌ {prompt_name} prompt validation failed")
    
    print("Custom fact extraction prompts ready!") 