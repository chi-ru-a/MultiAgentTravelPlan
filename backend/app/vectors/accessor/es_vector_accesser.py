"""
Elasticsearch 向量访问器
"""
import json
import requests
import httpx
import asyncio
from typing import List, Optional, Any
from ..vector_accessor import VectorAccesser


def check_success(response):
    """检查响应是否成功"""
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(f"{response.status_code}:{response.text}")
    return response


class EsVectorAccesser(VectorAccesser):
    """Elasticsearch 向量访问器"""

    def __init__(self, url: str, index: str = "knowledge_base", type_: str = "doc"):
        """
        初始化ES访问器

        Args:
            url: Elasticsearch 地址，如 http://localhost:9200
            index: 索引名称
            type_: 文档类型
        """
        if not url.endswith("/"):
            url += "/"
        self.url = url
        self.index = index
        self.type_ = type_
        self.index_url = self.url + index
        self.type_url = self.url + index + "/" + type_
        self.arequests = httpx.AsyncClient(base_url=self.url, timeout=300)

        # 初始化索引
        self._init_index()

    def _init_index(self):
        """初始化索引和映射"""
        # 创建索引
        requests.put(self.index_url)

        # 定义映射
        mappings = {
            "properties": {
                "id": {"type": "keyword"},
                "vectorData": {
                    "type": "dense_vector",
                    "dims": 1024,  # 需要根据实际向量维度调整
                    "index": True,
                    "similarity": "cosine"
                },
                "sparseData": {
                    "type": "sparse_vector"
                },
                "content": {"type": "text"},
                "title": {"type": "text"},
                "source": {"type": "keyword"},
                "metadata": {"type": "object"}
            }
        }

        requests.put(self.index_url + "/_mapping", json=mappings)

    def store(self, data: dict):
        """存储单条数据"""
        doc_id = data.get("id")
        if not doc_id:
            doc_id = str(hash(data.get("content", "")))
            data["id"] = doc_id

        url = f"{self.type_url}/{doc_id}"
        check_success(requests.put(url, json=data))
        self._refresh()

    def store_list(self, datas: list[dict]):
        """批量存储数据"""
        bulk_data = []
        for doc in datas:
            doc_id = doc.get("id")
            if not doc_id:
                doc_id = str(hash(doc.get("content", "")))
                doc["id"] = doc_id

            action = {"index": {"_index": self.index, "_id": doc_id}}
            bulk_data.append(action)
            bulk_data.append(doc)

        if bulk_data:
            requests.put(self.url + "_bulk", data="\n".join([json.dumps(item, ensure_ascii=False) for item in bulk_data]) + "\n")
            self._refresh()

    def query(self, vector_arr: list, limit: int = 7, score: float = 1.3, query_condition: dict = None, with_vectors: bool = True):
        """向量相似度查询"""
        # 构建knn查询
        query = {
            "knn": {
                "field": "vectorData",
                "query_vector": vector_arr,
                "k": limit,
                "num_candidates": limit * 2
            }
        }

        # 添加分数过滤
        if score > 0:
            query["knn"]["min_score"] = score

        # 添加其他条件过滤
        if query_condition:
            query = {
                "bool": {
                    "must": [
                        query,
                        query_condition
                    ]
                }
            }

        result = requests.post(f"{self.index_url}/_search", json={"from": 0, "size": limit, "query": query})
        check_success(result)

        results = []
        for hit in json.loads(result.text).get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            if hit.get("_score"):
                source["score"] = hit["_score"]
            # 如果不需要返回向量数据，移除
            if not with_vectors:
                source.pop("vectorData", None)
                source.pop("sparseData", None)
            results.append(source)

        return results

    def query_mix(self, vector_arr: list, sparse_vector: dict, limit: int = 7, score: float = 1.3, query_condition: dict = None, with_vectors: bool = True):
        """混合向量查询（稠密+稀疏）"""
        # 使用 hybrid 查询 - sparse_vector 格式为 {indices: [], values: []}
        if not sparse_vector or not sparse_vector.get("indices"):
            # 没有稀疏向量，只使用稠密向量
            return self.query(vector_arr, limit, score, query_condition, with_vectors)

        # 构建 KNN 查询 - 稠密向量
        knn_dense = {
            "knn": {
                "field": "vectorData",
                "query_vector": vector_arr,
                "k": limit,
                "num_candidates": limit * 2
            }
        }

        # 添加分数过滤
        if score > 0:
            knn_dense["knn"]["min_score"] = score

        result = requests.post(f"{self.index_url}/_search", json={"from": 0, "size": limit, "query": knn_dense})
        check_success(result)

        results = []
        for hit in json.loads(result.text).get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            if hit.get("_score"):
                source["score"] = hit["_score"]
            if not with_vectors:
                source.pop("vectorData", None)
                source.pop("sparseData", None)
            results.append(source)

        return results

    async def aquery_mix(self, vector_arr: list, sparse_vector, limit: int = 7, score: float = 1.3, query_condition: dict = None, with_vectors: bool = True):
        """异步混合向量查询"""
        return await asyncio.get_event_loop().run_in_executor(
            self.query_mix, vector_arr, sparse_vector, limit, score, query_condition, with_vectors
        )

    def query_condition(self, condition: dict, limit: int = 1000, with_vectors: bool = True):
        """条件查询"""
        result = requests.post(f"{self.index_url}/_search", json={"from": 0, "size": limit, "query": condition})
        check_success(result)

        results = []
        for hit in json.loads(result.text).get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            if not with_vectors:
                source.pop("vectorData", None)
                source.pop("sparseData", None)
            results.append(source)

        return results

    def count_condition(self, condition: dict):
        """统计符合条件的数量"""
        result = requests.post(f"{self.index_url}/_count", json={"query": condition})
        check_success(result)
        return json.loads(result.text).get("count", 0)

    def query_page(self, page_num: int, page_size: int, condition: dict, orderkeys: dict = None, with_vectors: bool = True):
        """分页查询"""
        from_val = (page_num - 1) * page_size
        query = {
            "from": from_val,
            "size": page_size,
            "query": condition or {"match_all": {}}
        }

        if orderkeys:
            query["sort"] = []
            for field, direction in orderkeys.items():
                query["sort"].append({field: {"order": direction}})

        result = requests.post(f"{self.index_url}/_search", json=query)
        check_success(result)

        total = json.loads(result.text).get("hits", {}).get("total", 0)
        hits = json.loads(result.text).get("hits", {}).get("hits", [])

        results = []
        for hit in hits:
            source = hit.get("_source", {})
            if not with_vectors:
                source.pop("vectorData", None)
                source.pop("sparseData", None)
            results.append(source)

        return {
            "total": total,
            "results": results
        }

    def get(self, id_: str, with_vectors: bool = True):
        """根据ID获取"""
        result = requests.get(f"{self.type_url}/{id_}")
        if result.status_code == 404:
            return None
        check_success(result)
        source = json.loads(result.text).get("_source", {})
        if not with_vectors:
            source.pop("vectorData", None)
            source.pop("sparseData", None)
        return source

    def delete(self, id_: str):
        """删除文档"""
        check_success(requests.delete(f"{self.type_url}/{id_}"))
        self._refresh()

    def delete_condition(self, condition: dict):
        """条件删除"""
        requests.post(f"{self.index_url}/_delete_by_query?size=100000", json={"query": condition})
        self._refresh()

    def _refresh(self):
        """刷新索引"""
        requests.post(self.index_url + "/_refresh")

    # ===== 异步方法 =====

    async def astore(self, data: dict):
        """异步存储单条数据"""
        doc_id = data.get("id")
        if not doc_id:
            doc_id = str(hash(data.get("content", "")))
            data["id"] = doc_id

        url = f"{self.type_url}/{doc_id}"
        response = await self.arequests.put(url, json=data)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")
        await self._arefresh()

    async def astore_list(self, datas: list[dict]):
        """异步批量存储数据"""
        bulk_data = []
        for doc in datas:
            doc_id = doc.get("id")
            if not doc_id:
                doc_id = str(hash(doc.get("content", "")))
                doc["id"] = doc_id

            action = {"index": {"_index": self.index, "_id": doc_id}}
            bulk_data.append(action)
            bulk_data.append(doc)

        if bulk_data:
            bulk_str = "\n".join([json.dumps(item, ensure_ascii=False) for item in bulk_data]) + "\n"
            response = await self.arequests.put("_bulk", content=bulk_str)
            if response.status_code < 200 or response.status_code >= 300:
                raise RuntimeError(f"{response.status_code}:{response.text}")
            await self._arefresh()

    async def aquery(self, vector_arr: list, limit: int = 7, score: float = 1.3,
                     query_condition: dict = None, with_vectors: bool = True):
        """异步向量相似度查询"""
        query = {
            "knn": {
                "field": "vectorData",
                "query_vector": vector_arr,
                "k": limit,
                "num_candidates": limit * 2
            }
        }

        if score > 0:
            query["knn"]["min_score"] = score

        if query_condition:
            query = {
                "bool": {
                    "must": [
                        query,
                        query_condition
                    ]
                }
            }

        response = await self.arequests.post(
            f"{self.index}/_search",
            json={"from": 0, "size": limit, "query": query}
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")

        data = response.json()
        results = []
        for hit in data.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            if hit.get("_score"):
                source["score"] = hit["_score"]
            if not with_vectors:
                source.pop("vectorData", None)
                source.pop("sparseData", None)
            results.append(source)

        return results

    async def aquery_mix(self, vector_arr: list, sparse_vector: dict, limit: int = 7,
                         score: float = 1.3, query_condition: dict = None, with_vectors: bool = True):
        """异步混合向量查询"""
        if not sparse_vector or not sparse_vector.get("indices"):
            return await self.aquery(vector_arr, limit, score, query_condition, with_vectors)

        knn_dense = {
            "knn": {
                "field": "vectorData",
                "query_vector": vector_arr,
                "k": limit,
                "num_candidates": limit * 2
            }
        }

        if score > 0:
            knn_dense["knn"]["min_score"] = score

        response = await self.arequests.post(
            f"{self.index}/_search",
            json={"from": 0, "size": limit, "query": knn_dense}
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")

        data = response.json()
        results = []
        for hit in data.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            if hit.get("_score"):
                source["score"] = hit["_score"]
            if not with_vectors:
                source.pop("vectorData", None)
                source.pop("sparseData", None)
            results.append(source)

        return results

    async def aquery_condition(self, condition: dict, limit: int = 1000, with_vectors: bool = True):
        """异步条件查询"""
        response = await self.arequests.post(
            f"{self.index}/_search",
            json={"from": 0, "size": limit, "query": condition}
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")

        data = response.json()
        results = []
        for hit in data.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            if not with_vectors:
                source.pop("vectorData", None)
                source.pop("sparseData", None)
            results.append(source)

        return results

    async def acount_condition(self, condition: dict):
        """异步统计数量"""
        response = await self.arequests.post(
            f"{self.index}/_count",
            json={"query": condition}
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")
        return response.json().get("count", 0)

    async def aquery_page(self, page_num: int, page_size: int, condition: dict,
                          orderkeys: dict = None, with_vectors: bool = True):
        """异步分页查询"""
        from_val = (page_num - 1) * page_size
        query = {
            "from": from_val,
            "size": page_size,
            "query": condition or {"match_all": {}}
        }

        if orderkeys:
            query["sort"] = []
            for field, direction in orderkeys.items():
                query["sort"].append({field: {"order": direction}})

        response = await self.arequests.post(f"{self.index}/_search", json=query)
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")

        data = response.json()
        total = data.get("hits", {}).get("total", 0)
        hits = data.get("hits", {}).get("hits", [])

        results = []
        for hit in hits:
            source = hit.get("_source", {})
            if not with_vectors:
                source.pop("vectorData", None)
                source.pop("sparseData", None)
            results.append(source)

        return {
            "total": total,
            "results": results
        }

    async def aget(self, id_: str, with_vectors: bool = True):
        """异步根据ID获取"""
        response = await self.arequests.get(url=f"{self.index}/_doc/{id_}")
        if response.status_code == 404:
            return None
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")
        source = response.json().get("_source", {})
        if not with_vectors:
            source.pop("vectorData", None)
            source.pop("sparseData", None)
        return source

    async def adelete(self, id_: str):
        """异步删除文档"""
        response = await self.arequests.delete(url=f"{self.index}/_doc/{id_}")
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")
        await self._arefresh()

    async def adelete_condition(self, condition: dict):
        """异步条件删除"""
        response = await self.arequests.post(
            f"{self.index}/_delete_by_query?size=100000",
            json={"query": condition}
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"{response.status_code}:{response.text}")
        await self._arefresh()

    async def _arefresh(self):
        """异步刷新索引"""
        await self.arequests.post(f"{self.index}/_refresh")


# 工具函数
def hash_content(content: str) -> str:
    """生成内容的哈希"""
    import hashlib
    return hashlib.md5(content.encode()).hexdigest()[:16]