from enum import Enum


# vector length created by embedding fn
class VectorDimensions(Enum):
    GPT4ALL = 384
    OPENAI = 1536
    VERTEX_AI = 768
    HUGGING_FACE = 384
    GOOGLE_AI = 768
    MISTRAL_AI = 1024
    NVIDIA_AI = 1024
    COHERE = 384
    OLLAMA = 384
