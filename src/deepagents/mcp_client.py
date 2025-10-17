"""
MCP (Model Context Protocol) 客户端 - 使用 LangChain 官方适配器
连接到 MCP 服务器并将其工具集成到 DeepAgent
"""

import os
import logging
from typing import List, Optional
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


async def create_mcp_tools(
    server_url: Optional[str] = None,
    transport: str = "sse",
    timeout: int = 30,
    api_key: Optional[str] = None
) -> List[BaseTool]:
    """
    使用 LangChain MCP Adapters 创建 MCP 工具列表（异步）

    Args:
        server_url: MCP 服务器 URL（默认从环境变量 MCP_SERVER_URL 读取）
        transport: 传输协议类型，支持 "sse", "streamable_http", "stdio", "websocket"
        timeout: 请求超时时间（秒）
        api_key: API Key（默认从环境变量 MCP_SERVER_API_KEY 读取）

    Returns:
        LangChain Tool 列表
    """
    server_url = server_url or os.environ.get("MCP_SERVER_URL")
    api_key = api_key or os.environ.get("MCP_SERVER_API_KEY")

    if not server_url:
        logger.warning("MCP_SERVER_URL 未设置，跳过 MCP 工具加载")
        return []

    try:
        logger.info(f"正在连接 MCP 服务器: {server_url} (transport: {transport})")
        if api_key:
            logger.info("使用 API Key 认证")

        # 创建 MultiServerMCPClient
        # 注意：即使只有一个服务器，也要使用字典格式配置
        server_config = {
            "transport": transport,
            "url": server_url,
            "timeout": timeout,
            "sse_read_timeout": 300.0,  # 5分钟 keep-alive
        }

        # 如果有 API Key，添加到 headers
        if api_key:
            server_config["headers"] = {
                "Authorization": f"Bearer {api_key}",
                "X-API-Key": api_key,  # 有些服务器使用这个 header
            }

        client = MultiServerMCPClient({"default": server_config})

        # 获取所有工具
        tools = await client.get_tools()

        logger.info(f"✅ 成功加载 {len(tools)} 个 MCP 工具")
        for tool in tools:
            logger.info(f"  • {tool.name}: {tool.description[:60]}...")

        return tools

    except Exception as e:
        logger.error(f"❌ 加载 MCP 工具失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def create_mcp_tools_sync(
    server_url: Optional[str] = None,
    transport: str = "sse",
    timeout: int = 30
) -> List[BaseTool]:
    """
    使用 LangChain MCP Adapters 创建 MCP 工具列表（同步版本）

    Args:
        server_url: MCP 服务器 URL（默认从环境变量 MCP_SERVER_URL 读取）
        transport: 传输协议类型，支持 "sse", "streamable_http", "stdio", "websocket"
        timeout: 请求超时时间（秒）

    Returns:
        LangChain Tool 列表
    """
    import asyncio

    try:
        # 创建新的事件循环来运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                create_mcp_tools(server_url, transport, timeout)
            )
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ 创建 MCP 工具失败（同步）: {e}")
        return []
