"""
工具注册中心 - 统一管理所有工具
"""
import logging
from typing import Dict, List, Type, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 这是一个工具配置的 Pydantic 数据模型
class ToolConfig(BaseModel):
    """工具配置"""
    name: str  # 工具名
    display_name: str
    description: str  # 工具描述
    keywords: List[str]  # 关键词列表，基于关键词匹配工具
    priority: int = 3  # 优先级：1=最高，3=最低
    tool_class: Type[BaseTool]  # 工具类，可以用于获取工具实例 config.tool_class()
    requires_params: bool = False  # 是否需要参数提取
    required_params: List[str] = []  # 必需参数列表（如 ["departure", "destination"]）
    # 上下文映射（用于 Supervisor 动态更新 AgentState 中的上下文字段）
    context_field: Optional[str] = None  # AgentState 中对应的字段名，如 "ticket_context"
    context_description: Optional[str] = None  # 上下文描述模板，如 "查询了从 {departure} 到 {destination} 的班次"


class ToolRegistry:
    """工具注册中心"""


    # __new__() 创建对象，__init__() 初始化对象
    # __init__() 只会执行一次、可以不写、没有返回值(不能 return)
    def __init__(self):
        # _tools，对象的属性，字典，key 是 str，value 是 ToolConfig 对象，默认为{}
        # 注册的工具
        self._tools: Dict[str, ToolConfig] = {}


    # 注册工具  放到 _tools 字典中，key 是工具名，value 是 ToolConfig 对象
    def register(
        self,
        name: str,
        display_name: str,
        description: str,
        keywords: List[str],
        tool_class: Type[BaseTool],
        priority: int = 3,
        requires_params: bool = False,
        required_params: List[str] = None,
        context_field: Optional[str] = None,
        context_description: Optional[str] = None
    ):
        """注册工具"""
        config = ToolConfig(
            name=name,
            display_name=display_name,
            description=description,
            keywords=keywords,
            priority=priority,
            tool_class=tool_class,
            requires_params=requires_params,
            required_params=required_params or [],
            context_field=context_field,
            context_description=context_description
        )
        self._tools[name] = config
        logger.info(f"注册工具: {name} ({display_name})")

    # 获取工具配置，【ToolConfig】，_tools 的 key 是工具名，value 是 ToolConfig 对象
    def get(self, name: str) -> ToolConfig:
        """获取工具配置"""
        return self._tools.get(name)

    # 获取所有工具，_tools【工具名及其配置】
    def get_all(self) -> Dict[str, ToolConfig]:
        """获取所有工具"""
        return self._tools

    # 获取工具实例，具体的工具【BaseTool】
    def get_tool_instance(self, name: str) -> BaseTool:
        """获取工具实例"""
        config = self.get(name)  # 工具配置 ToolConfig
        if not config:
            raise ValueError(f"工具 {name} 未注册")
        # tool_class: Type[BaseTool]
        # tool_class 是 ToolConfig 的一个属性，这个属性的类型是 BaseTool(或其子类)，也就是工具的类，而不是实例
        # config.tool_class() 是调用这个类的构造函数，返回一个工具实例
        return config.tool_class()

    # 根据关键词匹配工具，返回的是工具名和工具优先级
    def match_by_keywords(self, query: str) -> List[tuple[str, int]]:
        """
        根据关键词匹配工具
        
        Returns:
            List[tuple[tool_name, priority]]: 匹配的工具及其优先级
        """
        logger.debug(f"关键词匹配查询: '{query}'")
        matched = {}
        for name, config in self._tools.items():
            for keyword in config.keywords:
                if keyword in query:
                    logger.debug(f"匹配到: {name} (关键词: '{keyword}')")
                    matched[name] = config.priority
                    break

        # 按优先级排序（数字越小优先级越高）
        sorted_result = sorted(matched.items(), key=lambda x: x[1])
        logger.debug(f"匹配结果: {sorted_result}")
        return sorted_result


# 全局工具注册中心实例  有 _tools 属性和一些方法
_registry = ToolRegistry()


# 获取全局工具注册中心实例  _registry
def get_tool_registry() -> ToolRegistry:
    """获取工具注册中心实例"""
    return _registry

# 一个自定义的装饰器，类似 Java 的注解，但 Python 的装饰器没有任何特殊的关键字、语法啥的
# 任何可以调用的对象都可以作为装饰器，比如函数、类、类的实例、可调用对象等
def register_tool(
    name: str,
    display_name: str,
    description: str,
    keywords: List[str],
    tool_class: Type[BaseTool],
    priority: int = 3,
    requires_params: bool = False
):
    """注册工具的装饰器"""
    _registry.register(
        name=name,
        display_name=display_name,
        description=description,
        keywords=keywords,
        tool_class=tool_class,
        priority=priority,
        requires_params=requires_params
    )
    return tool_class
