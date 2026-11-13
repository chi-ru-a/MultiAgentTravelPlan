"""
LangChain Tools - 工具层
"""
from .registry import get_tool_registry, register_tool
from .ticket_tool import TicketSearchTool
from .kb_tool import KnowledgeBaseTool
from .weather_tool import WeatherSearchTool
from .chitchat_tool import ChitchatTool

# 自动注册所有工具
def _register_all_tools():
    """自动注册所有工具"""
    registry = get_tool_registry()
    
    # 注册闲聊工具（最高优先级）
    registry.register(
        name="chitchat",
        display_name="闲聊",
        description="闲聊：问候、感谢、一般对话",
        keywords=["你好", "嗨", "您好", "谢谢", "多谢", "感谢", "再见", "拜拜", "你是谁", "介绍一下", "早上好", "晚上好", "中午好"],
        tool_class=ChitchatTool,
        priority=1,
        requires_params=False
    )
    
    # 注册班次查询工具
    registry.register(
        name="ticket_search",
        display_name="智慧出行",
        description="班次查询：查询车次、班次、出行计划",
        keywords=["火车", "班次", "车票", "车次", "出发", "到达", "行程", "买票", "订票", "高铁", "飞机", "航班"],
        tool_class=TicketSearchTool,
        priority=2,
        requires_params=True,
        required_params=["departure", "destination"],
        context_field="ticket_context",
        context_description="用户查询了从 {departure} 到 {destination} 的班次"
    )

    # 注册天气查询工具
    registry.register(
        name="weather_search",
        display_name="天气",
        description="天气查询：查询天气信息",
        keywords=["天气", "温度", "气温", "下雨", "晴天", "阴天", "多云", "降雨"],
        tool_class=WeatherSearchTool,
        priority=2,
        requires_params=True,
        required_params=["location"],
        context_field="weather_context",
        context_description="用户查询了 {location} 的天气"
    )

    # 注册知识库工具（最低优先级）
    registry.register(
        name="kb_search",
        display_name="知识库",
        description="知识库：退票改签规则、业务咨询",
        keywords=["退票", "改签", "手续费", "票价", "规则", "政策", "规定", "儿童票", "学生票", "优惠", "补票"],
        tool_class=KnowledgeBaseTool,
        priority=3,
        requires_params=False,
        context_field="consultation_context",
        context_description="用户咨询了出行规则"
    )

# 自动注册
_register_all_tools()

__all__ = [
    "TicketSearchTool",
    "KnowledgeBaseTool",
    "WeatherSearchTool",
    "ChitchatTool",
    "get_tool_registry",
]
