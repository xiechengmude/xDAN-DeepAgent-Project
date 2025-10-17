#!/usr/bin/env python3
"""对比两个 MCP 服务器的工具差异"""
import asyncio
import os
import sys
sys.path.insert(0, 'src')

from deepagents.mcp_client import create_mcp_tools

async def get_tools(server_url, name):
    """获取指定服务器的工具列表"""
    print(f"\n正在连接 {name}: {server_url}")
    try:
        tools = await create_mcp_tools(server_url=server_url, transport="sse", timeout=30)
        tool_names = set([t.name for t in tools])
        print(f"✅ {name} 加载了 {len(tools)} 个工具")
        return tool_names
    except Exception as e:
        print(f"❌ {name} 连接失败: {e}")
        return set()

async def main():
    old_server = "http://43.134.61.136:7223/sse"
    new_server = "http://43.156.81.75:7223/sse"

    # 获取两个服务器的工具
    old_tools = await get_tools(old_server, "旧服务器")
    new_tools = await get_tools(new_server, "新服务器")

    # 对比差异
    only_in_new = new_tools - old_tools
    only_in_old = old_tools - new_tools
    common = old_tools & new_tools

    print("\n" + "="*80)
    print("对比结果")
    print("="*80)
    print(f"旧服务器独有: {len(only_in_old)} 个工具")
    print(f"新服务器独有: {len(only_in_new)} 个工具")
    print(f"共同工具: {len(common)} 个")

    if only_in_new:
        print(f"\n{'='*80}")
        print(f"新服务器新增的 {len(only_in_new)} 个工具:")
        print("="*80)
        for i, tool in enumerate(sorted(only_in_new), 1):
            print(f"  {i}. {tool}")

    if only_in_old:
        print(f"\n{'='*80}")
        print(f"旧服务器独有的 {len(only_in_old)} 个工具:")
        print("="*80)
        for i, tool in enumerate(sorted(only_in_old), 1):
            print(f"  {i}. {tool}")

if __name__ == "__main__":
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    asyncio.run(main())
