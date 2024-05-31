import json
import os
from typing import Any, Callable, Dict, Optional, Type, Union

from langchain_core.tools import BaseTool
from pydantic import BaseModel
from zhipuai import ZhipuAI

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class ZhipuAILlm(BaseLlm):
    def __init__(
            self,
            config: Optional[BaseLlmConfig] = None,
            tools: Optional[Union[Dict[str, Any], Type[BaseModel], Callable[..., Any], BaseTool]] = None,
    ):
        self.tools = tools
        super().__init__(config=config)

    @staticmethod
    def cal_steam(data):
        for chunk in data:
            yield chunk.choices[0].delta.content

    def get_llm_model_answer(self, prompt) -> str:
        # print("prompt:", prompt)
        response = self._get_answer(prompt, self.config)
        return response

    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> str:
        messages = []
        if config.system_prompt:
            messages.append({"role": "system", "content": config.system_prompt})
        messages.append({"role": "user", "content": prompt})
        # kwargs 相关参数见：https://open.bigmodel.cn/dev/api#glm-4
        kwargs = {
            "model": config.model or "glm-4",
            "temperature": config.temperature,
            "top_p": config.top_p,
        }

        if config.max_tokens:
            # 限制最大tokens数量为8192
            kwargs["max_tokens"] = min(config.max_tokens, 8192)

        api_key = config.api_key or os.environ["ZHIPU_API_KEY"]
        client = ZhipuAI(api_key=api_key)

        if self.tools:
            return self._query_function_call(client, self.tools, messages, **kwargs)
        if config.stream:
            # callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
            response = client.chat.completions.create(
                stream=True, messages=messages, **kwargs,
            )
            return ZhipuAILlm.cal_steam(response)
        else:
            response = client.chat.completions.create(
                messages=messages, **kwargs,
            )
            return response.choices[0].message.content

    def _query_function_call(
            self,
            client: ZhipuAI,
            tools: Optional[Union[Dict[str, Any], Type[BaseModel], Callable[..., Any], BaseTool]],
            messages: list[Dict], **kwargs
    ) -> str:
        from langchain_core.utils.function_calling import convert_to_openai_tool
        openai_tools = [convert_to_openai_tool(tools)]
        response = client.chat.completions.create(
            messages=messages,
            tools=openai_tools,
            tool_choice="auto", **kwargs
        )
        try:
            """query: https://open.bigmodel.cn/dev/api#glm-4
              {'arguments': '{"date":"2024-01-01","departure":"北京南站","destination":"上海"}', 'name': 'query_train_info'}
            """
            return json.dumps(dict(response.choices[0].message.tool_calls[0].function))

        except IndexError:
            return "Input could not be mapped to the function!"
