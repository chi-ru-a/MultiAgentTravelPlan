"""
知识库检索工具 - LangChain Tool
"""
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from typing import Type, Optional
from app.services.kb_service import KnowledgeBaseService
import json


class KnowledgeBaseInput(BaseModel):
    """知识库检索输入参数"""
    query: str = Field(description="用户的问题或查询内容")


class KnowledgeBaseTool(BaseTool):
    """知识库检索工具"""
    name: str = "kb_search"
    description: str = """知识库检索工具，用于查询业务规则、政策、常见问题等。
    
    使用场景：
    - 用户询问退票、改签规则
    - 用户询问票价政策、优惠信息
    - 用户询问手续费、补票等业务问题
    - 用户进行一般性咨询
    
    输入参数：
    - query: 用户的问题
    
    示例：
    - "退票需要手续费吗？"
    - "儿童票怎么购买？"
    - "改签有什么规定？"
    """
    args_schema: Type[BaseModel] = KnowledgeBaseInput
    
    # 使用 PrivateAttr 声明私有属性
    _kb_service: Optional[KnowledgeBaseService] = PrivateAttr(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化服务
        self._kb_service = KnowledgeBaseService()
    
    def _run(self, query: str) -> str:
        """执行知识库检索"""
        try:
            # 确保服务已初始化
            if self._kb_service is None:
                self._kb_service = KnowledgeBaseService()
            
            # 检索知识库
            results = self._kb_service.search(query, top_k=5)
            
            if not results:  # 未检索到也有兜底数据返回
                return json.dumps({
                    "success": True,
                    "count": 0,
                    "message": "未找到相关信息",
                    "suggestion": "建议拨打客服热线400-XXX-XXXX进行咨询"
                }, ensure_ascii=False)
            
            # 格式化结果
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append({
                    "序号": i,
                    "内容": result.get('content', ''),
                    "相关度": result.get('score', 0)
                })
            
            return json.dumps({
                "success": True,
                "count": len(results),
                "query": query,
                "results": formatted_results
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:  # 检索过程中出现异常，返回检索失败和对应的错误信息
            import traceback
            print(f"[KnowledgeBaseTool] 错误: {e}")
            print(traceback.format_exc())
            return json.dumps({
                "success": False,
                "error": f"检索失败: {str(e)}"
            }, ensure_ascii=False)
    
    async def _arun(self, query: str) -> str:
        """异步执行（当前使用同步实现）"""
        return self._run(query)
