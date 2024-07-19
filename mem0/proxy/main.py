import httpx
from typing import Optional, List, Union

import litellm

from mem0 import Memory, MemoryClient
from mem0.configs.prompts import MEMORY_ANSWER_PROMPT

class Mem0:
    def __init__(
            self, 
            config: Optional[dict] = None,
            mem0_api_key: Optional[str] = None,
            host: Optional[str] = None
        ):
        
        if mem0_api_key:
            self.mem0_client = MemoryClient(mem0_api_key, host)
        else:
            self.mem0_client = Memory.from_config(config) if config else Memory()

        self.chat = Chat(self.mem0_client)


class Chat:
    def __init__(self, mem0_client):
        self.completions = Completions(mem0_client)


class Completions:
    def __init__(self, mem0_client):
        self.mem0_client = mem0_client
    
    def create(
        self,
        model: str,
        messages: List = [],
        # Mem0 arguments
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        filters: Optional[dict] = None,
        limit: Optional[int] = 10,
        # LLM arguments
        timeout: Optional[Union[float, str, httpx.Timeout]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        stream: Optional[bool] = None,
        stream_options: Optional[dict] = None,
        stop=None,
        max_tokens: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[dict] = None,
        user: Optional[str] = None,
        # openai v1.0+ new params
        response_format: Optional[dict] = None,
        seed: Optional[int] = None,
        tools: Optional[List] = None,
        tool_choice: Optional[Union[str, dict]] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        parallel_tool_calls: Optional[bool] = None,
        deployment_id=None,
        extra_headers: Optional[dict] = None,
        # soon to be deprecated params by OpenAI
        functions: Optional[List] = None,
        function_call: Optional[str] = None,
        # set api_base, api_version, api_key
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        api_key: Optional[str] = None,
        model_list: Optional[list] = None,  # pass in a list of api_base,keys, etc.
    ):
        
        if not litellm.supports_function_calling(model):
            raise ValueError(f"Model '{model}' does not support function calling. Please use a model that supports function calling.")
        
        if messages[0]["role"] == "system":
            messages[0]["content"] = MEMORY_ANSWER_PROMPT
        else:
            messages.insert(0, {"role": "system", "content": MEMORY_ANSWER_PROMPT})
        
        if messages[-1]["role"] == "user":
            query = messages[-1]["content"]
            self.mem0_client.add(
                data=query,
                user_id=user_id,
                agent_id=agent_id,
                run_id=run_id,
                metadata=metadata,
                filters=filters, 
            ) # add the messages to memory
        
            # fetch relevant memories
            relevant_memories = self.mem0_client.search(
                query=query,
                user_id=user_id,
                agent_id=agent_id,
                run_id=run_id,
                filters=filters,
                limit=limit,
            )

            relevant_memories = "\n".join([memory["text"] for memory in relevant_memories])
            messages[-1]["content"] = f"- Memories: {relevant_memories}\n\n- Question: {messages[-1]['content']}"

        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            n=n,
            timeout=timeout,
            stream=stream,
            stream_options=stream_options,
            stop=stop,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            logit_bias=logit_bias,
            user=user,
            response_format=response_format,
            seed=seed,
            tools=tools,
            tool_choice=tool_choice,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            parallel_tool_calls=parallel_tool_calls,
            deployment_id=deployment_id,
            extra_headers=extra_headers,
            functions=functions,
            function_call=function_call,
            base_url=base_url,
            api_version=api_version,
            api_key=api_key,
            model_list=model_list
        )

        return response