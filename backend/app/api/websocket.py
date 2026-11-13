"""
WebSocket 连接处理 - 多 Agent 协作模式

使用 MemorySaver checkpointer 管理会话状态，
通过 thread_id 区分不同会话。
"""
import logging
import uuid
import json
from fastapi import WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

"""
websocket.accept()、websocket.receive_text()、websocket.send_json、websocket.close()
这端点是用来干嘛的？建立连接、循环接受客户端数据并解析【JSON】、获取工作流并执行工作流、发送数据给客户端、关闭连接
"""
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点"""
    from app.api.routes import get_workflow

    # 接受请求的握手，建立连接
    await websocket.accept()
    session_id = None

    try:
        while True:  # 循环接收前端消息，并解析 JSON【那说明前端发的是 JSON 数据】
            data = await websocket.receive_text()  # 等待接受用户消息
            message_data = json.loads(data)

            session_id = message_data.get("session_id") or str(uuid.uuid4())  # 前端发送或uuid自动生成会话id
            user_message = message_data.get("message", "")

            workflow = get_workflow()

            # 使用 MemorySaver + thread_id 管理会话
            config = {"configurable": {"thread_id": session_id}}

            # 构建输入状态，实际上是自定义的 ChatRequest【models】
            input_state = {
                "messages": [HumanMessage(content=user_message)],
                "session_id": session_id,
                "show_thought": message_data.get("show_thought", False),
            }

            # 执行工作流  这里是 ainvoke，是阻塞式的，直到工作流执行完成才向前端返回结果
            result = await workflow.ainvoke(input_state, config=config)

            # 发送 JSON 消息给客户端
            # 格式为自定义的 ChatResponse【models】
            await websocket.send_json({
                "response": result.get("final_response", ""),
                "session_id": session_id,
                "needs_input": result.get("needs_user_input", False),
                "metadata": result.get("metadata", {})
            })

    except WebSocketDisconnect:  # 连接断开，记录日志
        logger.info(f"WebSocket 断开连接: {session_id}")
    except Exception as e:  # 连接异常、错误，记录日志，断开连接
        logger.error(f"WebSocket 错误: {e}", exc_info=True)
        await websocket.close()  # 关闭连接
