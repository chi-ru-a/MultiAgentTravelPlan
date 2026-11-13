"""
JSON 解析工具 - 统一处理 LLM 返回的 JSON
"""
import json
import re
from typing import Any, Dict, Optional

# 这俩函数都是为了让 LLM 不规范的输出能被安全消费


# 这个函数是 解析 + 清理 + 兜底
# 解析 LLM 返回的 JSON，处理可能的格式问题，比如多余的文本、markdown 代码块等
# 返回解析后的 JSON，解析失败则返回默认值
def parse_llm_json(llm_output: str, default_value: Optional[Dict] = None) -> Dict[str, Any]:
    """
    安全解析 LLM 返回的 JSON
    
    Args:
        llm_output: LLM 返回的文本
        default_value: 解析失败时的默认值
        
    Returns:
        解析后的字典
    """
    if default_value is None:
        default_value = {}
        
    if not llm_output:
        return default_value

    cleaned = llm_output.strip()

    # 移除 markdown 代码块标记
    if "```" in cleaned:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        # 提取 JSON 对象
        start = cleaned.find('{')  # find 第一个 '{' 的位置
        end = cleaned.rfind('}')   # rfind 最后一个 '}' 的位置
        if start >= 0 and end > start:
            cleaned = cleaned[start:end+1]
        
        return json.loads(cleaned)  # json.loads() 将 JSON 字符串转换为 Python 字典
    except json.JSONDecodeError as e:  # 解析失败，也返回默认值
        print(f"[JSON Parser] 解析失败: {e}, 原始内容: {llm_output[:100]}...")
        return default_value

# 这个函数是从文本里找第一个能解析的 JSON 对象，找不到返回 None
def extract_json_from_text(text: str) -> Optional[Dict]:
    """
    从文本中提取第一个 JSON 对象
    
    Args:
        text: 包含 JSON 的文本
        
    Returns:
        提取的 JSON 对象，如果没有找到则返回 None
    """
    # 尝试匹配 JSON 对象
    pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.finditer(pattern, text, re.DOTALL)
    
    for match in matches:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
    
    return None
