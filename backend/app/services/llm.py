import os

import requests


class LLMError(Exception):
    pass


def call_llm(prompt: str) -> str:
    """
    调用大模型生成回答。

    当前写成 OpenAI-compatible 风格：
    只要你的模型服务支持 /v1/chat/completions 这种接口，就可以使用。
    """

    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not api_key or not api_base or not model:
        raise LLMError(
            "LLM_API_KEY, LLM_API_BASE, and LLM_MODEL must be configured"
        )

    url = f"{api_base.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是一名严谨的知识库问答助手。你必须基于用户提供的知识库资料回答问题，不要编造。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise LLMError(f"LLM request failed: {error}") from error

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LLMError(f"Unexpected LLM response format: {data}") from error