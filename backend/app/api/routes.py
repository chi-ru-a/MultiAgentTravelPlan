"""
API 路由 - LangGraph 流式输出（最佳实践版本）

使用 stream_mode="custom" 实现统一流式输出：
- 思考链事件：Supervisor/Agent 通过 get_stream_writer() 推送
- 内容事件：Synthesizer 通过 get_stream_writer() 推送 content_stream
- 所有事件通过 custom 模式统一管控，避免 messages 模式重复

通过 MemorySaver + thread_id 实现会话管理，替代手写 SessionManager。
"""
import logging
import uuid
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.graph.langgraph_workflow import compile_workflow
from app.models.schemas import ChatRequest
from app.utils.message_helpers import sse_event

logger = logging.getLogger(__name__)

router = APIRouter()  # 相当于控制器

# 全局工作流实例（延迟初始化）
_workflow_instance = None  # _开头，私有，只能在模块内部访问；但这是约定，语法层面不强制，还是可以访问


def get_workflow():
    """获取编译后的工作流实例（延迟初始化，确保工具已注册）"""
    global _workflow_instance
    if _workflow_instance is None:
        logger.info("首次编译工作流...")
        _workflow_instance = compile_workflow()
        logger.info("工作流编译完成")
    return _workflow_instance


def warmup_workflow():
    """预热工作流（在 lifespan 中调用，避免首次请求延迟）"""
    get_workflow()


@router.get("/test")  # 相当于 @RequestMapping 及其派生注解
async def test_route():
    """测试路由"""
    return {"status": "ok", "message": "test route works"}

"""
用户输入消息 → POST 请求 → 消息封装为自定义的 ChatRequest → workflow.astream() → SSE 流式输出
把用户的请求消息封装为自定义的 ChatRequest，
"""
@router.post("/chat/stream")
async def chat_stream(request_body: ChatRequest, request: Request):
    """
    聊天流式接口 - LangGraph 原生流式输出

    使用 stream_mode="custom"：
    - 所有事件通过 get_stream_writer() 统一推送
    - 思考链（thinking_stream）：Supervisor 和 Agent 推送
    - 回复内容（content_stream）：Synthesizer 推送
    - 通过 thread_id 配置实现 MemorySaver 会话持久化
    """
    workflow = get_workflow()  # app 应用在启动时预热过工作流，在这里直接获取
    session_id = request_body.session_id or str(uuid.uuid4())

    logger.info(f"收到流式请求: session={session_id}, message={request_body.message[:50]}...")

    # MemorySaver 通过 thread_id 区分会话
    config = {"configurable": {"thread_id": session_id}}

    async def stream_output():
        try:
            # 发送初始事件
            yield sse_event("session_id", {"session_id": session_id})
            yield sse_event("thinking_start")

            # 构建输入状态（MemorySaver 自动加载历史 messages）
            input_state = {
                "messages": [HumanMessage(content=request_body.message)],
                "session_id": session_id,
                "show_thought": request_body.show_thought,
            }

            # 追踪累积内容
            accumulated_content = ""
            has_content = False

            # 使用 custom 流模式：所有事件通过 get_stream_writer() 推送
            async for payload in workflow.astream(
                input_state,
                config=config,
                stream_mode="custom"
            ):
                # 检查客户端断连
                if await request.is_disconnected():
                    logger.info(f"客户端断连: session={session_id}")
                    break

                event_type = payload.get("type", "")

                if event_type == "thinking_stream":
                    # 思考链事件 → 直接转发
                    yield sse_event("thinking_stream", payload)

                elif event_type == "content_stream":
                    # 内容推送事件（来自 Synthesizer）
                    block = payload.get("block", {})
                    delta = block.get("delta", "")
                    accumulated = block.get("accumulated", "")
                    agent = block.get("agent", "")
                    agent_display = block.get("agent_display", "")

                    if delta:
                        accumulated_content = accumulated or (accumulated_content + delta)
                        has_content = True

                        yield sse_event("content_stream", {
                            "delta": delta,
                            "accumulated": accumulated_content,
                            "agent": agent,
                            "agent_display": agent_display,
                        })

            # 思考结束
            yield sse_event("thinking_end")

            # 如果没有通过流式事件发送内容，从 final_response 获取
            if not has_content:
                try:
                    final_state = await workflow.aget_state(config)
                    if final_state and final_state.values:
                        final_response = final_state.values.get("final_response", "")
                        if final_response:
                            accumulated_content = final_response
                            yield sse_event("content_stream", {
                                "delta": final_response,
                                "accumulated": final_response,
                            })
                except Exception as e:
                    logger.warning(f"获取 final_state 失败: {e}")

            if not accumulated_content:
                accumulated_content = "抱歉，我无法处理您的请求。"
                yield sse_event("content_stream", {
                    "delta": accumulated_content,
                    "accumulated": accumulated_content,
                })

            # 发送结束事件
            yield sse_event("response_end", {
                "content": accumulated_content,
                "needs_input": False,
            })

        except Exception as e:
            logger.error(f"流式处理错误: {e}", exc_info=True)
            yield sse_event("error", {"error": str(e)})

    return StreamingResponse(
        stream_output(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "multi-agent-collaborative-api"}
