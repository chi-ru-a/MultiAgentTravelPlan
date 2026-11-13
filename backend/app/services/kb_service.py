"""
知识库服务 - 使用向量数据库
"""
from typing import List, Dict

from app.config import settings
from app.vectors import (
    VectorAccesserAdapter,
    AccesserType,
    EMBEDDINGS,
    reinitialize_embeddings
)


class KnowledgeBaseService:
    """知识库服务"""

    def __init__(self, use_internal_db: bool = True):
        """
        初始化知识库服务

        Args:
            use_internal_db: 是否使用内部向量数据库
        """
        self.use_internal_db = use_internal_db

        # 重新初始化向量化服务（确保使用配置的地址）
        reinitialize_embeddings(
            url=settings.EMBEDDINGS_URL,
            model_name=settings.EMBEDDINGS_MODEL
        )

        # 配置向量数据库
        self._init_vector_db()

        # 返回向量数据时不包含向量本身
        self.with_vectors = False

    # 初始化向量库
    def _init_vector_db(self):
        """初始化向量数据库连接"""
        # 根据配置选择向量数据库类型
        db_type = settings.VECTOR_DB_TYPE.upper()
        accesser_type = AccesserType.valueOfName(db_type) if db_type in ["ES", "QDRANT"] else AccesserType.ES

        # 创建适配器
        self.adapter = VectorAccesserAdapter(accesser_type)

        # 获取带嵌入功能的访问器
        if accesser_type == AccesserType.ES:
            self.vector_accesser = self.adapter.get_vector_embeddings_accesser(
                embeddings=EMBEDDINGS,
                url=settings.ES_URL,
                index=settings.ES_INDEX
            )
        else:  # QDRANT
            self.vector_accesser = self.adapter.get_vector_embeddings_accesser(
                embeddings=EMBEDDINGS,
                url=settings.QDRANT_URL,
                port=settings.QDRANT_PORT,
                collection=settings.QDRANT_COLLECTION,
                dense_vector_size=settings.QDRANT_VECTOR_SIZE,
                indexes=settings.QDRANT_INDEXES
            )

    # 同步检索
    def search(self, query: str, top_k: int = 5, filter_condition: dict = None) -> List[Dict]:
        """
        查询知识库

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_condition: 额外的过滤条件

        Returns:
            查询结果列表
        """
        try:
            # 使用混合向量搜索（稠密+稀疏）
            results = self.vector_accesser.query(
                vector_query=query,
                limit=top_k,
                score=0,  # 不设置最低分数
                query_condition=filter_condition,
                with_vectors=self.with_vectors
            )
            return results if results else []

        except Exception as e:
            print(f"知识库查询失败: {e}")
            # 查询失败时返回空列表
            return []

    # 异步检索
    async def asearch(self, query: str, top_k: int = 3, filter_condition: dict = None) -> List[Dict]:
        """
        异步查询知识库

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_condition: 额外的过滤条件

        Returns:
            查询结果列表
        """
        try:
            results = await self.vector_accesser.aquery(
                vector_query=query,
                limit=top_k,
                score=0,
                query_condition=filter_condition,
                with_vectors=self.with_vectors
            )
            return results if results else []

        except Exception as e:
            print(f"知识库异步查询失败: {e}")
            return []

    # 添加单个文档
    def add_document(self, content: str, title: str = "", source: str = "", metadata: dict = None) -> str:
        """
        添加文档到知识库

        Args:
            content: 文档内容
            title: 文档标题
            source: 来源
            metadata: 元数据

        Returns:
            文档ID
        """
        doc_data = {
            "vectorData": content,  # 会自动向量化
            "content": content,
            "title": title,
            "source": source,
            "metadata": metadata or {}
        }
        self.vector_accesser.store(doc_data)
        return doc_data.get("id")

    # 添加多个文档
    def add_documents(self, documents: List[Dict]) -> None:
        """
        批量添加文档到知识库

        Args:
            documents: 文档列表，每个文档包含 content, title, source, metadata 等字段
        """
        self.vector_accesser.store_list(documents)

    # 删除单个文档
    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档

        Args:
            doc_id: 文档ID

        Returns:
            是否删除成功
        """
        try:
            self.vector_accesser.delete(doc_id)
            return True
        except Exception as e:
            print(f"删除文档失败: {e}")
            return False

    # 获取文档
    def get_document(self, doc_id: str) -> Dict:
        """
        获取文档

        Args:
            doc_id: 文档ID

        Returns:
            文档内容
        """
        return self.vector_accesser.get(doc_id, with_vectors=False)

    def count(self, condition: dict = None) -> int:
        """
        统计文档数量

        Args:
            condition: 过滤条件

        Returns:
            文档数量
        """
        if condition:
            return self.vector_accesser.count_condition(condition)
        # 不传条件时返回默认集合的总数
        return self.vector_accesser.count_condition({})



# 全局单例  KnowledgeBaseService 的对象，用于在整个应用中共享知识库服务实例，避免重复初始化和资源浪费
_kb_service_instance = None


# 获取知识库服务单例  _kb_service_instance
def get_kb_service() -> KnowledgeBaseService:
    """获取知识库服务单例"""
    global _kb_service_instance
    if _kb_service_instance is None:
        _kb_service_instance = KnowledgeBaseService()
    return _kb_service_instance


# 重置知识库服务  将 _kb_service_instance 设置为 None
def reset_kb_service():
    """重置知识库服务（用于测试）"""
    global _kb_service_instance
    _kb_service_instance = None