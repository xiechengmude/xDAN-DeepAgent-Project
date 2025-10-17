#!/usr/bin/env python3
"""快速检查 MCP 服务器返回的工具数量"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, 'src')

from deepagents.mcp_client import create_mcp_tools

async def main():
    mcp_server_url = os.environ.get("MCP_SERVER_URL")
    print(f"连接到: {mcp_server_url}")

    tools = await create_mcp_tools(server_url=mcp_server_url, transport="sse", timeout=30)

    print(f"\n总共加载: {len(tools)} 个工具")
    print(f"\n前 20 个工具:")
    for i, tool in enumerate(tools[:20], 1):
        print(f"  {i}. {tool.name}")

    print(f"\n后 20 个工具:")
    for i, tool in enumerate(tools[-20:], len(tools)-19):
        print(f"  {i}. {tool.name}")

    # 检查是否有重复
    tool_names = [t.name for t in tools]
    unique_names = set(tool_names)
    if len(tool_names) != len(unique_names):
        print(f"\n⚠️  发现重复工具！")
        print(f"总工具数: {len(tool_names)}")
        print(f"唯一工具数: {len(unique_names)}")

        # 找出重复的
        from collections import Counter
        duplicates = [name for name, count in Counter(tool_names).items() if count > 1]
        print(f"重复的工具: {duplicates}")
    else:
        print(f"\n✅ 没有重复工具")

if __name__ == "__main__":
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    asyncio.run(main())
