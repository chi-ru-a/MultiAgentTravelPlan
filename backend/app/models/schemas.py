"""
Pydantic模型定义
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ThoughtStep(BaseModel):
    """思考步骤"""
    step: str  # 步骤名称（计划/思考/行动）
    content: str  # 步骤内容
    agent: Optional[str] = None  # 执行的Agent名称
    duration: Optional[float] = None  # 耗时（秒）


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: str = None
    show_thought: bool = False  # 是否展示思考过程


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str
    session_id: str
    needs_input: bool
    thoughts: List[ThoughtStep] = []  # 思考链
    metadata: dict = None