"""
Search Query Parser
==================
KISS原则：解析 <search> 标签和管道符号
"""

import re
from typing import List, Union


def parse_search_queries(query: str) -> List[str]:
    """
    解析搜索查询，支持两种格式：
    1. <search>标签格式: <search>query1</search><search>query2</search>
    2. 管道格式: query1 | query2 | query3
    
    Args:
        query: 输入查询字符串
        
    Returns:
        查询列表
    """
    # 首先检查是否有 <search> 标签
    search_pattern = r'<search>(.*?)</search>'
    search_matches = re.findall(search_pattern, query, re.DOTALL)
    
    if search_matches:
        # 有 <search> 标签，返回所有匹配的查询
        return [q.strip() for q in search_matches if q.strip()]
    
    # 检查是否有管道符号
    elif '|' in query:
        # 管道格式
        queries = [q.strip() for q in query.split('|') if q.strip()]
        return queries
    
    # 单一查询
    else:
        return [query.strip()]


def format_parallel_search(queries: List[str]) -> str:
    """
    将查询列表格式化为 <search> 标签格式
    
    Args:
        queries: 查询列表
        
    Returns:
        格式化的搜索字符串
    """
    if len(queries) == 1:
        return queries[0]
    
    return ''.join([f'<search>{q}</search>' for q in queries])


def convert_to_pipe_format(query: str) -> str:
    """
    将 <search> 标签格式转换为管道格式
    
    Args:
        query: 可能包含 <search> 标签的查询
        
    Returns:
        管道格式的查询字符串
    """
    queries = parse_search_queries(query)
    
    if len(queries) == 1:
        return queries[0]
    
    return ' | '.join(queries)


# 测试
if __name__ == "__main__":
    # 测试各种格式
    test_cases = [
        "Tesla stock price 2024",  # 单一查询
        "Tesla stock | Apple stock | Microsoft stock",  # 管道格式
        "<search>Tesla stock 2024</search><search>Apple earnings</search>",  # 标签格式
        "<search>特斯拉股价 2024</search><search>比亚迪销量</search>",  # 中文标签
    ]
    
    for test in test_cases:
        print(f"\n输入: {test}")
        queries = parse_search_queries(test)
        print(f"解析结果: {queries}")
        print(f"管道格式: {convert_to_pipe_format(test)}")