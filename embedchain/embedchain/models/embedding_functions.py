from enum import Enum


class EmbeddingFunctions(Enum):
    OPENAI = "OPENAI"
    HUGGING_FACE = "HUGGING_FACE"
    VERTEX_AI = "VERTEX_AI"
    AWS_BEDROCK = "AWS_BEDROCK"
    GPT4ALL = "GPT4ALL"
    OLLAMA = "OLLAMA"
