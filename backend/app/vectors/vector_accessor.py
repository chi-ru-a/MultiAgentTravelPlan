"""
向量访问器抽象基类
"""
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from .utils.md5_util import md5_string


"""
VectorEmbeddingsAccesserProxy【文本向量化 + 操作数据库】 --> VectorAccesser【操作数据库的抽象】 --> QdrantVectorAccesser【具体实现操作数据库】
"""

# 抽象基类，定义向量数据库该有哪些操作；相当于 Java 的接口、抽象类
class VectorAccesser(ABC):
    """向量数据库访问器抽象基类"""

    async def astore(self, data: dict):
        """异步存储向量数据"""
        return await asyncio.get_event_loop().run_in_executor(None, self.store, data)

    async def astore_list(self, datas: list[dict]):
        """异步存储多条向量数据"""
        return await asyncio.get_event_loop().run_in_executor(None, self.store_list, datas)

    @abstractmethod
    def store(self, data: dict):
        """
        存储向量数据

        Args:
            data: dict, 必须包含字段 id (str), vectorData (list)
        """
        pass

    @abstractmethod
    def store_list(self, datas: list[dict]):
        """存储多条向量数据"""
        pass

    async def aquery(self, vector_arr: list, limit: int = 7, score: float = 1.3, query_condition: dict = None, with_vectors: bool = True):
        """异步查询向量数据"""
        return await asyncio.get_event_loop().run_in_executor(
            self.query, vector_arr, limit, score, query_condition, with_vectors
        )

    @abstractmethod
    def query(self, vector_arr: list, limit: int = 7, score: float = 1.3, query_condition: dict = None, with_vectors: bool = True):
        """查询向量数据"""
        pass

    def query_mix(self, vector_arr: list, sparse_vector, limit: int = 7, score: float = 1.3, query_condition: dict = None, with_vectors: bool = True):
        """混合向量查询（稠密+稀疏）"""
        pass

    async def aquery_mix(self, vector_arr: list, sparse_vector, limit: int = 7, score: float = 1.3, query_condition: dict = None, with_vectors: bool = True):
        """异步混合向量查询"""
        pass

    async def aquery_condition(self, condition: dict, limit: int = 1000, with_vectors: bool = True):
        """异步条件查询"""
        return await asyncio.get_event_loop().run_in_executor(
            self.query_condition, condition, limit, with_vectors
        )

    @abstractmethod
    def query_condition(self, condition: dict, limit: int = 1000, with_vectors: bool = True):
        """条件查询"""
        pass

    @abstractmethod
    def count_condition(self, condition: dict):
        """统计符合条件的数量"""
        pass

    @abstractmethod
    def query_page(self, page_num: int, page_size: int, condition: dict, orderkeys: dict = None, with_vectors: bool = True):
        """分页查询"""
        pass

    async def acount_condition(self, condition: dict):
        """异步统计"""
        return await asyncio.get_event_loop().run_in_executor(None, self.count_condition, condition)

    async def aquery_page(self, page_num: int, page_size: int, condition: dict, orderkeys: dict = None, with_vectors: bool = True):
        """异步分页查询"""
        return await asyncio.get_event_loop().run_in_executor(
            self.query_page, page_num, page_size, condition, orderkeys, with_vectors
        )

    async def aget(self, id_: str, with_vectors: bool = True):
        """异步根据ID获取"""
        return await asyncio.get_event_loop().run_in_executor(None, self.get, id_, with_vectors)

    @abstractmethod
    def get(self, id_: str, with_vectors: bool = True):
        """根据ID获取"""
        pass

    async def adelete_condition(self, condition: dict):
        """异步条件删除"""
        return await asyncio.get_event_loop().run_in_executor(None, self.delete_condition, condition)

    @abstractmethod
    def delete_condition(self, condition: dict):
        """条件删除"""
        pass

    async def adelete(self, id_: str):
        """异步ID删除"""
        return await asyncio.get_event_loop().run_in_executor(None, self.delete, id_)

    @abstractmethod
    def delete(self, id_: str):
        """ID删除"""
        pass


# 代理层，文本 --> 向量化 --> 向量数据库访问器
class VectorEmbeddingsAccesserProxy:
    """向量 Embeddings 访问器代理 - 自动处理向量化"""

    def __init__(self, accesser: VectorAccesser, embeddings):
        """
        初始化代理

        Args:
            accesser: 向量数据库访问器
            embeddings: 向量化服务
        """
        self.accesser = accesser
        self.embeddings = embeddings

    def store(self, data: dict, check_exist: bool = True):
        """
        保存数据（自动向量化）

        Args:
            data: 数据字典，需包含 content 或 varcharData 字段
            check_exist: 是否检查已存在
        """
        # 给数据增加签名
        if data.get('sign') is None:
            data['sign'] = md5_string(str(data))
        if data.get('id') is None:
            data['id'] = data['sign']

        # 检查是否存在
        if check_exist:
            exist = self.accesser.query_condition({"sign": data.get('sign')})
            if exist is not None and len(exist) > 0:
                return

        # 文本向量化
        if data.get('vectorData') and isinstance(data.get('vectorData'), str):
            vectorData = data.get('vectorData')
            data['vectorData'] = self.embeddings.embed_query(vectorData)
            data['sparseData'] = self.embeddings.sparse_query(vectorData)

        self.accesser.store(data)

    async def astore(self, data: dict, check_exist: bool = True):
        """异步保存数据（自动向量化）"""
        # 给数据增加签名
        if data.get('sign') is None:
            data['sign'] = md5_string(str(data))
        if data.get('id') is None:
            data['id'] = data['sign']

        # 检查是否存在
        if check_exist:
            exist = await self.accesser.aquery_condition({"sign": data.get('sign')})
            if exist is not None and len(exist) > 0:
                return

        # 文本向量化
        if data.get('vectorData') and isinstance(data.get('vectorData'), str):
            vectorData = data.get('vectorData')
            data['vectorData'] = await self.embeddings.aembed_query(vectorData)
            data['sparseData'] = await self.embeddings.asparse_query(vectorData)

        await self.accesser.astore(data)

    async def astore_list(self, datas: list):
        """异步保存多条数据"""
        if not datas:
            return
        for data in datas:
            if data.get('vectorData') and isinstance(data.get('vectorData'), str):
                vectorData = data.get('vectorData')
                data['vectorData'] = await self.embeddings.aembed_query(vectorData)
                data['sparseData'] = await self.embeddings.asparse_query(vectorData)
        await self.accesser.astore_list(datas)

    def store_list(self, datas: list):
        """保存多条数据"""
        if not datas:
            return
        for data in datas:
            if data.get('vectorData') and isinstance(data.get('vectorData'), str):
                vectorData = data.get('vectorData')
                data['vectorData'] = self.embeddings.embed_query(vectorData)
                data['sparseData'] = self.embeddings.sparse_query(vectorData)
        self.accesser.store_list(datas)

    def query(self, vector_query: str, limit: int = 7, score: float = 0, query_condition: dict = None, with_vectors: bool = False):
        """
        文本查询（自动将查询文本向量化）

        Args:
            vector_query: 查询文本
            limit: 返回数量
            score: 最小分数
            query_condition: 额外的查询条件
            with_vectors: 是否返回向量
        """
        result = self.accesser.query_mix(
            self.embeddings.embed_query(vector_query),
            self.embeddings.sparse_query(vector_query),
            limit, score, query_condition, with_vectors
        )
        if result is not None and with_vectors is False:
            for data in result:
                data.pop('vectorData', None)
                data.pop('sparseData', None)
        return result

    async def aquery(self, vector_query: str, limit: int = 7, score: float = 0, query_condition: dict = None, with_vectors: bool = False):
        """异步文本查询"""
        result = await self.accesser.aquery_mix(
            await self.embeddings.aembed_query(vector_query),
            await self.embeddings.asparse_query(vector_query),
            limit, score, query_condition, with_vectors
        )
        if result is not None and with_vectors is False:
            for data in result:
                data.pop('vectorData', None)
                data.pop('sparseData', None)
        return result

    def query_condition(self, condition: dict, limit: int = 1000, with_vectors: bool = False):
        """条件查询"""
        return self.accesser.query_condition(condition, limit, with_vectors)

    async def aquery_condition(self, condition: dict, limit: int = 1000, with_vectors: bool = False):
        """异步条件查询"""
        return await self.accesser.aquery_condition(condition, limit, with_vectors)

    def count_condition(self, condition: dict):
        """统计数量"""
        return self.accesser.count_condition(condition)

    def query_page(self, page_num: int, page_size: int, condition: dict, orderkeys: dict = None, with_vectors: bool = True):
        """分页查询"""
        return self.accesser.query_page(page_num, page_size, condition, orderkeys, with_vectors)

    async def acount_condition(self, condition: dict):
        """异步统计"""
        return await self.accesser.acount_condition(condition)

    async def aquery_page(self, page_num: int, page_size: int, condition: dict, orderkeys: dict = None, with_vectors: bool = True):
        """异步分页查询"""
        return await self.accessor.aquery_page(page_num, page_size, condition, orderkeys, with_vectors)

    def delete_condition(self, condition: dict):
        """条件删除"""
        return self.accesser.delete_condition(condition)

    async def adelete_condition(self, condition: dict):
        """异步条件删除"""
        return await self.accessor.adelete_condition(condition)

    async def adelete(self, id_: str):
        """异步删除"""
        return await self.accesser.adelete(id_)

    def delete(self, id_: str):
        """ID 删除"""
        return self.accesser.delete(id_)

    async def aget(self, id_: str, with_vectors: bool = False):
        """异步 ID 查询"""
        return await self.accesser.aget(id_, with_vectors)

    def get(self, id_: str, with_vectors: bool = False):
        """ID 查询"""
        return self.accesser.get(id_, with_vectors)