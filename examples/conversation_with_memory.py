"""
对话系统 + Mem0 记忆示例
功能：记录对话历史、引用历史内容、记住用户偏好

需要环境变量：
export OPENAI_API_KEY="your_openai_api_key"
export MEM0_API_KEY="your_mem0_api_key"
"""

import os
import requests
from openai import OpenAI

openai_api_key = os.getenv("OPENAI_API_KEY", "EMPTY")
openai_api_base = "http://192.168.1.14:8000/v1"
mem0_api_base = "http://192.168.1.14:8888"

# 初始化客户端
openai_client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

#model = "gpt-3.5-turbo"
model="Qwen/Qwen3-4B"

def chat(user_id: str, user_message: str) -> str:
    """带记忆的对话函数"""

    # 1. 搜索相关记忆
    search_resp = requests.post(
        f"{mem0_api_base}/search",
        json={"query": user_message, "user_id": user_id}
    )
    memories = search_resp.json().get("results", [])
    memory_context = "\n".join(f"- {m.get('memory', m)}" for m in memories) if memories else "无历史记忆"

    # 2. 构建提示词
    prompt = f"""你是一个智能助手，能记住用户的对话历史和偏好。

相关记忆：
{memory_context}

用户消息：{user_message}

请基于记忆提供个性化回答。如果用户提到新的偏好或重要信息，自然地确认。"""

    # 3. 调用 LLM
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    assistant_reply = response.choices[0].message.content

    # 4. 存储对话到记忆
    requests.post(
        f"{mem0_api_base}/memories",
        json={
            "messages": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_reply}
            ],
            "user_id": user_id
        }
    )

    return assistant_reply

# 示例使用
if __name__ == "__main__":
    user_id = "user_001"

    # 第一轮对话 - 建立偏好
    print("用户：我喜欢喝咖啡，不喜欢茶")
    reply = chat(user_id, "我喜欢喝咖啡，不喜欢茶")
    print(f"助手：{reply}\n")

    # 第二轮对话 - 记录信息
    print("用户：我每天早上7点起床")
    reply = chat(user_id, "我每天早上7点起床")
    print(f"助手：{reply}\n")

    # 第三轮对话 - 引用历史
    print("用户：推荐一个早餐饮品")
    reply = chat(user_id, "推荐一个早餐饮品")
    print(f"助手：{reply}\n")

    # 第四轮对话 - 测试记忆
    print("用户：我的作息时间是什么？")
    reply = chat(user_id, "我的作息时间是什么？")
    print(f"助手：{reply}")
