"""
简单的标签内容提取工具
使用字符串匹配，对特殊字符免疫
"""
import re
from typing import Optional, List


def extract_tag_content(text: str, tag_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    提取指定标签的内容
    
    Args:
        text: 包含标签的文本
        tag_name: 标签名称
        default: 未找到时的默认值
        
    Returns:
        标签内容，如果未找到返回default
    """
    pattern = f'<{tag_name}>(.*?)</{tag_name}>'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    return default


def extract_all_tags(text: str, tag_name: str) -> List[str]:
    """
    提取所有指定标签的内容（支持多个同名标签）
    
    Args:
        text: 包含标签的文本
        tag_name: 标签名称
        
    Returns:
        所有匹配标签的内容列表
    """
    pattern = f'<{tag_name}>(.*?)</{tag_name}>'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    return [match.strip() for match in matches if match.strip()]