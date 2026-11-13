"""
联网搜索服务 - 使用智谱AI搜索引擎
"""
from zhipuai import ZhipuAI
from app.config import settings


# 使用智谱AI搜索引擎
class SearchService:
    """联网搜索服务"""

    # 搜索引擎选项
    # search_std: 智谱基础版搜索引擎
    # search_pro: 智谱高阶版搜索引擎
    # search_pro_sogou: 搜狗
    # search_pro_quark: 夸克搜索
    SEARCH_ENGINE = "search_std"

    def __init__(self):
        """初始化智谱AI客户端"""
        self.client = ZhipuAI(api_key=settings.ZHIPU_API_KEY)

    # 这个方法返回一个字符串，是搜索结果的摘要信息，适合直接展示给用户
    def search(self, query: str, result_rows: int = 3) -> str:
        """
        联网搜索

        Args:
            query: 搜索查询
            result_rows: 返回结果数量，范围1-50，默认3

        Returns:
            搜索结果摘要
        """
        try:
            response = self.client.web_search.web_search(
                search_engine=self.SEARCH_ENGINE,
                search_query=query,
                count=result_rows,
                search_domain_filter="",  # 只访问指定域名的内容
                search_recency_filter="noLimit",  # 搜索指定日期范围内的内容
                content_size="high"  # 搜索结果内容大小，默认medium
            )

            print(f"[Zhipu搜索] 查询: {query}, 结果数: {len(response.search_result)}")

            if not response.search_result:
                return "抱歉，没有找到相关信息。"

            # 格式化搜索结果
            result_parts = []
            for i, item in enumerate(response.search_result, 1):
                result_parts.append(f"{i}. {item.title}")
                result_parts.append(f"   {item.content}")
                result_parts.append("")

            return "\n".join(result_parts)

        except Exception as e:
            print(f"Zhipu搜索失败: {e}")
            return self._get_mock_data(query)

    # 这个方法返回一个列表，每个元素是一个字典，包含 content, link, title, icon 等字段，适合进一步处理或展示
    def search_raw(self, query: str, result_rows: int = 5) -> list:
        """
        获取原始搜索结果（结构化数据）

        Args:
            query: 搜索查询
            result_rows: 返回结果数量

        Returns:
            搜索结果列表，每项包含 content, link, title, icon
        """
        try:
            response = self.client.web_search.web_search(
                search_engine=self.SEARCH_ENGINE,
                search_query=query,
                count=result_rows,
                search_domain_filter="",
                search_recency_filter="noLimit",
                content_size="high"
            )

            result = []
            for item in response.search_result:
                result.append({
                    "content": item.content,
                    "link": item.link,
                    "title": item.title,
                    "icon": item.icon,
                })
            return result

        except Exception as e:
            print(f"Zhipu原始搜索失败: {e}")
            return []

    # 兜底的 mock 数据
    def _get_mock_data(self, query: str) -> str:
        """模拟数据（搜索失败时备用）"""
        from datetime import datetime, timedelta

        # 简单的天气模拟
        cities = {
            "上海": "多云，气温12-20℃，东南风3-4级",
            "北京": "晴，气温5-15℃，北风2-3级",
            "深圳": "晴，气温20-28℃，微风",
            "杭州": "小雨，气温10-18℃，东风3-4级",
            "广州": "多云，气温22-30℃，微风"
        }

        for city in cities:
            if city in query:
                return f"[模拟数据] {city}{cities[city]}。"

        return "抱歉，搜索服务暂时不可用，请稍后再试。"