"""
天气查询工具 - LangChain Tool
"""
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from typing import Optional
from app.services.search_service import SearchService
import json


class WeatherSearchInput(BaseModel):
    """天气查询输入参数"""
    location: str = Field(description="城市名称，如：北京、上海、成都")

"""
一个方法，搭配 @Tool 注解，这是最简单的工具定义，@Tool 注解本质上是自动生成了一个 BaseTool 的子类；
自己定义类，继承 BaseTool，这种方式更灵活，可以自定义更多的属性和方法，进行更多的控制。
_run()、 _arun() 是 BaseTool 的两个方法，分别用于同步和异步执行工具逻辑，_run() 是必须实现的，_arun() 可以不实现，默认会调用 _run()。
这两种方式在 Agent 眼里都是 BaseTool

拿这些工具来举例，每一个工具内部都要初始化服务【SearchService()、TicketService()、KnowledgeBaseService()】，这些服务通过
自定义类继承 BaseTool 这种方式，可以实现复用，不需要每次都创建对象，而用 @Tool 注解的方式，每次调用工具都会创建一个新的对象，服务也会被重新初始化，效率低。

精细控制输入 schema、错误处理、自定义同步/异步实现，这些都是自定义类继承 BaseTool 这种方式可以实现的，而 @Tool 注解的方式不行。
"""
class WeatherSearchTool(BaseTool):
    """天气查询工具"""
    name: str = "weather_search"
    description: str = """天气查询工具，用于查询城市的天气信息。
    
    使用场景：
    - 用户询问天气情况
    - 用户询问气温、降雨等信息
    
    输入参数：
    - location: 城市名称
    
    示例：
    - "北京天气怎么样？" → location="北京"
    - "上海今天下雨吗？" → location="上海"
    """
    args_schema: type[BaseModel] = WeatherSearchInput
    
    # 使用 PrivateAttr 声明私有属性
    _search_service: Optional[SearchService] = PrivateAttr(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化服务
        self._search_service = SearchService()
    
    def _run(self, location: str) -> str:
        """执行天气查询"""
        try:
            # 确保服务已初始化
            if self._search_service is None:
                self._search_service = SearchService()
            
            # 构建查询
            query = f"{location}天气"
            
            # 调用搜索服务
            result = self._search_service.search(query)
            
            if not result:
                return json.dumps({
                    "success": False,
                    "error": f"未找到 {location} 的天气信息"
                }, ensure_ascii=False)
            
            return json.dumps({
                "success": True,
                "location": location,
                "weather_info": result
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            import traceback
            print(f"[WeatherSearchTool] 错误: {e}")
            print(traceback.format_exc())
            return json.dumps({
                "success": False,
                "error": f"查询失败: {str(e)}"
            }, ensure_ascii=False)
    
    async def _arun(self, location: str) -> str:
        """异步执行（当前使用同步实现）"""
        return self._run(location)
