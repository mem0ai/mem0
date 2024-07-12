from enum import Enum


class Providers(Enum):
    OPENAI = "OPENAI"
    ANTHROPHIC = "ANTHPROPIC"
    VERTEX_AI = "VERTEX_AI"
    AWS_BEDROCK = "AWS_BEDROCK"
    GPT4ALL = "GPT4ALL"
    OLLAMA = "OLLAMA"
    AZURE_OPENAI = "AZURE_OPENAI"
