"""
向量数据库访问适配器 - 管理向量数据库访问器实例
"""
import contextvars
from enum import Enum

# 枚举  支持哪些向量数据库
class AccesserType(Enum):
    ES = "ES"
    QDRANT = "QDRANT"

    @classmethod
    def valueOfName(cls, name: str):
        """根据名称获取枚举值"""
        for item in cls:
            if item.name == name:
                return item


# 默认向量库名称
DEFAULT_VECTOR_NAME = "default"

# 上下文变量，保存当前协程的访问器实例   按协程隔离的缓存
vector_accesser_context = contextvars.ContextVar("vector_accesser", default={})

# 适配器主体
class VectorAccesserAdapter:
    """向量数据库访问适配器"""

    def __init__(self, accesser_type: AccesserType = AccesserType.ES):
        """
        初始化适配器

        Args:
            accesser_type: 向量数据库类型
        """
        self.accesser_type = accesser_type

    def choose_accesser(self, accesser_type: AccesserType):
        """切换向量数据库访问方式"""
        self.accesser_type = accesser_type

    def get_vector_accesser(self, data_type: str = None, newed: bool = False, **kwargs):
        """
        获取向量数据库访问器

        Args:
            data_type: 数据类型/集合名称，默认使用 default
            newed: 是否创建新实例
            **kwargs: 其他参数（ES: url, index; Qdrant: url, port, collection）

        Returns:
            向量访问器实例
        """
        if not data_type:
            data_type = DEFAULT_VECTOR_NAME

        if newed:
            return self._build_vector_accesser(data_type, **kwargs)

        vector_accesser_map = vector_accesser_context.get()
        accesser = vector_accesser_map.get(data_type)
        if accesser:
            return accesser

        accesser = self._build_vector_accesser(data_type, **kwargs)
        vector_accesser_map[data_type] = accesser
        vector_accesser_context.set(vector_accesser_map)
        return accesser

    def _build_vector_accesser(self, data_type: str = None, **kwargs):
        """
        构建向量数据库访问器

        Args:
            data_type: 数据类型/集合名称
            **kwargs: 其他参数

        Returns:
            向量访问器实例
        """
        if self.accesser_type == AccesserType.ES:
            from .accessor.es_vector_accesser import EsVectorAccesser
            url = kwargs.get('url', 'http://localhost:9200')
            index = kwargs.get('index', data_type if data_type != DEFAULT_VECTOR_NAME else 'knowledge_base')
            return EsVectorAccesser(url, index)

        if self.accesser_type == AccesserType.QDRANT:
            from .accessor.qdrant_vector_accesser import QdrantVectorAccesser
            url = kwargs.get('url', 'http://localhost')
            port = kwargs.get('port', 6333)
            collection = kwargs.get('collection', data_type if data_type != DEFAULT_VECTOR_NAME else 'knowledge_base')
            dense_vector_size = kwargs.get('dense_vector_size', 1024)
            indexes = kwargs.get('indexes', {})
            return QdrantVectorAccesser(url, port, collection, dense_vector_size, indexes)

        raise RuntimeError(f"暂不支持此向量数据库访问方式[{self.accesser_type}]")

    def get_vector_embeddings_accesser(self, embeddings, data_type: str = None, newed: bool = False, **kwargs):
        """
        获取带嵌入功能的向量访问器

        Args:
            embeddings: 向量化服务实例
            data_type: 数据类型/集合名称
            newed: 是否创建新实例
            **kwargs: 其他参数

        Returns:
            VectorEmbeddingsAccesserProxy 实例
        """
        from .vector_accessor import VectorEmbeddingsAccesserProxy
        accesser = self.get_vector_accesser(data_type, newed, **kwargs)
        return VectorEmbeddingsAccesserProxy(accesser, embeddings)