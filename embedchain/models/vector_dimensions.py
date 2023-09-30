from enum import Enum


# vector length created by embedding fn
class VectorDimensions(Enum):
    GPT4ALL = 384
    OPENAI = 1536
    VERTEX_AI = 768
    HUGGING_FACE = 384
