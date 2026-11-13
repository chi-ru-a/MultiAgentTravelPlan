"""
LLM 调用辅助工具 - 统一管理所有 LLM 调用

支持同步调用和异步流式调用，统一日志和错误处理。
"""
import logging
import time
from typing import Optional, Any

from app.utils.llm_client import get_llm_client
from app.config import settings

logger = logging.getLogger(__name__)


def call_llm(
    prompt: str,
    model: str = None,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    context: str = "",
    parse_json: bool = False,
    default_response: Any = None
) -> Any:
    """
    统一的 LLM 调用接口

    Args:
        prompt: 提示词
        model: 模型名称（默认使用配置中的模型）
        temperature: 温度参数
        max_tokens: 最大 token 数
        context: 上下文描述（用于日志）
        parse_json: 是否解析为 JSON
        default_response: 失败时的默认响应

    Returns:
        LLM 响应内容（字符串或解析后的 JSON）
    """
    model = model or settings.LLM_MODEL
    start_time = time.time()

    try:
        logger.info(f"LLM 调用开始 - {context} (模型: {model})")

        client = get_llm_client()

        request_params = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "timeout": settings.LLM_TIMEOUT,
        }

        if max_tokens:
            request_params["max_tokens"] = max_tokens

        response = client.chat.completions.create(**request_params)

        content = response.choices[0].message.content.strip()
        duration = time.time() - start_time

        logger.info(f"LLM 调用成功 - {context} (耗时: {duration:.2f}s, 长度: {len(content)})")

        if parse_json:
            try:
                from app.utils.json_parser import parse_llm_json
                result = parse_llm_json(content, default_response or {})
                logger.debug(f"JSON 解析成功 - {context}")
                return result
            except Exception as e:
                logger.warning(f"JSON 解析失败 - {context}: {e}")
                return default_response if default_response is not None else content

        return content

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"LLM 调用失败 - {context} (耗时: {duration:.2f}s): {e}")

        if default_response is not None:
            return default_response
        raise


def call_llm_with_retry(
    prompt: str,
    max_retries: int = 2,
    **kwargs
) -> Any:
    """
    带重试的 LLM 调用

    Args:
        prompt: 提示词
        max_retries: 最大重试次数
        **kwargs: 其他参数传递给 call_llm
    """
    for attempt in range(max_retries + 1):
        try:
            return call_llm(prompt, **kwargs)
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"LLM 调用重试 {attempt + 1}/{max_retries}: {e}")
                time.sleep(1)
            else:
                raise


async def call_llm_stream(
    prompt: str,
    model: str = None,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    context: str = ""
):
    """
    统一的 LLM 流式调用接口

    Args:
        prompt: 提示词
        model: 模型名称（默认使用配置中的模型）
        temperature: 温度参数
        max_tokens: 最大 token 数
        context: 上下文描述（用于日志）

    Yields:
        str: 流式输出的文本片段
    """
    model = model or settings.LLM_MODEL
    start_time = time.time()

    try:
        logger.info(f"LLM 流式调用开始 - {context} (模型: {model})")

        from app.utils.llm_client import get_async_llm_client
        client = get_async_llm_client()

        request_params = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": True,
            "timeout": settings.LLM_TIMEOUT,
        }

        if max_tokens:
            request_params["max_tokens"] = max_tokens

        stream = await client.chat.completions.create(**request_params)

        accumulated = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                accumulated += content
                yield content

        duration = time.time() - start_time
        logger.info(f"LLM 流式调用完成 - {context} (耗时: {duration:.2f}s, 长度: {len(accumulated)})")

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"LLM 流式调用失败 - {context} (耗时: {duration:.2f}s): {e}")
        raise
