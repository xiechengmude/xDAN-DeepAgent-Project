#!/usr/bin/env python3
"""
测试 MCP 集成 - 使用 LangChain 官方适配器
验证 MCP 工具能否正确加载和调用
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from deepagents.mcp_client import create_mcp_tools, create_mcp_tools_sync


async def test_mcp_async():
    """测试异步 MCP 工具加载"""
    print("=" * 60)
    print("测试异步 MCP 工具加载")
    print("=" * 60)

    mcp_server_url = os.environ.get("MCP_SERVER_URL")
    if not mcp_server_url:
        print("❌ MCP_SERVER_URL 未设置")
        return False

    print(f"\n✅ MCP 服务器: {mcp_server_url}")

    try:
        print("\n[1/2] 加载 MCP 工具（异步）...")
        tools = await create_mcp_tools(
            server_url=mcp_server_url,
            transport="sse",  # 使用 SSE 传输
            timeout=30
        )

        print(f"\n[2/2] 成功加载 {len(tools)} 个工具:")
        for i, tool in enumerate(tools, 1):
            desc = tool.description if hasattr(tool, 'description') else 'No description'
            desc = desc[:60] + '...' if len(desc) > 60 else desc
            print(f"  {i}. {tool.name}: {desc}")

        print("\n" + "=" * 60)
        if len(tools) > 0:
            print(f"✅ 异步测试通过 - 发现 {len(tools)} 个 MCP 工具")
        else:
            print("⚠️  异步测试通过 - 但没有发现 MCP 工具")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sync_wrapper():
    """测试同步包装器"""
    print("\n" + "=" * 60)
    print("测试同步包装器")
    print("=" * 60)

    try:
        print("\n正在加载 MCP 工具（同步）...")
        tools = create_mcp_tools_sync()

        print(f"\n✅ 成功加载 {len(tools)} 个工具:")
        for i, tool in enumerate(tools, 1):
            desc = tool.description if hasattr(tool, 'description') else 'No description'
            desc = desc[:60] + '...' if len(desc) > 60 else desc
            print(f"  {i}. {tool.name}: {desc}")

        print("\n" + "=" * 60)
        if len(tools) > 0:
            print(f"✅ 同步测试通过 - 发现 {len(tools)} 个 MCP 工具")
        else:
            print("⚠️  同步测试通过 - 但没有发现 MCP 工具")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n🚀 开始测试 MCP 集成 (使用 LangChain 官方适配器)\n")

    # 测试 1: 异步 MCP 工具加载
    test1_passed = await test_mcp_async()

    # 测试 2: 同步包装器
    test2_passed = test_sync_wrapper()

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"异步 MCP 工具加载: {'✅ 通过' if test1_passed else '❌ 失败'}")
    print(f"同步包装器测试: {'✅ 通过' if test2_passed else '❌ 失败'}")

    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过！MCP 集成正常工作")
        print("\n📝 注意: 如果没有发现 MCP 工具，可能是：")
        print("  1. MCP 服务器没有注册任何工具")
        print("  2. MCP 服务器配置或网络问题")
        print("  3. Transport 类型不匹配（当前使用 'sse'）")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查上面的错误信息")
        return 1


if __name__ == "__main__":
    # 禁用代理
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
