"""
GeoMind Core - 多模型统一调用层
使用 openai 库（替代 httpx，更稳定）
"""

import os
from typing import List, Dict, AsyncIterator, Optional
from openai import AsyncOpenAI

# ============================================================
# 模型提供商配置
# ============================================================

MODEL_PROVIDERS = {
    "Claude (Zeabur)": {
        "env_key": "CLAUDE_ZEABUR_API_KEY",
        "base_url": "https://hnd1.aihub.zeabur.ai/v1",
        "models": ["claude-sonnet-4-5"],
        "default_model": "claude-sonnet-4-5",
        "description": "Claude via Zeabur AI Hub",
        "icon": "🔵",
    },
    "Kimi (Zeabur)": {
        "env_key": "KIMI_ZEABUR_API_KEY",
        "base_url": "https://hnd1.aihub.zeabur.ai/v1",
        "models": ["kimi-k2.5"],
        "default_model": "kimi-k2.5",
        "description": "Kimi via Zeabur AI Hub",
        "icon": "🟣",
    },
}

# 客户端缓存
_clients: Dict[str, AsyncOpenAI] = {}


def _get_client(provider: str) -> Optional[AsyncOpenAI]:
    """获取/复用 OpenAI 客户端"""
    if provider in _clients:
        return _clients[provider]

    config = MODEL_PROVIDERS.get(provider)
    if not config:
        return None

    api_key = os.getenv(config["env_key"], "")
    if not api_key:
        return None

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=config["base_url"],
        timeout=120.0,
    )
    _clients[provider] = client
    return client


def get_available_providers() -> List[str]:
    """获取已配置 API Key 的可用提供商"""
    available = []
    for name, config in MODEL_PROVIDERS.items():
        key = os.getenv(config["env_key"], "")
        if key:
            available.append(name)
    return available


def get_provider_config(provider_name: str) -> Optional[Dict]:
    """获取提供商配置"""
    return MODEL_PROVIDERS.get(provider_name)


# ============================================================
# 统一调用接口
# ============================================================

async def call_llm(
    messages: List[Dict],
    system_prompt: str,
    provider: str,
    api_key: str = None,
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """
    统一 LLM 调用（非流式）
    """
    config = MODEL_PROVIDERS.get(provider)
    if not config:
        return f"❌ 未知的模型提供商: {provider}"

    client = _get_client(provider)
    if not client:
        return f"⚠️ 请设置 {provider} 的 API Key（环境变量: {config['env_key']}）"

    model = model or config["default_model"]
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"❌ 请求失败: {str(e)}"


async def stream_llm(
    messages: List[Dict],
    system_prompt: str,
    provider: str,
    api_key: str = None,
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    """
    统一 LLM 流式调用

    Yields: 文本 token 片段
    """
    config = MODEL_PROVIDERS.get(provider)
    if not config:
        yield f"❌ 未知的模型提供商: {provider}"
        return

    client = _get_client(provider)
    if not client:
        yield f"⚠️ 请设置 {provider} 的 API Key"
        return

    model = model or config["default_model"]
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        yield f"\n\n❌ 流式请求失败: {type(e).__name__}: {str(e)}"
