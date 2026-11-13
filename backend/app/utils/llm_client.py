"""
LLM 客户端管理 - 使用依赖注入模式
"""
from functools import lru_cache
from openai import OpenAI, AsyncOpenAI
from app.config import settings

"""
这是 OpenAI 和 AsyncOpenAI 客户端，使用 OpenAI 官方提供的 Python SDK 调用模型，不走 LangChain、LangGraph
- OpenAI：同步客户端，适合阻塞调用
- AsyncOpenAI：异步客户端，适合异步调用
使用 lru_cache 装饰器缓存客户端实例，确保只创建一个 LLM 客户端实例，避免重复创建，提高性能
"""

@lru_cache(maxsize=1)  # 缓存函数返回值，确保只创建一个 LLM 客户端实例，避免重复创建
def get_llm_client() -> OpenAI:
    """
    获取 LLM 客户端单例（线程安全）
    使用 lru_cache 确保只创建一次
    """
    return OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        timeout=settings.LLM_TIMEOUT,
    )

@lru_cache(maxsize=1)  # 异步客户端
def get_async_llm_client() -> AsyncOpenAI:
    """
    获取异步 LLM 客户端单例
    """
    return AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        timeout=settings.LLM_TIMEOUT,
    )
