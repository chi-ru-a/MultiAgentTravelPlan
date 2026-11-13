"""
ReAct Agent 定义 - 使用 LangGraph create_react_agent

每个 Agent 绑定特定工具，由 LLM 驱动工具调用（ReAct 模式）。
Supervisor 决定调用哪个 Agent，Agent 内部自行决定如何使用工具。
"""
import logging
from typing import Dict
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from app.config import settings
from app.agents.tools import get_tool_registry

logger = logging.getLogger(__name__)

# 缓存 Agent 实例，避免重复创建
_agents_cache: Dict[str, object] = {}

# 这是使用 LangChain 的 ChatOpenAI 客户端来调用大模型
def _create_llm() -> ChatOpenAI:
    """创建 LLM 实例（OpenAI 兼容接口，支持 qwen-max 等模型）"""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=True,  # 启用流式，让 stream_mode="messages" 生效
    )


# 每个 Agent 的系统提示词
AGENT_PROMPTS = {
    "ticket_search": (
        "你是智慧出行助手，专门帮用户查询班次信息。\n"
        "用户可能会问火车、高铁、航班等班次。\n"
        "请根据用户的问题调用工具查询，然后用友好的中文回复。\n"
        "如果缺少出发地或目的地，请友好地询问用户。\n"
        "回复时提取关键信息，语气自然，不要照搬 JSON。"
    ),
    "weather_search": (
        "你是天气查询助手，帮用户查询城市天气。\n"
        "请根据用户提到的城市调用工具查询天气。\n"
        "如果用户没有明确城市，请从对话上下文推断或询问。\n"
        "回复时用简洁友好的中文描述天气情况。"
    ),
    "kb_search": (
        "你是出行知识库助手，帮用户解答退票、改签、票价规则等问题。\n"
        "请调用知识库工具检索相关信息，然后用通俗易懂的中文回复。\n"
        "如果检索结果不够准确，请如实告知用户。"
    ),
    "chitchat": (
        "你是智能旅行助手，负责友好地与用户闲聊。\n"
        "你可以帮用户查询班次、天气、出行规则等。\n"
        "回复简短友好，不超过100字，不使用 markdown 格式。"
    ),
}


def create_worker_agents() -> Dict[str, object]:
    """
    从工具注册中心动态创建所有 ReAct Agent

    每个 Agent 是一个编译后的 LangGraph 子图，可以直接作为节点添加到主图。

    Returns:
        Dict[str, CompiledGraph]: {tool_name: compiled_agent}
    """
    global _agents_cache
    if _agents_cache:
        logger.debug("使用缓存的 Agent 实例")
        return _agents_cache

    registry = get_tool_registry()
    llm = _create_llm()
    agents = {}

    for tool_name, tool_config in registry.get_all().items():  # 得到所有注册的工具并遍历
        tool_instance = registry.get_tool_instance(tool_name)  # 根据工具名获取工具实例
        # 根据工具名获取系统提示词，如果没有定义，则使用默认提示词  get(key, default)
        prompt = AGENT_PROMPTS.get(tool_name, f"你是{tool_config.display_name}助手，请帮助用户完成任务。")

        # 每个工具注册为一个 ReAct Agent【就是一个创建并编译好的状态图StateGraph】
        agent = create_react_agent(
            model=llm,  # 绑定 LLM
            tools=[tool_instance],  # 绑定工具
            name=tool_name,  # agent 名称，和方法名同名
            prompt=prompt,  # 绑定系统提示词
        )
        # 缓存 Agent 实例，避免重复创建；key 是 Agent 名，value 是编译后的 Agent
        # _agents_cache = agents
        agents[tool_name] = agent
        logger.info(f"创建 ReAct Agent: {tool_name} ({tool_config.display_name})")

    _agents_cache = agents
    logger.info(f"共创建 {len(agents)} 个 ReAct Agent")
    return agents
