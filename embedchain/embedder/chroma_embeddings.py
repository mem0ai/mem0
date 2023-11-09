"""
Note that this file is copied from Chroma repository. We will remove this file once the fix in
ChromaDB's repository.
"""

from typing import Optional

from chromadb.api.types import Documents, Embeddings


class OpenAIEmbeddingFunction:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "text-embedding-ada-002",
        organization_id: Optional[str] = None,
        api_base: Optional[str] = None,
        api_type: Optional[str] = None,
        api_version: Optional[str] = None,
        deployment_id: Optional[str] = None,
    ):
        """
        Initialize the OpenAIEmbeddingFunction.
        Args:
            api_key (str, optional): Your API key for the OpenAI API. If not
                provided, it will raise an error to provide an OpenAI API key.
            organization_id(str, optional): The OpenAI organization ID if applicable
            model_name (str, optional): The name of the model to use for text
                embeddings. Defaults to "text-embedding-ada-002".
            api_base (str, optional): The base path for the API. If not provided,
                it will use the base path for the OpenAI API. This can be used to
                point to a different deployment, such as an Azure deployment.
            api_type (str, optional): The type of the API deployment. This can be
                used to specify a different deployment, such as 'azure'. If not
                provided, it will use the default OpenAI deployment.
            api_version (str, optional): The api version for the API. If not provided,
                it will use the api version for the OpenAI API. This can be used to
                point to a different deployment, such as an Azure deployment.
            deployment_id (str, optional): Deployment ID for Azure OpenAI.

        """
        try:
            import openai
        except ImportError:
            raise ValueError("The openai python package is not installed. Please install it with `pip install openai`")

        if api_key is not None:
            openai.api_key = api_key
        # If the api key is still not set, raise an error
        elif openai.api_key is None:
            raise ValueError(
                "Please provide an OpenAI API key. You can get one at https://platform.openai.com/account/api-keys"
            )

        if api_base is not None:
            openai.api_base = api_base

        if api_version is not None:
            openai.api_version = api_version

        self._api_type = api_type
        if api_type is not None:
            openai.api_type = api_type

        if organization_id is not None:
            openai.organization = organization_id

        self._v1 = openai.__version__.startswith("1.")
        if self._v1:
            if api_type == "azure":
                self._client = openai.AzureOpenAI(
                    api_key=api_key, api_version=api_version, azure_endpoint=api_base
                ).embeddings
            else:
                self._client = openai.OpenAI(api_key=api_key, base_url=api_base).embeddings
        else:
            self._client = openai.Embedding
        self._model_name = model_name
        self._deployment_id = deployment_id

    def __call__(self, input: Documents) -> Embeddings:
        # replace newlines, which can negatively affect performance.
        input = [t.replace("\n", " ") for t in input]

        # Call the OpenAI Embedding API
        if self._v1:
            embeddings = self._client.create(input=input, model=self._deployment_id or self._model_name).data

            # Sort resulting embeddings by index
            sorted_embeddings = sorted(embeddings, key=lambda e: e.index)  # type: ignore

            # Return just the embeddings
            return [result.embedding for result in sorted_embeddings]
        else:
            if self._api_type == "azure":
                embeddings = self._client.create(input=input, engine=self._deployment_id or self._model_name)["data"]
            else:
                embeddings = self._client.create(input=input, model=self._model_name)["data"]

            # Sort resulting embeddings by index
            sorted_embeddings = sorted(embeddings, key=lambda e: e["index"])  # type: ignore

            # Return just the embeddings
            return [result["embedding"] for result in sorted_embeddings]
