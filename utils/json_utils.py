import json
import re
from typing import Dict, Any, Optional, List, Union

def extract_and_parse_json(text: str) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
    """
    从字符串中提取JSON对象或数组并进行解析。
    能够处理JSON被包裹在Markdown代码块或被其他文本包围的情况。

    Args:
        text: 来自LLM的输入字符串。

    Returns:
        如果找到有效的JSON，则返回解析后的字典或列表，否则返回None。
    """
    if not isinstance(text, str):
        return None

    # 1. 尝试寻找被Markdown代码块包裹的JSON (e.g., ```json ... ```)
    # 匹配对象 (e.g. {...}) 或数组 (e.g. [...])
    match = re.search(r'```(?:json)?\s*([\[{].*?[\]}])\s*```', text, re.DOTALL)
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 如果解析失败，继续尝试其他方法
            pass

    # 2. 如果没有Markdown块，寻找第一个 '{' 或 '[' 到最后一个 '}' 或 ']'
    # 这对于从被文本包围的JSON中救援出来很有效
    json_str = None
    try:
        # 优先匹配对象
        start_brace = text.find('{')
        end_brace = text.rfind('}')
        if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
            json_str = text[start_brace:end_brace + 1]
            return json.loads(json_str)

        # 其次匹配数组
        start_bracket = text.find('[')
        end_bracket = text.rfind(']')
        if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
            json_str = text[start_bracket:end_bracket + 1]
            return json.loads(json_str)

    except json.JSONDecodeError:
        # 如果从提取的子字符串解析失败，继续
        pass

    # 3. 作为最后的手段，尝试直接解析整个字符串
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 如果所有尝试都失败了，则返回None
    print(f"警告: 无法从响应中解析JSON: {text[:500]}...")
    return None