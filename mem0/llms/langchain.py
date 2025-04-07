from typing import Dict, List, Optional
import enum

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase

# Default import for langchain_community
try:
    from langchain_community import chat_models
except ImportError:
    raise ImportError("langchain_community not found. Please install it with `pip install langchain-community`")

# Provider-specific package mapping
PROVIDER_PACKAGES = {
    "Anthropic": "langchain_anthropic",
    "MistralAI": "langchain_mistralai",
    "Fireworks": "langchain_fireworks",
    "AzureOpenAI": "langchain_openai",
    "OpenAI": "langchain_openai",
    "Together": "langchain_together",
    "VertexAI": "langchain_google_vertexai",
    "GoogleAI": "langchain_google_genai",
    "Groq": "langchain_groq",
    "Cohere": "langchain_cohere",
    "Bedrock": "langchain_aws",
    "HuggingFace": "langchain_huggingface",
    "NVIDIA": "langchain_nvidia_ai_endpoints",
    "Ollama": "langchain_ollama",
    "AI21": "langchain_ai21",
    "Upstage": "langchain_upstage",
    "Databricks": "databricks_langchain",
    "Watsonx": "langchain_ibm",
    "xAI": "langchain_xai",
    "Perplexity": "langchain_perplexity",
}


class LangchainProvider(enum.Enum):
    Abso = "ChatAbso"
    AI21 = "ChatAI21"
    Alibaba = "ChatAlibabaCloud"
    Anthropic = "ChatAnthropic"
    Anyscale = "ChatAnyscale"
    AzureAIChatCompletionsModel = "AzureAIChatCompletionsModel"
    AzureOpenAI = "AzureChatOpenAI"
    AzureMLEndpoint = "ChatAzureMLEndpoint"
    Baichuan = "ChatBaichuan"
    Qianfan = "ChatQianfan"
    Bedrock = "ChatBedrock"
    Cerebras = "ChatCerebras"
    CloudflareWorkersAI = "ChatCloudflareWorkersAI"
    Cohere = "ChatCohere"
    ContextualAI = "ChatContextualAI"
    Coze = "ChatCoze"
    Dappier = "ChatDappier"
    Databricks = "ChatDatabricks"
    DeepInfra = "ChatDeepInfra"
    DeepSeek = "ChatDeepSeek"
    EdenAI = "ChatEdenAI"
    EverlyAI = "ChatEverlyAI"
    Fireworks = "ChatFireworks"
    Friendli = "ChatFriendli"
    GigaChat = "ChatGigaChat"
    Goodfire = "ChatGoodfire"
    GoogleAI = "ChatGoogleAI"
    VertexAI = "VertexAI"
    GPTRouter = "ChatGPTRouter"
    Groq = "ChatGroq"
    HuggingFace = "ChatHuggingFace"
    Watsonx = "ChatWatsonx"
    Jina = "ChatJina"
    Kinetica = "ChatKinetica"
    Konko = "ChatKonko"
    LiteLLM = "ChatLiteLLM"
    LiteLLMRouter = "ChatLiteLLMRouter"
    Llama2Chat = "Llama2Chat"
    LlamaAPI = "ChatLlamaAPI"
    LlamaEdge = "ChatLlamaEdge"
    LlamaCpp = "ChatLlamaCpp"
    Maritalk = "ChatMaritalk"
    MiniMax = "ChatMiniMax"
    MistralAI = "ChatMistralAI"
    MLX = "ChatMLX"
    ModelScope = "ChatModelScope"
    Moonshot = "ChatMoonshot"
    Naver = "ChatNaver"
    Netmind = "ChatNetmind"
    NVIDIA = "ChatNVIDIA"
    OCIModelDeployment = "ChatOCIModelDeployment"
    OCIGenAI = "ChatOCIGenAI"
    OctoAI = "ChatOctoAI"
    Ollama = "ChatOllama"
    OpenAI = "ChatOpenAI"
    Outlines = "ChatOutlines"
    Perplexity = "ChatPerplexity"
    Pipeshift = "ChatPipeshift"
    PredictionGuard = "ChatPredictionGuard"
    PremAI = "ChatPremAI"
    PromptLayerOpenAI = "PromptLayerChatOpenAI"
    QwQ = "ChatQwQ"
    Reka = "ChatReka"
    RunPod = "ChatRunPod"
    SambaNovaCloud = "ChatSambaNovaCloud"
    SambaStudio = "ChatSambaStudio"
    SeekrFlow = "ChatSeekrFlow"
    SnowflakeCortex = "ChatSnowflakeCortex"
    Solar = "ChatSolar"
    SparkLLM = "ChatSparkLLM"
    Nebula = "ChatNebula"
    Hunyuan = "ChatHunyuan"
    Together = "ChatTogether"
    TongyiQwen = "ChatTongyiQwen"
    Upstage = "ChatUpstage"
    Vectara = "ChatVectara"
    VLLM = "ChatVLLM"
    VolcEngine = "ChatVolcEngine"
    Writer = "ChatWriter"
    xAI = "ChatXAI"
    Xinference = "ChatXinference"
    Yandex = "ChatYandex"
    Yi = "ChatYi"
    Yuan2 = "ChatYuan2"
    ZhipuAI = "ChatZhipuAI"


class LangchainLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        provider = self.config.langchain_provider
        if provider not in LangchainProvider.__members__:
            raise ValueError(f"Invalid provider: {provider}")
        model_name = LangchainProvider[provider].value

        try:
            # Check if this provider needs a specialized package
            if provider in PROVIDER_PACKAGES:
                if provider == "Anthropic": # Special handling for Anthropic with Pydantic v2
                    try:
                        from langchain_anthropic import ChatAnthropic
                        model_class = ChatAnthropic
                    except ImportError:
                        raise ImportError("langchain_anthropic not found. Please install it with `pip install langchain-anthropic`")
                else:
                    package_name = PROVIDER_PACKAGES[provider]
                    try:
                            # Import the model class directly from the package
                        module_path = f"{package_name}"
                        model_class = __import__(module_path, fromlist=[model_name])
                        model_class = getattr(model_class, model_name)
                    except ImportError:
                        raise ImportError(
                            f"Package {package_name} not found. " f"Please install it with `pip install {package_name}`"
                        )
                    except AttributeError:
                        raise ImportError(f"Model {model_name} not found in {package_name}")
            else:
                # Use the default langchain_community module
                if not hasattr(chat_models, model_name):
                    raise ImportError(f"Provider {provider} not found in langchain_community.chat_models")

                model_class = getattr(chat_models, model_name)

            # Initialize the model with relevant config parameters
            self.langchain_model = model_class(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        except (ImportError, AttributeError, ValueError) as e:
            raise ImportError(f"Error setting up langchain model for provider {provider}: {str(e)}")

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using langchain_community.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Not used in Langchain.
            tools (list, optional): List of tools that the model can call. Not used in Langchain.
            tool_choice (str, optional): Tool choice method. Not used in Langchain.

        Returns:
            str: The generated response.
        """
        try:
            # Convert the messages to LangChain's tuple format
            langchain_messages = []
            for message in messages:
                role = message["role"]
                content = message["content"]

                if role == "system":
                    langchain_messages.append(("system", content))
                elif role == "user":
                    langchain_messages.append(("human", content))
                elif role == "assistant":
                    langchain_messages.append(("ai", content))

            if not langchain_messages:
                raise ValueError("No valid messages found in the messages list")

            ai_message = self.langchain_model.invoke(langchain_messages)

            return ai_message.content

        except Exception as e:
            raise Exception(f"Error generating response using langchain model: {str(e)}")
