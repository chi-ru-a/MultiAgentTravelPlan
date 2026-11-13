"""
Agent 状态定义 - LangGraph 最佳实践版本

使用 Annotated reducer 支持并行节点安全写入。
通过 get_stream_writer() 推送思考链，不再依赖 state 传递。
"""
from typing import TypedDict, Annotated, Sequence, List, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# 自定义规约器
def _reset_on_empty(existing: list, new: list) -> list:
    """
    自定义列表 reducer：空列表重置，非空追加

    用于 agent_outputs 字段，确保：
    - Supervisor 传入 [] 时重置（清除上一轮调用的旧结果）
    - Agent 传入 [{...}] 时追加（支持并行 fan-in 安全聚合）
    """
    if not new:
        return []
    return existing + new

"""
LangGraph的自定义状态，继承 TypedDict，是字典，无默认值、无校验
除了继承 TypedDict 之外，还有 @dataclass、继承 BaseModel 等方式实现自定义状态
"""
class ThoughtStep(TypedDict):
    """思考步骤 - 用于 SSE 推送"""
    content: str               # 思考内容
    agent: str                 # Agent 技术名称
    agent_display: str         # Agent 显示名称
    duration: float            # 耗时（秒）
    is_streaming: bool         # 是否正在流式输出
    sub_thoughts: List[Any]    # 子思考（可选）


class AgentOutput(TypedDict):
    """单个 Agent 的执行结果（用于 reducer 聚合）"""
    agent_name: str            # Agent 技术名称
    display_name: str          # Agent 显示名称
    success: bool              # 是否执行成功
    response: str              # 格式化后的回复文本
    data: dict                 # 原始工具返回数据

# 目前看到了这个状态的使用，是整个工作流主图中共享的状态
class AgentState(TypedDict):
    """
    Agent 共享状态 - LangGraph 最佳实践

    关键设计：
    - messages: 使用 add_messages reducer，LangGraph 自动管理对话历史
    - agent_outputs: 使用 _reset_on_empty reducer，支持并行 fan-in 且每轮自动重置
    - 思考链通过 get_stream_writer() 推送，不再往 state 中 append
    - 配合 MemorySaver checkpointer 实现跨轮次会话持久化
    """
    # ===== 对话管理（LangGraph 原生） =====
    messages: Annotated[Sequence[BaseMessage], add_messages]  # add_messages 规约器，针对消息列表的智能合并，支持按 id 去重、更新、删除
    session_id: str
    show_thought: bool

    # ===== 路由 =====
    next_agents: List[str]     # 待执行的 Agent 列表
    intent: str                # 用户意图分析结果

    # ===== 思考链（兼容旧前端，主要通过 custom stream 推送） =====
    thoughts: List[ThoughtStep]

    # ===== Agent 结果（自定义 reducer：空列表重置，非空追加） =====
    agent_outputs: Annotated[list, _reset_on_empty]  # 自定义规约器

    # ===== 各 Agent 上下文 =====
    ticket_context: dict
    weather_context: dict
    consultation_context: dict

    # ===== 输出 =====
    final_response: str
    needs_user_input: bool
    metadata: dict

    # ===== 协作 =====
    subtasks: List[dict]       # Supervisor 分解的子任务列表
    collaboration_mode: str    # single / parallel
