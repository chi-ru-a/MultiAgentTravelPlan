"""
LangGraph Workflow - 多 Agent 协作工作流（最佳实践版本）

核心特性：
- Send API 实现并行 fan-out/fan-in
- create_react_agent 子图作为 Worker Agent
- get_stream_writer() 推送自定义流事件
- MemorySaver checkpointer 实现会话持久化
- Annotated reducer 支持并行安全聚合
- 单 Agent 场景：astream_events 逐 token 流式输出
- 多 Agent 场景：ainvoke 收集结果，synthesizer 流式汇总
"""
import logging
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from app.utils.message_helpers import get_writer

from app.graph.state import AgentState
from app.graph.agents import create_worker_agents
from app.agents.nodes.supervisor import supervisor_node
from app.agents.nodes.synthesizer import synthesizer_node
from app.agents.tools import get_tool_registry

logger = logging.getLogger(__name__)


# ===== Agent 包装节点 =====
# Agent 节点的定义；supervisor_node、synthesizer_node 在 agents/nodes 里定义
def _make_agent_node(agent_name: str, compiled_agent):
    """
    创建 Agent 包装节点函数

    包装 create_react_agent 子图，负责：
    1. 通过 get_stream_writer() 推送执行进度事件
    2. 单 Agent 模式：astream_events 逐 token 流式输出到前端
    3. 多 Agent 模式：ainvoke 收集完整结果供 synthesizer 汇总
    4. 构建 AgentOutput 写入 agent_outputs（reducer 聚合）
    """

    # 封装一个 Agent 为节点，之所以封装，是为了在使用 Agent 时【在它的前后】，插入自己的逻辑，比如推送进度事件、流式输出、异常处理、结果提取等
    # AgentState：工作流主图节点之间的共享状态、RunnableConfig 运行图的配置；节点的输入都是这俩东西
    async def node_fn(state: AgentState, config: RunnableConfig) -> dict:
        # stream_writer = runtime.stream_writer
        # stream_writer(f"正在查询 {city} 今天的天气...")
        # 这里的 writer 就是 stream_writer，因此，底下的 writer() 包裹的那块东西就是流式输出的
        writer = get_writer(config)  # 拿到流式输出的调用函数

        # 从注册中心获取 display_name【展示名，给前端看的】
        registry = get_tool_registry()
        tool_config = registry.get_all().get(agent_name)
        display_name = tool_config.display_name if tool_config else agent_name

        # 判断是否为单 Agent 模式（可直接流式输出到前端）
        is_single_agent = len(state.get("next_agents", [])) == 1

        # 推送开始事件
        writer({"type": "thinking_stream", "block": {
            "content": f"🔄 {display_name}处理中...",
            "agent": agent_name,
            "agent_display": display_name,
            "is_streaming": True
        }})

        try:
            if is_single_agent:
                # 单 Agent：astream_events 逐 token 流式输出
                response_text = await _stream_agent(
                    compiled_agent, state, writer, agent_name, display_name
                )
            else:
                # 多 Agent：ainvoke 收集完整结果（由 synthesizer 流式汇总）
                result = await compiled_agent.ainvoke({"messages": state["messages"]})
                response_text = _extract_response(result)

            logger.info(f"Agent {agent_name} 执行完成，响应长度: {len(response_text)}")

            # 推送完成事件【这个 Agent 完成了】
            writer({"type": "thinking_stream", "block": {
                "content": f"✓ {display_name}完成",
                "agent": agent_name,
                "agent_display": display_name,
                "is_streaming": False
            }})

            return {
                "messages": [AIMessage(content=response_text, name=agent_name)],
                "agent_outputs": [{
                    "agent_name": agent_name,
                    "display_name": display_name,
                    "success": True,
                    "response": response_text,
                    "data": {}
                }],
            }

        except Exception as e:
            logger.error(f"Agent {agent_name} 执行失败: {e}", exc_info=True)
            error_msg = f"抱歉，{display_name}执行出错了。"

            # 推送错误事件
            writer({"type": "thinking_stream", "block": {
                "content": f"⚠ {display_name}执行失败: {str(e)[:50]}",
                "agent": agent_name,
                "agent_display": display_name,
                "is_streaming": False
            }})

            return {
                "messages": [AIMessage(content=error_msg, name=agent_name)],
                "agent_outputs": [{
                    "agent_name": agent_name,
                    "display_name": display_name,
                    "success": False,
                    "response": error_msg,
                    "data": {"error": str(e)}
                }],
            }


    # 设置函数名，便于调试和日志
    # 在 Python 中，函数也是对象，__name__是它的名字属性，默认就是函数名
    # 每个 Agent 都要使用 node_fn 进行封装，因此需要给它们不同的名字，否则日志里都是 node_fn，无法区分
    node_fn.__name__ = f"{agent_name}_node"
    return node_fn  # 这里不是调用 node_fn，而是把 node_fn 这个函数返回


async def _stream_agent(compiled_agent, state, writer, agent_name, display_name):
    """
    流式获取 ReAct Agent 的 LLM token 并逐个推送到前端

    通过 astream_events 捕获子图内部的 LLM 流式输出，
    过滤掉工具调用消息（tool_call_chunks），只输出最终回复的 token。
    """
    response_text = ""

    try: 
        # 两套 API 返回的迭代器，在此进行遍历
        async for event in compiled_agent.astream_events(  # stream/astream、astream_events，这是 LangGraph 提供的两套流式输出 API
            {"messages": state["messages"]}, version="v2"  # 事件格式的版本，v2 结构更清晰
        ):
            # event 当中有哪些字段，需要查询 LangChain 文档，这不是自定义的
            # name【产生这个事件的 Runnable 的名称】、data【事件相关的数据，内容随事件类型变化】
            # event【事件类型，格式固定为 on_[类型]_(start/stream/end)】，还有其他的字段
            if event["event"] == "on_chat_model_stream":  # LLM 流式输出事件，过滤掉工具调用消息，只输出最终回复的 token
                chunk = event["data"]["chunk"]  # 取出 chunk 的文本内容
                content = chunk.content or ""
                # 只输出非工具调用的内容 token   ReAct Agent 在决定调用工具时，LLM 输出的 chunk 里可能带 tool_call_chunks（工具调用的结构化数据），这些不是给用户看的正文。如果不过滤，前端会看到一堆工具调用的 JSON 碎片混在回答里
                if content and not getattr(chunk, "tool_call_chunks", []):
                    response_text += content
                    writer({"type": "content_stream", "block": {
                        "delta": content,
                        "accumulated": response_text,
                        "agent": agent_name,
                        "agent_display": display_name,
                    }})
    except Exception as e:  # 流式输出是有兜底策略的，出错会走阻塞式输出
        logger.warning(f"Agent {agent_name} 流式输出降级为 ainvoke: {e}")
        # 降级：使用 ainvoke 获取完整结果
        result = await compiled_agent.ainvoke({"messages": state["messages"]})  # state["messages"]，共享状态中的消息历史
        response_text = _extract_response(result)  # 再提取模型的响应内容
        if response_text:
            writer({"type": "content_stream", "block": {
                "delta": response_text,
                "accumulated": response_text,
                "agent": agent_name,
                "agent_display": display_name,
            }})

    return response_text


# 提取模型响应内容
def _extract_response(result: dict) -> str:
    """从 ReAct Agent 的 ainvoke 结果中提取最后一条有效 AI 消息"""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            # hasattr(msg, "tool_calls")，判断 msg 是否有 tool_calls 属性
            # msg.tool_calls，tool_calls 是工具调用列表，因此是真的要调用工具
            # not msg.content.strip()，msg.content 是模型输出的内容，strip() 去掉左右的空白，如果为空，说明模型没有输出任何内容
            # 跳过纯工具调用，没有任何内容输出的消息
            # 有工具调用，也有内容输出，是不会跳过的，而是会把模型内容返回
            # 比如模型说，"我要调用工具 X"，那 AIMessage 里就有 tool_calls，也有 content，content 里可能是 "我要调用工具 X"，那就会返回这个内容
            if not (hasattr(msg, "tool_calls") and msg.tool_calls and not msg.content.strip()):
                return msg.content
    return ""






# ===== 路由函数 =====
# 用于给 Supervisor 节点添加条件边，根据 next_agents 列表动态路由到一个或多个 Agent 节点
def route_after_supervisor(state: AgentState):
    """
    Supervisor 后的路由逻辑

    - 无任务 → END
    - 单任务 → 直接路由到对应 Agent
    - 多任务 → 返回 Send 对象列表实现并行 fan-out
    """
    next_agents = state.get("next_agents", [])  # 字典.get(key, default) 避免 key 不存在报错

    if not next_agents:
        logger.info("无需执行 Agent，直接结束")
        return END

    if len(next_agents) == 1:
        logger.info(f"单任务路由: {next_agents[0]}")
        return next_agents[0]

    # 多任务：使用 Send API 并行 fan-out
    logger.info(f"并行 fan-out: {next_agents}")
    return [Send(agent, state) for agent in next_agents]


# ===== 工作流构建 =====
# 封装创建 StateGraph 的过程；初始化、定义节点【节点的定义不在这做】、添加节点和边
def create_workflow() -> StateGraph:
    """
    创建 LangGraph 工作流

    工作流结构：
    START → Supervisor → [Agent1, Agent2...] → Synthesizer → END
                                ↑ Send 并行 fan-out
                                ↓ Reducer fan-in 聚合
    """
    # 创建 ReAct Agent 实例【每个工具是一个 ReAct Agent】
    agents = create_worker_agents()
    logger.info(f"创建工作流，共 {len(agents)} 个 Agent: {list(agents.keys())}")

    # 创建工作流主图  StateGraph(state_schema=xx, input_schema=xx, output_schema=xx) 共享状态、输入状态、输出状态
    workflow = StateGraph(AgentState)  # 整张图的共享状态 AgentState

    # 添加节点
    workflow.add_node("supervisor", supervisor_node)
    for name, compiled_agent in agents.items():  # 遍历创建好的 ReAct Agent【也是状态图、子图】
        wrapper = _make_agent_node(name, compiled_agent)  # 拿到包装这个 Agent 为节点的函数
        # 这里是把 node_fn 这个函数注册为节点，而不是调用 node_fn 这个函数；
        # 工作流走到这个节点，才会调用 node_fn 这个函数，执行 Agent 的逻辑
        workflow.add_node(name, wrapper)
    workflow.add_node("synthesizer", synthesizer_node)  # 合并多 Agent 结果的汇总节点

    # 设置入口点
    workflow.set_entry_point("supervisor")

    # Supervisor → 条件路由（支持单 Agent 直达和 Send 并行）
    route_map = {name: name for name in agents.keys()}
    route_map[END] = END
    # 条件边   add_conditional_edges(source, path, path_map)    起点、路由函数、路由结果到实际节点名的映射
    # supervisor 动态路由到一个或多个 Agent 节点
    workflow.add_conditional_edges("supervisor", route_after_supervisor, route_map)

    # 所有 Agent → Synthesizer（Synthesizer 内部判断是否需要汇总）
    for name in agents.keys():
        workflow.add_edge(name, "synthesizer")  # 工作 Agent 到 synthesizer 的边

    # Synthesizer → END
    workflow.add_edge("synthesizer", END)  # synthesizer 到 END 的边

    return workflow


# 先调用 create_workflow 创建状态图，再调用 compile 编译状态图；
# 先定义状态、再创建状态图（初始化、定义节点、添加节点和边）、再编译，之后就可以使用这个状态图了【工作流、Agent】
def compile_workflow():
    """
    编译工作流（带 MemorySaver checkpointer）

    MemorySaver 提供会话持久化：
    - messages 通过 add_messages reducer 自动管理对话历史
    - agent_outputs 通过 _reset_on_empty reducer 每轮自动重置
    - 通过 config={"configurable": {"thread_id": session_id}} 区分会话
    """
    logger.info("开始编译 LangGraph 工作流")

    # 检查工具注册情况
    registry = get_tool_registry()
    all_tools = registry.get_all()  # 获取到所有的工具 all_tools
    for name, config in all_tools.items():
        logger.info(f"  已注册工具: {name} ({config.display_name}, 优先级={config.priority})")

    workflow = create_workflow()
    checkpointer = MemorySaver()  # 就是 InMemorySaver，记忆保存在内存当中
    # 编译时通过 checkpointer 指定检查点存储器【State 持久化机制】
    # 调用图时传入带有 thread_id 的 config
    compiled = workflow.compile(checkpointer=checkpointer)

    logger.info("工作流编译成功")
    return compiled
