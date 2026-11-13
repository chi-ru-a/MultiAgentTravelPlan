"""
闲聊工具 - LangChain Tool
"""
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from typing import Type, Optional
from app.utils.llm_client import get_llm_client
import json

"""
pydantic 的 BaseModel，定义数据模型，可以声明字段结构、类型约束、默认值以及校验规则
定义类，继承 BaseModel
Field 用于声明字段的元数据，比如描述【description】、默认值【default】、校验规则【比如 Literal["celsius", "fahrenheit"] 限定字段类型】

Optional 用于类型注解，表示某个字段可以为 None
"""
class ChitchatInput(BaseModel):
    """闲聊输入参数"""
    message: str = Field(description="用户的消息内容")

"""
@tool(args_schema=ChitchatInput)，通过 args_schema，将工具参数与自定义的 Pydantic 模型绑定，方便参数校验和文档生成
@tool(args_schema=json_schema_dict)，通过 args_schema，将自定义的 JSON Schema 字典与工具参数绑定，方便参数校验和文档生成
这是一个 JSON Schema 示例
weather_schema = {
    "type": "object",  # 当前数据节点的类型，常见类型有 string, number, integer, boolean, object, array, null。object即是json对象
    "properties": {    # 对象包含的属性，以及类型说明
        "location": {"type": "string"},
        "units": {"type": "string"},
        "include_forecast": {"type": "boolean"}
    },
    "required": ["location", "units", "include_forecast"]  # object 为数组，对象中必须存在的属性
}




BaseTool 是 LangChain 的工具基类，所有自定义工具都需要继承它


# parse_docstring=True 表示自动解析 docstring，提取工具的描述信息和参数说明，填充到响应的字段中
# name_or_callable 更改工具名称
# description 工具功能描述
@tool(parse_docstring=True, name_or_callable="getWeather", description="根据城市名称查询当日天气的工具")
def get_weather(city: str, units: str = "celsius", include_forecast: bool = False) -> str:
    获取当日天气，可选择是否同时查询未来五日天气预报

    Args:
        city: 城市
        units: 气温单位，可选：celsius-摄氏度，fahrenheit-华氏度
        include_forecast: 是否包含未来五日的天气预报
"""
class ChitchatTool(BaseTool):
    """闲聊工具"""
    name: str = "chitchat"
    description: str = """闲聊工具，用于处理一般性对话、问候、感谢等。
    
    使用场景：
    - 用户问候：你好、嗨、早上好
    - 用户感谢：谢谢、多谢
    - 一般性对话：聊天、闲聊
    - 无法匹配其他工具的查询
    
    输入参数：
    - message: 用户的消息

    示例：
    - "你好"
    - "谢谢你的帮助"
    - "你是谁？"
    - "今天天气真好"
    """
    args_schema: Type[BaseModel] = ChitchatInput  # Type 用于类型注解，表示某个字段的类型是一个类，而不是实例
    
    # 使用 PrivateAttr 声明私有属性
    _llm_client: Optional[any] = PrivateAttr(default=None)  # PrivateAttr 用于声明私有属性，不会被序列化或校验，适合存储内部状态或缓存
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化 LLM 客户端
        self._llm_client = get_llm_client()
    
    def _run(self, message: str) -> str:
        """执行闲聊"""
        try:
            # 确保客户端已初始化
            if self._llm_client is None:
                self._llm_client = get_llm_client()
            
            # 构建系统提示词
            system_prompt = """你是一个友好的智能旅行助手。

你的职责：
1. 友好地回应用户的问候、感谢等
2. 简要介绍自己的能力（班次查询、天气查询、业务咨询）
3. 引导用户使用你的服务
4. 保持简洁、友好的语气

回复要求：
- 简洁明了，不超过 100 字
- 语气友好、自然
- 适当引导用户使用服务
- 不要使用 markdown 格式

示例：
用户："你好"
回复："你好！我是智能旅行助手，可以帮您查询班次、天气，以及解答出行相关问题。有什么可以帮您的吗？"

用户："谢谢"
回复："不客气！很高兴能帮到您。如果还有其他问题，随时告诉我。"
"""
            
            # 调用 LLM
            response = self._llm_client.chat.completions.create(
                model="qwen-max",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            reply = response.choices[0].message.content.strip()

            # json.dumps() 将 Python 字典转换为 JSON 字符串，ensure_ascii=False 保证中文不被转义
            # json.loads() 将 JSON 字符串转换为 Python 字典
            return json.dumps({
                "success": True,
                "message": message,
                "reply": reply
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            import traceback
            print(f"[ChitchatTool] 错误: {e}")
            print(traceback.format_exc())
            
            # 降级方案：使用预设回复
            fallback_replies = {
                "你好": "你好！我是智能旅行助手，可以帮您查询班次、天气，以及解答出行相关问题。有什么可以帮您的吗？",
                "谢谢": "不客气！很高兴能帮到您。",
                "再见": "再见！祝您旅途愉快！",
            }
            
            # 尝试匹配预设回复
            reply = fallback_replies.get(message, "您好！我是智能旅行助手，有什么可以帮您的吗？")  # 字典.get(key, default)
            
            return json.dumps({
                "success": True,
                "message": message,
                "reply": reply,
                "fallback": True
            }, ensure_ascii=False, indent=2)
    
    async def _arun(self, message: str) -> str:
        """异步执行（当前使用同步实现）"""
        return self._run(message)
