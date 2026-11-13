"""
Supervisor Node - 任务分解和路由（LangGraph 最佳实践版本）

使用 get_stream_writer() 推送思考链事件，
保留关键词 + LLM 双层路由策略。
"""
import asyncio
import logging
from app.graph.state import AgentState
from app.config import settings
from app.agents.tools import get_tool_registry
from app.utils.message_helpers import get_latest_user_message, get_writer
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


async def supervisor_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Supervisor 节点：分析用户意图，决定调用哪些 Agent

    通过 stream writer 推送思考链事件到 SSE 流。
    接收 config 参数以兼容 Python 3.10（contextvars 不传播问题）。
    返回 next_agents 列表，由工作流路由函数决定单任务/并行执行。
    """
    writer = get_writer(config)
    messages = state["messages"]

    # 获取最新用户消息
    user_message = get_latest_user_message(messages)
    if not user_message:
        return {
            "next_agents": [],
            "final_response": "未收到有效消息",
            "needs_user_input": False
        }

    logger.info(f"Supervisor 开始分析: {user_message[:50]}...")

    # 推送思考事件
    writer({"type": "thinking_stream", "block": {
        "content": "💭 分析用户意图...",
        "agent": "supervisor",
        "agent_display": "规划",
        "is_streaming": True
    }})

    # 分析任务（关键词 + LLM 双层路由，阻塞调用放到线程中）
    decision = await asyncio.to_thread(_analyze_task, user_message, messages, state)
    logger.info(f"Supervisor 决策: mode={decision.get('mode')}, agents={[st['agent'] for st in decision.get('subtasks', [])]}")

    # 推送推理结果
    if decision.get("reasoning"):
        writer({"type": "thinking_stream", "block": {
            "content": f"✓ {decision['reasoning']}",
            "agent": "supervisor",
            "agent_display": "规划",
            "is_streaming": False
        }})

    # 构建执行计划
    subtasks = decision.get("subtasks", [])
    agent_names = [st["agent"] for st in subtasks]

    # 推送执行计划
    registry = get_tool_registry()
    all_tools = registry.get_all()
    if len(agent_names) > 1:
        tool_displays = [all_tools[n].display_name for n in agent_names if n in all_tools]
        mode_text = {"parallel": "并行", "sequential": "顺序"}.get(decision.get("mode", ""), "")
        writer({"type": "thinking_stream", "block": {
            "content": f"🎯 {mode_text}执行 {len(agent_names)} 个任务：{', '.join(tool_displays)}",
            "agent": "supervisor",
            "agent_display": "规划",
            "is_streaming": False
        }})
    elif agent_names:
        display = all_tools.get(agent_names[0], None)
        display_name = display.display_name if display else agent_names[0]
        writer({"type": "thinking_stream", "block": {
            "content": f"🎯 执行：{display_name}",
            "agent": "supervisor",
            "agent_display": "规划",
            "is_streaming": False
        }})

    # 动态更新上下文（根据工具注册的 context_field 映射）
    context_updates = {}
    for subtask in subtasks:
        agent_name = subtask["agent"]
        params = subtask.get("params", {})
        tool_config = all_tools.get(agent_name)
        if tool_config and tool_config.context_field and params:
            ctx = state.get(tool_config.context_field, {})
            ctx.update(params)
            context_updates[tool_config.context_field] = ctx

    return {
        "thoughts": [],  # 思考通过 writer 推送，不再通过 state
        "next_agents": agent_names,
        "subtasks": subtasks,
        "collaboration_mode": decision.get("mode", "single"),
        "agent_outputs": [],  # 初始化为空列表（触发 _reset_on_empty reducer 清除上轮结果）
        **context_updates,
    }


def _analyze_task(query: str, messages: list, state: AgentState = None) -> dict:
    """
    分析任务，决定调用哪些工具

    双层路由策略：
    1. 关键词快速匹配（O(n)，无 LLM 调用）
    2. LLM 精确判断（仅在多工具同优先级或无匹配时触发）
    """
    registry = get_tool_registry()
    all_tools = registry.get_all()

    logger.debug(f"已注册工具: {list(all_tools.keys())}")

    # 第一层：关键词快速匹配
    matched_tools = registry.match_by_keywords(query)
    logger.debug(f"关键词匹配结果: {matched_tools}")

    if matched_tools:
        # 只有一个工具匹配 → 直接选择
        if len(matched_tools) == 1:
            tool_name = matched_tools[0][0]
            tool_config = all_tools[tool_name]
            return {
                "mode": "single",
                "parallel": False,
                "subtasks": [{"agent": tool_name, "task": tool_config.description, "params": {}}],
                "reasoning": f"识别到{tool_config.description}需求",
                "plan": tool_config.description
            }

        # 多工具匹配，第一个优先级明显更高 → 选择最高优先级
        if matched_tools[0][1] < matched_tools[1][1]:
            tool_name = matched_tools[0][0]
            tool_config = all_tools[tool_name]
            return {
                "mode": "single",
                "parallel": False,
                "subtasks": [{"agent": tool_name, "task": tool_config.description, "params": {}}],
                "reasoning": f"识别到{tool_config.description}需求",
                "plan": tool_config.description
            }

        # 多工具同优先级 → 使用 LLM 判断是否并行
        same_priority_tools = [t for t in matched_tools if t[1] == matched_tools[0][1]]
        if len(same_priority_tools) > 1:
            logger.info(f"检测到 {len(same_priority_tools)} 个同优先级工具，使用 LLM 判断")
            return _analyze_with_llm(query, messages, all_tools, matched_tools=same_priority_tools, state=state)

    # 无匹配 → 使用 LLM 分析
    logger.info("无关键词匹配，使用 LLM 分析")
    return _analyze_with_llm(query, messages, all_tools, state=state)


def _analyze_with_llm(query: str, messages: list, available_tools: dict,
                      matched_tools: list = None, state: AgentState = None) -> dict:
    """使用 LLM 分析任务（第二层路由）"""
    from app.utils.llm_helper import call_llm

    # 构建工具描述
    tools_desc = "\n".join([
        f"- {name}: {config.description}"
        for name, config in available_tools.items()
    ])

    # 关键词匹配提示
    hint_text = ""
    if matched_tools:
        matched_names = [t[0] for t in matched_tools]
        hint_text = f"\n\n# 关键词匹配结果\n检测到以下工具的关键词: {', '.join(matched_names)}\n请判断是否需要同时使用这些工具。"

    # 工具选择规则
    tool_rules = []
    for name, config in available_tools.items():
        examples = ", ".join([f'"{kw}"' for kw in config.keywords[:3]])
        tool_rules.append(f"{config.priority}. **{name}（{config.display_name}）**：{config.description}")
        tool_rules.append(f"   - 示例：{examples}")

    tools_rules_text = "\n".join(tool_rules)
    tool_names = "/".join(available_tools.keys())

    # 对话上下文（最近 5 条）
    context_messages = []
    for msg in messages[-5:]:
        if isinstance(msg, HumanMessage):
            context_messages.append(f"user: {msg.content}")
        elif isinstance(msg, AIMessage):
            context_messages.append(f"assistant: {msg.content}")
    context_text = "\n".join(context_messages)

    # 动态构建上下文信息（根据工具注册的 context_field + context_description）
    context_info = ""
    if state:
        context_parts = []
        for name, config in available_tools.items():
            if config.context_field and config.context_description:
                ctx = state.get(config.context_field, {})
                if any(v for v in ctx.values() if v):  # 有非空值时才构建描述
                    try:
                        # 用上下文数据填充模板，缺失字段用 "?" 替代
                        filled = config.context_description.format_map(
                            {k: v or "?" for k, v in ctx.items()}
                        )
                        context_parts.append(f"- {filled}")
                    except (KeyError, IndexError):
                        pass
        if context_parts:
            context_info = "\n\n# 上下文信息\n" + "\n".join(context_parts)

    # 兜底工具
    default_tool = min(available_tools.items(), key=lambda x: x[1].priority)[0]

    # 动态构建 params 示例（从各工具的 required_params 聚合）
    all_params = {}
    for name, config in available_tools.items():
        for p in config.required_params:
            if p not in all_params:
                all_params[p] = p  # 占位
    params_example = ", ".join([f'"{k}": "值"' for k in all_params]) if all_params else '"key": "value"'

    prompt = f"""你是任务规划专家，负责分析用户查询并选择合适的工具。

# 可用工具
{tools_desc}

# 工具选择规则
{tools_rules_text}
{hint_text}

# 对话历史
{context_text}{context_info}

# 当前查询
{query}

# 判断规则
1. 根据关键词匹配对应工具
2. 优先选择优先级高的工具
3. **如果查询包含多个独立任务，使用 parallel 模式**
4. **注意上下文引用**：如"目的地天气"应提取目的地城市作为 location
5. 兜底：无法判断时使用 {default_tool}

# 输出格式（严格 JSON）
{{
    "mode": "single" | "parallel",
    "subtasks": [
        {{
            "agent": "{tool_names}",
            "task": "任务描述",
            "params": {{{params_example}}}
        }}
    ],
    "reasoning": "推理过程（不超过20字）",
    "plan": "任务规划描述"
}}

只返回 JSON。"""

    return call_llm(
        prompt=prompt,
        model=settings.LLM_MODEL,
        temperature=0.1,
        context="任务规划分析",
        parse_json=True,
        default_response=_default_decision()
    )


def _default_decision() -> dict:
    """默认决策（兜底）"""
    registry = get_tool_registry()
    all_tools = registry.get_all()

    if all_tools:
        default_tool = min(all_tools.items(), key=lambda x: x[1].priority)
        tool_name, tool_config = default_tool
        return {
            "mode": "single",
            "subtasks": [{"agent": tool_name, "task": tool_config.description, "params": {}}],
            "reasoning": f"转入{tool_config.display_name}兜底",
            "plan": tool_config.description
        }

    return {
        "mode": "single",
        "subtasks": [{"agent": "end", "task": "无可用工具", "params": {}}],
        "reasoning": "无可用工具",
        "plan": "无可用工具"
    }
