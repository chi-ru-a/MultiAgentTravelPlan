"""
向量化服务模块 - 使用 OpenAI 兼容接口
"""
import asyncio
from abc import abstractmethod
from typing import List
import openai
import requests



# 代理模式：Embeddings 接口、 EmbeddingsProxy 代理类、OpenAIRemoteEmbeddings 被代理类/具体实现类

"""
抽象类，定义向量化该有哪些方法
"""
class Embeddings:
    """向量化抽象基类"""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """将多个文本转换为向量"""
        raise NotImplementedError("embed_documents is not implemented")

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """将单个文本转换为向量"""
        raise NotImplementedError("embed_query is not implemented")

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """异步向量化多个文本"""
        return await asyncio.get_event_loop().run_in_executor(None, self.embed_documents, texts)

    async def aembed_query(self, text: str) -> List[float]:
        """异步向量化单个文本"""
        return await asyncio.get_event_loop().run_in_executor(None, self.embed_query, text)

    @abstractmethod
    def sparse_documents(self, texts: List[str]) -> list[dict]:
        """生成稀疏向量"""
        pass

    def sparse_query(self, text: str) -> dict:
        """生成单个稀疏向量"""
        return self.sparse_documents([text])[0]

    async def asparse_documents(self, texts: List[str]) -> list[dict]:
        """异步生成稀疏向量"""
        return await asyncio.get_event_loop().run_in_executor(None, self.sparse_documents, texts)

    async def asparse_query(self, text: str) -> dict:
        """异步生成单个稀疏向量"""
        return await asyncio.get_event_loop().run_in_executor(None, self.sparse_query, text)

"""
具体实现，OpenAI 兼容接口的远程向量化服务
"""
class OpenAIRemoteEmbeddings(Embeddings):
    """OpenAI 兼容接口的远程向量化服务"""

    # 初始化
    def __init__(self, url: str, model_name: str = "bge-m3"):
        """
        初始化

        Args:
            url: 向量服务地址
            model_name: 模型名称
        """
        self.url = url
        self.model_name = model_name
        print(f"[Embeddings] 初始化向量化服务: {url}, 模型: {model_name}")
        self.embed_model = openai.Client(api_key="none", base_url=url)
        self.aembed_model = openai.AsyncClient(api_key="none", base_url=url)

    # 稠密向量，向量化多个文本
    def embed_documents(self, texts: list[str]) -> List[List[float]]:
        """向量化多个文本"""
        result = []
        for dat in self.embed_model.embeddings.create(model=self.model_name, input=texts).data:
            result.append(dat.embedding)
        return result

    # 稠密向量，向量化单个文本
    def embed_query(self, text: str) -> List[float]:
        """向量化单个文本"""
        return self.embed_documents([text]).pop()
    
    # 异步
    async def aembed_documents(self, texts: list[str]) -> List[List[float]]:
        """异步向量化多个文本"""
        response = await self.embed_model.embeddings.create(model=self.model_name, input=texts)
        return [d.embedding for d in response.data]
    
    # 异步
    async def aembed_query(self, text: str) -> List[float]:
        """异步向量化单个文本"""
        embeddings = await self.aembed_documents([text])
        return embeddings[0]

    # 稀疏向量，不走 OpenAI SDK，因为没有
    # 直接 requests.post 发请求，再解析返回结果，解析为 indices 和 values
    def sparse_documents(self, texts: List[str]) -> list[dict]:
        """生成稀疏向量"""
        # 构建完整的 URL
        full_url = self.url.rstrip('/') + "/sparse_embeddings"
        response = requests.post(full_url, json={"input": texts}, timeout=30)
        response.raise_for_status()

        result = []
        for sparse_embedding in response.json().get("data", []):
            embedding_data = sparse_embedding.get('embedding', {})
            result.append({
                "indices": embedding_data.get('indices', []),
                "values": embedding_data.get('values', []),
            })
        return result

"""
代理，不干活，负责懒加载配置和实例化 OpenAIRemoteEmbeddings，OpenAIRemoteEmbeddings 是干活的
"""
class EmbeddingsProxy(Embeddings):
    """向量化服务代理，支持懒加载配置更新"""

    _instance = None
    _embeddings_instance = None
    _url = None
    _model_name = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(EmbeddingsProxy, cls).__new__(cls)
        return cls._instance

    def __init__(self, url: str = None, model_name: str = "bge-m3"):
        """
        初始化代理

        Args:
            url: 向量服务地址
            model_name: 模型名称
        """
        # 保存配置参数
        if url is not None:
            self._url = url
        if model_name != "bge-m3":
            self._model_name = model_name

        # 如果已有 embeddings 实例且 url 变化了，重新创建
        if self._embeddings_instance and url is not None:
            old_url = getattr(self._embeddings_instance, 'url', None)
            if old_url != url:
                self._embeddings_instance = None

    @property
    def embeddings(self) -> OpenAIRemoteEmbeddings:
        """获取 embeddings 实例（懒加载）"""
        if self._embeddings_instance is None:
            # 从配置获取默认值
            if self._url is None:
                try:
                    from app.config import settings
                    self._url = settings.EMBEDDINGS_URL
                    self._model_name = settings.EMBEDDINGS_MODEL
                except ImportError:
                    self._url = "http://saas-model-api.xx.com/model-api/embeddings/v1"
                    self._model_name = "bge-m3"

            if self._model_name is None:
                self._model_name = "bge-m3"

            self._embeddings_instance = OpenAIRemoteEmbeddings(url=self._url, model_name=self._model_name)
        return self._embeddings_instance

    @embeddings.setter
    def embeddings(self, value: OpenAIRemoteEmbeddings):
        """直接设置 embeddings 实例"""
        self._embeddings_instance = value

    def embed_documents(self, texts: List[str], chunk_size: int = 0) -> List[List[float]]:
        """向量化多个文本"""
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """向量化单个文本"""
        return self.embeddings.embed_query(text)

    def sparse_documents(self, texts: List[str]) -> list[dict]:
        """生成稀疏向量"""
        return self.embeddings.sparse_documents(texts)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """异步向量化多个文本"""
        return await super().aembed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        """异步向量化单个文本"""
        return await super().aembed_query(text)


# 全局单例实例（懒加载，在首次使用时从配置读取）
EMBEDDINGS = EmbeddingsProxy()


def reinitialize_embeddings(url: str = None, model_name: str = None):
    """
    重新初始化全局 EMBEDDINGS 实例

    Args:
        url: 向量服务地址（可选，不传则从配置读取）
        model_name: 模型名称（可选）
    """
    global EMBEDDINGS
    if url is None or model_name is None:
        from app.config import settings
        url = url or settings.EMBEDDINGS_URL
        model_name = model_name or settings.EMBEDDINGS_MODEL

    # 强制重新创建实例
    EMBEDDINGS._embeddings_instance = None
    EMBEDDINGS._url = url
    EMBEDDINGS._model_name = model_name
    print(f"[Embeddings] 重新初始化: {url}, 模型: {model_name}")