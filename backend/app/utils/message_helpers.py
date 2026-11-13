"""
公共工具函数 - 消息处理、SSE 事件构造、stream writer 兼容
"""
import json
import logging
from typing import Sequence, Callable
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


# get_writer() 是用来获取流式输出的调用函数的【内部通过 get_stream_writer()】
# 而 ensure_config_context() 是给 get_writer() 打补丁的【因为 get_stream_writer() 在 Python 3.10 及以下版本存在问题】
# 上面是一种流式输出的做法，这样太麻烦了
#
# 我学的 LangGraph，是在工具中通过 ToolRuntime 来获取 stream_writer，在节点中通过 Runtime 来获取 stream_writer，
# 再在调用 运行图.stream() 时指定 stream_mode 为 custom 就行了【自定义输出内容】
# 他这个做法弄麻烦了





# 获取消息列表中最新的用户消息
def get_latest_user_message(messages: Sequence[BaseMessage]) -> str:
    """获取消息列表中最新的用户消息"""
    for msg in reversed(messages):  # 消息列表，取反
        if isinstance(msg, HumanMessage):  # 判断 msg 是不是 HumanMessage 类型
            return msg.content  # 返回 HumanMessage 的内容
    return ""





"""
SSE 协议规定，每个事件由若干行组成，每行以 \n 结尾，事件之间以空行分隔，\n\n 表示一个事件的结束。
事件格式：
    event: <event_type>\n  # 事件类型
    data: <json_data>\n    # 事件数据，JSON 格式
    \n

    event: thinking_start\n
    data: {"type": "thinking_start", "session_id": "xxx"}\n
    \n

上面是标准的格式，如果用这种格式，前端需要注册 EventSource.addEventListener("thinking_start", callback) 来监听事件。
为了简化前端处理，这里统一使用 data: {...}\n\n 的格式，所有事件都通过 data 字段传递【事件类型、事件数据都放到这里】
，前端只需要监听 onmessage 事件，再自己判断即可。

事件是在调用 sse_event 时，自己定义的
"""
def sse_event(event_type: str, data: dict = None) -> str:
    """
    构造 SSE 事件字符串

    Args:
        event_type: 事件类型（session_id, thinking_start, thinking_stream, content_stream 等）
        data: 事件数据字典

    Returns:
        格式化的 SSE 事件字符串
    """
    payload = {"type": event_type}
    if data:
        payload.update(data)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"





"""
这个函数是用来打补丁的
LangGraph 通过 get_stream_writer() 在节点间实现事件流式传输，该函数内部通过 contextvars 获取当前的 RunnableConfig。
contextvars 的传递依赖 asyncio 的上下文复制机制，但在 Python 3.10 及以下版本中，不会自动复制，导致在异步函数中无法获取到 RunnableConfig，从而无法正确推送事件。
因此，我先拿到上下文变量 var_child_runnable_config，再把配置手动塞到这个上下文变量中，这样在异步函数中就可以通过 get_stream_writer() 正常获取到配置了。

Runnable是可运行图，RunnableConfig是可运行图的配置
RunnableConfig继承TypedDict，因此可以用创建对象的方式实例化，也可以用字典的方式实例化
RunnableConfig里面的configurable属性，是一个字典，存储key-value这种配置
config = {"configurable": {"thread_id": "chapter_6_6-2-2"}}，配置的 configurable，就是 RunnableConfig 的属性
"""
def ensure_config_context(config: RunnableConfig) -> None:
    """
    确保 LangGraph config 在当前上下文中可用（Python 3.10 兼容方案）

    Python < 3.11 的 asyncio 不传播 contextvars，导致 get_stream_writer() 和
    writer() 调用时找不到运行时配置。手动将 config 设置到 contextvar 中解决此问题。

    Args:
        config: LangGraph 传入的 RunnableConfig（节点函数第二个参数）
    """
    from langchain_core.runnables.config import var_child_runnable_config
    if config and not var_child_runnable_config.get(None):
        var_child_runnable_config.set(config)



"""
Callable：一个可调用的东西，后面的中括号[]分别说明了"它需要什么输入"和"它返回什么"
比如：Callable[
    [ToolCallRequest, Callable[[ToolCallRequest], ToolMessage | Command]],  # 输入
    ToolMessage | Command  # 输出
]
"""
def get_writer(config: RunnableConfig = None) -> Callable:
    """
    获取 LangGraph stream writer（兼容 Python 3.10+）

    先确保 config context 可用，再获取 stream writer。

    Args:
        config: LangGraph 传入的 RunnableConfig（节点函数第二个参数）

    Returns:
        StreamWriter 函数，如果不可用则返回 no-op
    """
    # 确保 config context 在当前上下文中可用
    if config:
        ensure_config_context(config)  # 打补丁，把配置补到上下文当中

    try:
        from langgraph.config import get_stream_writer
        return get_stream_writer()  # 尝试拿 stream_writer()，拿到返回
    except RuntimeError:  # 拿不到，记录日志，返回匿名函数【一个参数 x，return None】
        logger.warning("无法获取 stream writer，思考链事件将不会推送")
        return lambda x: None
