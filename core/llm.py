"""
GeoMind Core - 多模型统一调用层
支持 Claude / Kimi via Zeabur AI Hub
"""

import httpx
import json
import os
from typing import List, Dict, AsyncIterator, Optional

# ============================================================
# 模型提供商配置
# ============================================================

MODEL_PROVIDERS = {
    "Claude (Zeabur)": {
        "env_key": "CLAUDE_ZEABUR_API_KEY",
        "base_url": "https://hnd1.aihub.zeabur.ai/v1",
        "models": ["claude-sonnet-4-5"],
        "default_model": "claude-sonnet-4-5",
        "format": "openai",
        "description": "Claude via Zeabur AI Hub",
        "icon": "🔵",
    },
    "Kimi (Zeabur)": {
        "env_key": "KIMI_ZEABUR_API_KEY",
        "base_url": "https://hnd1.aihub.zeabur.ai/v1",
        "models": ["kimi-k2.5"],
        "default_model": "kimi-k2.5",
        "format": "openai",
        "description": "Kimi via Zeabur AI Hub",
        "icon": "🟣",
    },
}


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
    
    Args:
        messages: [{"role": "user", "content": "..."}]
        system_prompt: 系统提示词
        provider: 提供商名称 (Claude / Kimi / DeepSeek)
        api_key: API Key（可选，默认从环境变量读取）
        model: 模型名（可选，默认使用提供商默认模型）
        temperature: 温度
        max_tokens: 最大 token 数
    """
    config = MODEL_PROVIDERS.get(provider)
    if not config:
        return f"❌ 未知的模型提供商: {provider}"
    
    api_key = api_key or os.getenv(config["env_key"], "")
    if not api_key:
        return f"⚠️ 请设置 {provider} 的 API Key（环境变量: {config['env_key']}）"
    
    model = model or config["default_model"]
    base_url = config["base_url"]
    
    if config["format"] == "anthropic":
        return await _call_anthropic(base_url, api_key, model, messages, system_prompt, temperature, max_tokens)
    else:
        return await _call_openai_compatible(base_url, api_key, model, messages, system_prompt, temperature, max_tokens)


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
    
    api_key = api_key or os.getenv(config["env_key"], "")
    if not api_key:
        yield f"⚠️ 请设置 {provider} 的 API Key"
        return
    
    model = model or config["default_model"]
    base_url = config["base_url"]
    
    if config["format"] == "anthropic":
        async for token in _stream_anthropic(base_url, api_key, model, messages, system_prompt, temperature, max_tokens):
            yield token
    else:
        async for token in _stream_openai_compatible(base_url, api_key, model, messages, system_prompt, temperature, max_tokens):
            yield token


# ============================================================
# Anthropic 原生格式
# ============================================================

async def _call_anthropic(base_url, api_key, model, messages, system_prompt, temperature, max_tokens) -> str:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": messages,
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{base_url}/v1/messages", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
            return f"❌ Anthropic API 错误 ({resp.status_code}): {resp.text[:300]}"
    except Exception as e:
        return f"❌ 请求失败: {str(e)}"


async def _stream_anthropic(base_url, api_key, model, messages, system_prompt, temperature, max_tokens) -> AsyncIterator[str]:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": messages,
        "stream": True,
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{base_url}/v1/messages", headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    yield f"❌ Anthropic API 错误 ({resp.status_code}): {error_body.decode()[:300]}"
                    return
                
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"\n\n❌ 流式请求失败: {str(e)}"


# ============================================================
# OpenAI 兼容格式 (Kimi / DeepSeek / Zeabur)
# ============================================================

async def _call_openai_compatible(base_url, api_key, model, messages, system_prompt, temperature, max_tokens) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": full_messages,
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            return f"❌ API 错误 ({resp.status_code}): {resp.text[:300]}"
    except Exception as e:
        return f"❌ 请求失败: {str(e)}"


async def _stream_openai_compatible(base_url, api_key, model, messages, system_prompt, temperature, max_tokens) -> AsyncIterator[str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": full_messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{base_url}/chat/completions", headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    error_text = error_body.decode()
                    yield f"❌ API 错误 ({resp.status_code})\n\n**请求模型**: `{model}`\n**错误详情**: {error_text[:500]}"
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            yield text
                    except json.JSONDecodeError:
                        continue
    except httpx.ConnectError as e:
        yield f"❌ 连接失败: 无法连接到 {base_url}\n\n错误: {str(e)}"
    except httpx.TimeoutException:
        yield f"❌ 请求超时: {base_url} 响应时间过长"
    except Exception as e:
        yield f"❌ 流式请求失败\n\n**请求模型**: `{model}`\n**错误类型**: {type(e).__name__}\n**错误信息**: {str(e)}"
