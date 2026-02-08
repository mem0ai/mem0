from enum import Enum


class MemoryType(Enum):
    SEMANTIC = "semantic_memory"
    EPISODIC = "episodic_memory"
    PROCEDURAL = "procedural_memory"


class MemoryLayer(Enum):
    GENERAL = "general"
    AGENT = "agent"
    GLOBAL = "global"
    CHAT = "chat"
