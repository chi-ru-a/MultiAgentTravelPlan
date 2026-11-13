"""
Synthesizer Node - 多 Agent 结果汇总（LangGraph 最佳实践版本）

使用 get_stream_writer() 推送汇总思考事件，
从 agent_outputs（_reset_on_empty reducer 聚合列表）读取结果。
"""
import logging
from app.graph.state import AgentState
from app.agents.tools import get_tool_registry
from app.utils.message_helpers import get_latest_user_message
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from app.utils.message_helpers import get_writer

logger = logging.getLogger(__name__)


async def synthesizer_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    汇总多个 Agent 的执行结果，生成统一回复

    接收 config 参数以兼容 Python 3.10（contextvars 不传播问题）。
    从 agent_outputs 读取各 Agent 结果。

    行为：
    - 0 个结果 → 返回空
    - 1 个结果 → 透传，设置 final_response
    - 多个结果 → LLM 汇总，设置 final_response
    """
    writer = get_writer(config)
    agent_outputs = state.get("agent_outputs", [])

    # 无结果
    if not agent_outputs:
        logger.debug("无 Agent 结果")
        return {}

    # 单 Agent 结果 → 直接透传（Agent wrapper 已流式推送 content_stream）
    if len(agent_outputs) == 1:
        response = agent_outputs[0].get("response", "")
        logger.debug(f"单 Agent 透传: {agent_outputs[0].get('agent_name')}")
        return {
            "final_response": response,
        }

    # 多 Agent 结果 → LLM 汇总
    logger.info(f"Synthesizer 开始汇总 {len(agent_outputs)} 个 Agent 结果")

    # 推送汇总思考事件
    writer({"type": "thinking_stream", "block": {
        "content": f"📋 汇总 {len(agent_outputs)} 个任务结果",
        "agent": "synthesizer",
        "agent_display": "汇总",
        "is_streaming": True
    }})

    # 获取用户查询
    messages = state["messages"]
    user_message = get_latest_user_message(messages)

    # 从工具注册中心动态获取 display_name
    registry = get_tool_registry()
    all_tools = registry.get_all()

    # 构建各 Agent 结果描述
    results_text = []
    for output in agent_outputs:
        agent_name = output.get("agent_name", "unknown")
        display_name = output.get("display_name", "")
        if not display_name:
            tool_config = all_tools.get(agent_name)
            display_name = tool_config.display_name if tool_config else agent_name

        response = output.get("response", "")
        if response:
            results_text.append(f"### {display_name}\n{response}\n")
        else:
            results_text.append(f"### {display_name}\n无结果\n")

    results_text_str = "\n".join(results_text)

    # 使用 LLM 汇总
    prompt = f"""你是智能助手，需要汇总多个 Agent 的执行结果，给用户一个完整、友好的回复。

# 用户问题
{user_message}

# 各 Agent 执行结果
{results_text_str}

# 要求
1. 清晰展示各方面的信息
2. 按逻辑顺序整理结果
3. 语气友好，简洁明了
4. 不要使用 markdown 格式

直接给出回复。"""

    try:
        from app.utils.llm_helper import call_llm_stream
        from app.config import settings

        writer({"type": "thinking_stream", "block": {
            "content": "⚡ 生成汇总回复",
            "agent": "synthesizer",
            "agent_display": "汇总",
            "is_streaming": True
        }})

        # 流式调用 LLM，逐 token 推送到前端
        response = ""
        async for token in call_llm_stream(
            prompt=prompt,
            model=settings.LLM_MODEL,
            temperature=0.5,
            context="多任务结果汇总"
        ):
            response += token
            writer({"type": "content_stream", "block": {
                "delta": token,
                "accumulated": response,
                "agent": "synthesizer",
                "agent_display": "汇总",
            }})

        writer({"type": "thinking_stream", "block": {
            "content": "✓ 汇总完成",
            "agent": "synthesizer",
            "agent_display": "汇总",
            "is_streaming": False
        }})

        logger.info(f"Synthesizer 汇总完成，响应长度: {len(response)}")

        return {
            "messages": [AIMessage(content=response)],
            "final_response": response,
            "needs_user_input": False,
        }

    except Exception as e:
        logger.error(f"LLM 汇总失败: {e}")

        # 降级方案：简单拼接各 Agent 结果
        parts = ["为您查询到以下信息："]
        for output in agent_outputs:
            response_text = output.get("response", "")
            if response_text:
                parts.append(f"\n{response_text}")
        parts.append("\n还有其他需要帮忙的吗？")
        fallback = "\n".join(parts)

        writer({"type": "thinking_stream", "block": {
            "content": "⚠ LLM 汇总失败，使用拼接方案",
            "agent": "synthesizer",
            "agent_display": "汇总",
            "is_streaming": False
        }})

        # 降级内容一次性推送
        writer({"type": "content_stream", "block": {
            "delta": fallback,
            "accumulated": fallback,
            "agent": "synthesizer",
            "agent_display": "汇总",
        }})

        return {
            "messages": [AIMessage(content=fallback)],
            "final_response": fallback,
            "needs_user_input": False,
        }
