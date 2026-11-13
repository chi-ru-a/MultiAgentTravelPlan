"""
Qdrant 向量访问器
"""
import json
import asyncio
import httpx
import hashlib
from typing import List, Optional, Any, Dict
from ..vector_accessor import VectorAccesser


"""
Payload 是附加在 Qdrant 每个数据点（Point）上的自定义 JSON 元数据
它本身不参与向量相似度计算，但可以用来 过滤 和 返回结果
过滤：在搜索时，可以用 Payload 里的字段（比如 source、year、category）来限定搜索范围，只在关心的数据里找相似向量
返回结果：搜索命中后，Payload 里的信息（如文章标题、内容片段、链接）会一并返回，可以知道这个向量对应的是什么具体内容

稠密向量就是文本、图片、音频等经过向量化后的高维向量，通常是浮点数数组；检索就是相似度检索
关键词检索会生成稀疏向量，再按稀疏向量检索得到结果；
但关键词检索只是生成稀疏向量的一种方式，还有其他方式，比如 LLM 生成稀疏向量等。
稀疏向量中：indices 权重非零位置，values 非零权重的值，不会存储整个向量，因为很稀疏，太浪费空间
"""

# Qdrant 向量库的访问器
class QdrantVectorAccesser(VectorAccesser):
    """Qdrant 向量访问器"""


    """
    这是 5 个辅助函数：初始化客户端、确保集合存在、构建过滤条件【用于条件查询】、解析查询结果、解析单个点【统一返回的数据格式】
    """
    # 初始化同步/异步客户端，共用 base_url
    def __init__(self, url: str, port: int, collection: str = "knowledge_base",
                 dense_vector_size: int = 1024, indexes: Dict = None):
        """
        初始化 Qdrant 访问器
        """
        self.url = url
        self.port = port
        self.collection = collection
        self.dense_vector_size = dense_vector_size
        self.indexes = indexes or {}

        # 构建 base_url
        if url.startswith("http://") or url.startswith("https://"):
            base = url.rstrip("/")
            self.base_url = f"{base}:{port}" if port and port not in [80, 443] else base
        else:
            self.base_url = f"http://{url}:{port}"

        # 同步客户端
        self.client = httpx.Client(base_url=self.base_url, timeout=300)  # 300s
        # 异步客户端
        self.aclient = httpx.AsyncClient(base_url=self.base_url, timeout=300)

    # 集合存在啥也不做，不存在创建集合；确保集合存在
    def _init_collection(self):
        """初始化 Qdrant 集合"""
        # 检查集合是否存在
        try:
            response = self.client.get(f"/collections/{self.collection}")
            if response.status_code == 200:
                return
        except Exception:
            pass

        # 稠密向量配置
        vectors_config = {
            "size": self.dense_vector_size,  # 维度
            "distance": "Cosine"  # 距离计算方式
        }

        # 稀疏向量配置
        sparse_vectors_config = {
            "content_sparse": {
                "index": "sparse"
            }
        }

        payload = {
            "vectors": vectors_config,
            "sparse_vectors": sparse_vectors_config
        }

        # 用两种配置创建集合
        response = self.client.put(
            f"/collections/{self.collection}?timeout=60",
            json=payload
        )
        response.raise_for_status()  # 创建失败抛异常

    # 把字典转成 Qdrant 的 filter 格式，用于条件查询
    def _build_filter(self, condition: dict) -> Optional[dict]:
        """构建 Qdrant filter"""
        if not condition:
            return None

        must = []
        for key, value in condition.items():
            if not value:
                continue
            # 值为字典时，说明已经是 filter 格式，跳过
            if isinstance(value, dict):
                continue
            if isinstance(value, (str, int, float, bool)):  # 值是标量  match.value
                must.append({
                    "key": f"payload.{key}",
                    "match": {"value": value}
                })
            elif isinstance(value, list):  # 值是列表  match.any，匹配列表中任意一个
                must.append({
                    "key": f"payload.{key}",
                    "match": {"any": value}
                })

        return {"must": must} if must else None

    # 解析函数，把 Qdrant 返回的原始 point 转成业务层统一的字典结构
    # data 里面包含多个 point
    def _parse_results(self, data: dict, with_vectors: bool) -> list:
        """解析响应结果"""
        results = []
        for point in data.get("result", []):
            payload = point.get("payload", {})
            result = {
                "id": point.get("id"),
                "score": point.get("score", 0),
                "content": payload.get("content", ""),
                "title": payload.get("title", ""),
                "source": payload.get("source", ""),
            }
            # 合并其他 payload 字段
            for k, v in payload.items():
                if k not in ["content", "title", "source", "content_sparse"]:
                    result[k] = v

            if with_vectors:
                result["vectorData"] = point.get("vector")
                result["sparseData"] = payload.get("content_sparse")

            results.append(result)
        return results

    # 解析单个 point
    def _parse_point(self, point: dict, with_vectors: bool) -> dict:
        """解析单个点"""
        payload = point.get("payload", {})
        result = {
            "id": point.get("id"),
            "content": payload.get("content", ""),
            "title": payload.get("title", ""),
            "source": payload.get("source", ""),
        }
        for k, v in payload.items():
            if k not in ["content", "title", "source", "content_sparse"]:
                result[k] = v
        if with_vectors:
            result["vectorData"] = point.get("vector")
            result["sparseData"] = payload.get("content_sparse")
        return result


    """
    写入：存单条和批量存【批量存汇总数据，只访问一次数据库，提高效率】
    """
    # 存储单条数据  put
    def store(self, data: dict):
        """存储单条数据"""

        # id
        doc_id = data.get("id")
        if not doc_id:
            # 没有 id 就用 content 的 MD5 前 32 位当 id（内容寻址，相同内容得到相同 id，天然去重）
            doc_id = hashlib.md5(data.get("content", "").encode()).hexdigest()[:32]
            data["id"] = doc_id

        # 存放的数据  id、向量数据、原始数据
        payload = {
            "id": doc_id,
            "vector": data.get("vectorData", []),  # 向量数据
            "payload": {  # 原始数据
                "content": data.get("content", ""),
                "title": data.get("title", ""),
                "source": data.get("source", ""),
                **data.get("metadata", {})
            }
        }

        # 稀疏向量
        sparse_data = data.get("sparseData")
        if sparse_data and (sparse_data.get("indices") or sparse_data.get("values")):
            # 如果有稀疏向量，把稀疏向量放到 payload 的 content_sparse 字段里
            payload["payload"]["content_sparse"] = {
                "indices": sparse_data.get("indices", []),
                "values": sparse_data.get("values", [])
            }

        # 写入 Qdrant  put
        response = self.client.put(
            f"/collections/{self.collection}/points",
            json={"points": [payload]}
        )
        response.raise_for_status()  # 写入过程中如果失败会抛异常
    
    # 批量存储。对每条数据做和 store 一样的处理，攒进 points 列表，最后一次请求提交所有点。
    # 比循环调 store 高效得多（一次网络往返 vs N 次）。
    def store_list(self, datas: list[dict]):
        """批量存储数据"""
        points = []
        for data in datas:
            doc_id = data.get("id")
            if not doc_id:
                doc_id = hashlib.md5(data.get("content", "").encode()).hexdigest()[:32]
                data["id"] = doc_id

            sparse_data = data.get("sparseData")
            point = {
                "id": doc_id,
                "vector": data.get("vectorData", []),
                "payload": {
                    "content": data.get("content", ""),
                    "title": data.get("title", ""),
                    "source": data.get("source", ""),
                    **data.get("metadata", {})
                }
            }

            if sparse_data and (sparse_data.get("indices") or sparse_data.get("values")):
                point["payload"]["content_sparse"] = {
                    "indices": sparse_data.get("indices", []),
                    "values": sparse_data.get("values", [])
                }

            points.append(point)

        if points:
            response = self.client.put(
                f"/collections/{self.collection}/points",
                json={"points": points}
            )
            response.raise_for_status()


    """
    查询 get
    """
    # 稠密向量相似度检索  post
    def query(self, vector_arr: list, limit: int = 7, score: float = 1.3,
             query_condition: dict = None, with_vectors: bool = True):
        """向量搜索"""

        search_payload = {
            "vector": vector_arr,  # 查询向量
            "limit": limit,  # 返回条数
            "with_payload": True,  # 要返回 payload
            "with_vectors": False  # 不返回原始向量
        }

        # 如果有查询条件 query_condition，就塞入过滤条件
        filter_query = self._build_filter(query_condition) if query_condition else None
        if filter_query:
            search_payload["filter"] = filter_query

        # 发送查询请求   post
        response = self.client.post(
            f"/collections/{self.collection}/points/search",
            json=search_payload
        )
        response.raise_for_status()  # 查询失败抛异常

        data = response.json()
        return self._parse_results(data, with_vectors)  # 解析查询结果并返回

    # 稠密向量和稀疏向量混合检索  这个方法目前并没有实现稀疏向量检索，名不副实
    def query_mix(self, vector_arr: list, sparse_vector: dict, limit: int = 7, score: float = 0,
                  query_condition: dict = None, with_vectors: bool = True):
        """混合向量搜索"""
        # 如果没有稀疏向量，退化为稠密向量搜索
        sparse_indices = sparse_vector.get("indices", []) if sparse_vector else []
        sparse_values = sparse_vector.get("values", []) if sparse_vector else []

        if not sparse_indices or not sparse_values:
            return self.query(vector_arr, limit, score, query_condition, with_vectors)

        # 混合搜索 - 使用 recommend API 或简化处理
        # 这里简化为分别搜索后合并结果
        dense_results = self.query(vector_arr, limit * 2, score, query_condition, False)
        # 稀疏向量搜索暂不实现，返回稠密向量结果
        return dense_results[:limit]

    # 条件查询  查询所有满足条件的数据【原始数据(store 存的时候的 payload)，不返回向量】
    def query_condition(self, condition: dict, limit: int = 1000, with_vectors: bool = True):
        """条件查询"""
        filter_query = self._build_filter(condition)  # 构造查询条件

        scroll_result = self.client.post(   # 条件查询  post
            f"/collections/{self.collection}/points/scroll",
            json={
                "limit": limit,
                "with_payload": True,
                "with_vectors": False,
                "filter": filter_query if filter_query else {}
            }
        )
        scroll_result.raise_for_status()  # 条件查询失败抛异常

        data = scroll_result.json()
        results = [self._parse_point(p, with_vectors) for p in data.get("result", [])]  # 解析查询结果

        # 继续获取  一页一页的查询，直到没有下一页
        next_page_offset = data.get("next_page_offset")
        while next_page_offset is not None:
            scroll_result = self.client.post(
                f"/collections/{self.collection}/points/scroll",
                json={
                    "limit": limit,
                    "with_payload": True,   # 返回 payload
                    "with_vectors": False,  # 不返回原始向量
                    "filter": filter_query if filter_query else {},
                    "offset": next_page_offset
                }
            )
            scroll_result.raise_for_status()
            data = scroll_result.json()
            next_page_offset = data.get("next_page_offset")
            # 合并结果
            results.extend(self._parse_point(p, with_vectors) for p in data.get("result", []))

        return results

    # 统计满足条件的数量
    def count_condition(self, condition: dict):
        """统计数量"""
        filter_query = self._build_filter(condition)

        response = self.client.post(
            f"/collections/{self.collection}/points/count",
            json={"filter": filter_query if filter_query else {}}
        )
        response.raise_for_status()

        return response.json().get("count", 0)

    # 分页查询
    def query_page(self, page_num: int, page_size: int, condition: dict,
                   orderkeys: dict = None, with_vectors: bool = True):
        """分页查询"""
        from_val = (page_num - 1) * page_size  # 计算偏移量
        filter_query = self._build_filter(condition)  # 构建过滤条件

        payload = {
            "limit": page_size,
            "offset": from_val,
            "with_payload": True,
            "with_vectors": False,
            "filter": filter_query if filter_query else {}
        }

        response = self.client.post(
            f"/collections/{self.collection}/points/scroll",
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        results = [self._parse_point(p, with_vectors) for p in data.get("result", [])]

        return {
            "total": self.count_condition(condition),  # 总数
            "results": results  # 查询结果
        }

    # 根据 ID 取单条数据【store 存的时候的 id】
    def get(self, id_: str, with_vectors: bool = True):
        """根据ID获取"""
        response = self.client.get(
            f"/collections/{self.collection}/points/{id_}",
            params={"with_payload": True, "with_vectors": with_vectors}
        )
        if response.status_code == 404:
            return None

        response.raise_for_status()

        data = response.json()
        result = data.get("result")
        return self._parse_point(result, with_vectors) if result else None


    """
    删除  delete
    """
    # 根据 ID 删除单条数据【store 存的时候的 id】
    def delete(self, id_: str):
        """删除文档"""
        response = self.client.delete(
            f"/collections/{self.collection}/points",
            params={"points": [id_]}
        )
        response.raise_for_status()

    # 删除满足条件的所有数据
    def delete_condition(self, condition: dict):
        """条件删除"""
        filter_query = self._build_filter(condition)

        response = self.client.post(
            f"/collections/{self.collection}/points/delete",
            json={"filter": filter_query if filter_query else {}}
        )
        response.raise_for_status()



    """
    异步和同步的逻辑完全一样，只是在访问数据库时，用 await 和异步客户端 aclient
    """
    # ===== 异步方法 =====

    # 异步存单条数据，和同步逻辑完全一样，只是用 await self.aclient.put() 代替 self.client.put()
    async def astore(self, data: dict):
        """异步存储单条数据"""
        doc_id = data.get("id")
        if not doc_id:
            doc_id = hashlib.md5(data.get("content", "").encode()).hexdigest()[:32]
            data["id"] = doc_id

        payload = {
            "id": doc_id,
            "vector": data.get("vectorData", []),
            "payload": {
                "content": data.get("content", ""),
                "title": data.get("title", ""),
                "source": data.get("source", ""),
                **data.get("metadata", {})
            }
        }

        sparse_data = data.get("sparseData")
        if sparse_data and (sparse_data.get("indices") or sparse_data.get("values")):
            payload["payload"]["content_sparse"] = {
                "indices": sparse_data.get("indices", []),
                "values": sparse_data.get("values", [])
            }

        response = await self.aclient.put(
            f"/collections/{self.collection}/points",
            json={"points": [payload]}
        )
        response.raise_for_status()

    async def astore_list(self, datas: list[dict]):
        """异步批量存储"""
        points = []
        for data in datas:
            doc_id = data.get("id")
            if not doc_id:
                doc_id = hashlib.md5(data.get("content", "").encode()).hexdigest()[:32]
                data["id"] = doc_id

            sparse_data = data.get("sparseData")
            payload = {
                "id": doc_id,
                "vector": data.get("vectorData", []),
                "payload": {
                    "content": data.get("content", ""),
                    "title": data.get("title", ""),
                    "source": data.get("source", ""),
                    **data.get("metadata", {})
                }
            }

            if sparse_data and (sparse_data.get("indices") or sparse_data.get("values")):
                payload["payload"]["content_sparse"] = {
                    "indices": sparse_data.get("indices", []),
                    "values": sparse_data.get("values", [])
                }

            points.append(payload)

        if points:
            response = await self.aclient.put(
                f"/collections/{self.collection}/points",
                json={"points": points}
            )
            response.raise_for_status()

    async def aquery(self, vector_arr: list, limit: int = 7, score: float = 1.3,
                     query_condition: dict = None, with_vectors: bool = True):
        """异步向量搜索"""
        search_payload = {
            "vector": vector_arr,
            "limit": limit,
            "with_payload": True,
            "with_vectors": False
        }

        filter_query = self._build_filter(query_condition) if query_condition else None
        if filter_query:
            search_payload["filter"] = filter_query

        response = await self.aclient.post(
            f"/collections/{self.collection}/points/search",
            json=search_payload
        )
        response.raise_for_status()

        data = response.json()
        return self._parse_results(data, with_vectors)

    async def aquery_mix(self, vector_arr: list, sparse_vector: dict, limit: int = 7, score: float = 0,
                         query_condition: dict = None, with_vectors: bool = True):
        """异步混合向量搜索"""
        sparse_indices = sparse_vector.get("indices", []) if sparse_vector else []
        sparse_values = sparse_vector.get("values", []) if sparse_vector else []

        if not sparse_indices or not sparse_values:
            return await self.aquery(vector_arr, limit, score, query_condition, with_vectors)

        dense_results = await self.aquery(vector_arr, limit * 2, score, query_condition, False)
        return dense_results[:limit]

    async def aquery_condition(self, condition: dict, limit: int = 1000, with_vectors: bool = True):
        """异步条件查询"""
        filter_query = self._build_filter(condition)

        scroll_result = await self.aclient.post(
            f"/collections/{self.collection}/points/scroll",
            json={
                "limit": limit,
                "with_payload": True,
                "with_vectors": False,
                "filter": filter_query if filter_query else {}
            }
        )
        scroll_result.raise_for_status()

        data = scroll_result.json()
        results = [self._parse_point(p, with_vectors) for p in data.get("result", [])]

        next_page_offset = data.get("next_page_offset")
        while next_page_offset is not None:
            scroll_result = await self.aclient.post(
                f"/collections/{self.collection}/points/scroll",
                json={
                    "limit": limit,
                    "with_payload": True,
                    "with_vectors": False,
                    "filter": filter_query if filter_query else {},
                    "offset": next_page_offset
                }
            )
            scroll_result.raise_for_status()
            data = scroll_result.json()
            next_page_offset = data.get("next_page_offset")
            results.extend(self._parse_point(p, with_vectors) for p in data.get("result", []))

        return results

    async def acount_condition(self, condition: dict):
        """异步统计数量"""
        filter_query = self._build_filter(condition)

        response = await self.aclient.post(
            f"/collections/{self.collection}/points/count",
            json={"filter": filter_query if filter_query else {}}
        )
        response.raise_for_status()

        return response.json().get("count", 0)

    async def aquery_page(self, page_num: int, page_size: int, condition: dict,
                          orderkeys: dict = None, with_vectors: bool = True):
        """异步分页查询"""
        from_val = (page_num - 1) * page_size
        filter_query = self._build_filter(condition)

        payload = {
            "limit": page_size,
            "offset": from_val,
            "with_payload": True,
            "with_vectors": False,
            "filter": filter_query if filter_query else {}
        }

        response = await self.aclient.post(
            f"/collections/{self.collection}/points/scroll",
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        results = [self._parse_point(p, with_vectors) for p in data.get("result", [])]

        count = await self.acount_condition(condition)
        return {"total": count, "results": results}

    async def aget(self, id_: str, with_vectors: bool = True):
        """异步根据ID获取"""
        response = await self.aclient.get(
            f"/collections/{self.collection}/points/{id_}",
            params={"with_payload": True, "with_vectors": with_vectors}
        )
        if response.status_code == 404:
            return None

        response.raise_for_status()

        data = response.json()
        result = data.get("result")
        return self._parse_point(result, with_vectors) if result else None

    async def adelete(self, id_: str):
        """异步删除文档"""
        response = await self.aclient.delete(
            f"/collections/{self.collection}/points",
            params={"points": [id_]}
        )
        response.raise_for_status()

    async def adelete_condition(self, condition: dict):
        """异步条件删除"""
        filter_query = self._build_filter(condition)

        response = await self.aclient.post(
            f"/collections/{self.collection}/points/delete",
            json={"filter": filter_query if filter_query else {}}
        )
        response.raise_for_status()