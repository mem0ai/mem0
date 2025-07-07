"""
Jean Memory V2 - Initial Core Ontology
=====================================

Defines custom entity types and edge types for Graphiti knowledge graph.
These types enable structured data extraction and richer semantic relationships.
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Union


# =============================================================================
# CUSTOM ENTITY TYPES
# =============================================================================

class Person(BaseModel):
    """A person entity with biographical and contextual information."""
    age: Optional[int] = Field(None, description="Age of the person in years")
    occupation: Optional[str] = Field(None, description="Current occupation or job title")
    location: Optional[str] = Field(None, description="Current location or residence")
    birth_date: Optional[datetime] = Field(None, description="Date of birth")
    interests: Optional[List[str]] = Field(None, description="List of interests or hobbies")
    relationship_status: Optional[str] = Field(None, description="Relationship status")
    
    @validator('age')
    def validate_age(cls, v):
        if v is not None and (v < 0 or v > 150):
            raise ValueError('Age must be between 0 and 150')
        return v


class Place(BaseModel):
    """A location, venue, or geographical entity."""
    place_type: Optional[str] = Field(None, description="Type of place (city, restaurant, park, etc.)")
    address: Optional[str] = Field(None, description="Physical address")
    country: Optional[str] = Field(None, description="Country name")
    region: Optional[str] = Field(None, description="State, province, or region")
    city: Optional[str] = Field(None, description="City name")
    coordinates: Optional[str] = Field(None, description="GPS coordinates (lat, lng)")
    description: Optional[str] = Field(None, description="Additional description of the place")


class Event(BaseModel):
    """An event, activity, or occurrence."""
    event_type: Optional[str] = Field(None, description="Type of event (meeting, party, conference, etc.)")
    start_date: Optional[datetime] = Field(None, description="Event start date and time")
    end_date: Optional[datetime] = Field(None, description="Event end date and time")
    duration: Optional[str] = Field(None, description="Duration of the event")
    participants: Optional[List[str]] = Field(None, description="List of participants or attendees")
    location: Optional[str] = Field(None, description="Event location")
    outcome: Optional[str] = Field(None, description="Result or outcome of the event")
    importance: Optional[str] = Field(None, description="Importance level (low, medium, high)")


class Topic(BaseModel):
    """A subject, theme, or area of interest."""
    category: Optional[str] = Field(None, description="Category or domain (technology, sports, etc.)")
    subcategory: Optional[str] = Field(None, description="More specific subcategory")
    keywords: Optional[List[str]] = Field(None, description="Related keywords or terms")
    description: Optional[str] = Field(None, description="Description of the topic")
    relevance: Optional[str] = Field(None, description="Relevance to the user (high, medium, low)")


class Object(BaseModel):
    """A physical or digital object, product, or item."""
    object_type: Optional[str] = Field(None, description="Type of object (book, device, clothing, etc.)")
    brand: Optional[str] = Field(None, description="Brand or manufacturer")
    model: Optional[str] = Field(None, description="Model or version")
    color: Optional[str] = Field(None, description="Color of the object")
    size: Optional[str] = Field(None, description="Size or dimensions")
    price: Optional[float] = Field(None, description="Price or cost")
    condition: Optional[str] = Field(None, description="Condition (new, used, broken, etc.)")
    purchase_date: Optional[datetime] = Field(None, description="Date of purchase")
    
    @validator('price')
    def validate_price(cls, v):
        if v is not None and v < 0:
            raise ValueError('Price must be non-negative')
        return v


class Emotion(BaseModel):
    """An emotional state or feeling."""
    emotion_type: Optional[str] = Field(None, description="Type of emotion (happy, sad, excited, etc.)")
    intensity: Optional[str] = Field(None, description="Intensity level (low, medium, high)")
    trigger: Optional[str] = Field(None, description="What triggered this emotion")
    context: Optional[str] = Field(None, description="Context or situation")
    duration: Optional[str] = Field(None, description="How long the emotion lasted")
    associated_memory: Optional[str] = Field(None, description="Memory associated with this emotion")


# =============================================================================
# CUSTOM EDGE TYPES
# =============================================================================

class ParticipatedIn(BaseModel):
    """Participation relationship between a person and an event."""
    role: Optional[str] = Field(None, description="Role of participation (organizer, attendee, speaker, etc.)")
    start_date: Optional[datetime] = Field(None, description="When participation started")
    end_date: Optional[datetime] = Field(None, description="When participation ended")
    contribution: Optional[str] = Field(None, description="What they contributed to the event")
    experience: Optional[str] = Field(None, description="How they experienced the event")
    is_organizer: Optional[bool] = Field(None, description="Whether they organized the event")


class LocatedAt(BaseModel):
    """Location relationship between entities and places."""
    location_type: Optional[str] = Field(None, description="Type of location relationship (lives_at, works_at, visited, etc.)")
    start_date: Optional[datetime] = Field(None, description="When the location relationship started")
    end_date: Optional[datetime] = Field(None, description="When the location relationship ended")
    frequency: Optional[str] = Field(None, description="How often they are at this location")
    purpose: Optional[str] = Field(None, description="Purpose for being at this location")
    is_current: Optional[bool] = Field(None, description="Whether this is a current location")


class RelatedTo(BaseModel):
    """General relationship between any two entities."""
    relationship_type: Optional[str] = Field(None, description="Type of relationship (friend, colleague, similar, etc.)")
    strength: Optional[str] = Field(None, description="Strength of relationship (weak, medium, strong)")
    context: Optional[str] = Field(None, description="Context in which they are related")
    start_date: Optional[datetime] = Field(None, description="When the relationship started")
    end_date: Optional[datetime] = Field(None, description="When the relationship ended")
    description: Optional[str] = Field(None, description="Additional description of the relationship")
    is_bidirectional: Optional[bool] = Field(None, description="Whether the relationship goes both ways")


class Expressed(BaseModel):
    """Emotional expression relationship between a person and an emotion."""
    expression_type: Optional[str] = Field(None, description="How the emotion was expressed (verbal, physical, etc.)")
    intensity: Optional[str] = Field(None, description="Intensity of expression (subtle, moderate, strong)")
    context: Optional[str] = Field(None, description="Context in which emotion was expressed")
    timestamp: Optional[datetime] = Field(None, description="When the emotion was expressed")
    trigger: Optional[str] = Field(None, description="What triggered the emotional expression")
    observer: Optional[str] = Field(None, description="Who observed the emotional expression")


# =============================================================================
# ONTOLOGY CONFIGURATION
# =============================================================================

# Entity Types Dictionary
ENTITY_TYPES = {
    "Person": Person,
    "Place": Place,
    "Event": Event,
    "Topic": Topic,
    "Object": Object,
    "Emotion": Emotion
}

# Edge Types Dictionary
EDGE_TYPES = {
    "ParticipatedIn": ParticipatedIn,
    "LocatedAt": LocatedAt,
    "RelatedTo": RelatedTo,
    "Expressed": Expressed
}

# Edge Type Mapping - Defines which edge types can exist between specific entity pairs
EDGE_TYPE_MAP = {
    # Person relationships
    ("Person", "Event"): ["ParticipatedIn", "RelatedTo"],
    ("Person", "Place"): ["LocatedAt", "RelatedTo"],
    ("Person", "Topic"): ["RelatedTo"],
    ("Person", "Object"): ["RelatedTo"],
    ("Person", "Emotion"): ["Expressed"],
    ("Person", "Person"): ["RelatedTo"],
    
    # Event relationships
    ("Event", "Place"): ["LocatedAt"],
    ("Event", "Topic"): ["RelatedTo"],
    ("Event", "Object"): ["RelatedTo"],
    ("Event", "Emotion"): ["RelatedTo"],
    ("Event", "Event"): ["RelatedTo"],
    
    # Place relationships
    ("Place", "Topic"): ["RelatedTo"],
    ("Place", "Object"): ["RelatedTo"],
    ("Place", "Emotion"): ["RelatedTo"],
    ("Place", "Place"): ["RelatedTo"],
    
    # Topic relationships
    ("Topic", "Object"): ["RelatedTo"],
    ("Topic", "Emotion"): ["RelatedTo"],
    ("Topic", "Topic"): ["RelatedTo"],
    
    # Object relationships
    ("Object", "Emotion"): ["RelatedTo"],
    ("Object", "Object"): ["RelatedTo"],
    
    # Emotion relationships
    ("Emotion", "Emotion"): ["RelatedTo"],
    
    # Generic fallback for any entity type
    ("Entity", "Entity"): ["RelatedTo"]
}

# Excluded Entity Types (can be used to exclude certain types from extraction)
EXCLUDED_ENTITY_TYPES = []


def get_ontology_config():
    """
    Get the complete ontology configuration for Graphiti.
    
    Returns:
        dict: Complete ontology configuration with entity types, edge types, and mappings
    """
    return {
        "entity_types": ENTITY_TYPES,
        "edge_types": EDGE_TYPES,
        "edge_type_map": EDGE_TYPE_MAP,
        "excluded_entity_types": EXCLUDED_ENTITY_TYPES
    }


def validate_ontology():
    """
    Validate the ontology configuration.
    
    Returns:
        bool: True if ontology is valid, False otherwise
    """
    try:
        # Validate entity types
        for name, entity_type in ENTITY_TYPES.items():
            if not issubclass(entity_type, BaseModel):
                raise ValueError(f"Entity type {name} must be a Pydantic BaseModel")
        
        # Validate edge types
        for name, edge_type in EDGE_TYPES.items():
            if not issubclass(edge_type, BaseModel):
                raise ValueError(f"Edge type {name} must be a Pydantic BaseModel")
        
        # Validate edge type mappings
        for (source, target), edge_types in EDGE_TYPE_MAP.items():
            for edge_type in edge_types:
                if edge_type not in EDGE_TYPES and edge_type != "RelatedTo":
                    raise ValueError(f"Edge type {edge_type} in mapping not found in EDGE_TYPES")
        
        return True
        
    except Exception as e:
        print(f"Ontology validation failed: {e}")
        return False


# Validate ontology on import
if __name__ == "__main__":
    if validate_ontology():
        print("✅ Ontology validation passed")
    else:
        print("❌ Ontology validation failed") 