"""
LangGraph Platform 工厂函数
符合 LangGraph Platform 要求的 graph 工厂函数
"""

import os
import logging
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from deepagents.graph import create_deep_agent, async_create_deep_agent
from deepagents.auto_search_tool.auto_search_tool import create_auto_search_tool
from deepagents.mcp_client import create_mcp_tools

logger = logging.getLogger(__name__)


async def deep_agent_factory(config: RunnableConfig):
    """
    LangGraph Platform 工厂函数 - 同步版本

    Args:
        config: RunnableConfig，由 LangGraph Platform 传入（预留用于未来扩展）

    Returns:
        创建好的 Deep Agent graph
    """
    # Note: config 参数由 LangGraph Platform 传入，预留用于未来配置扩展
    _ = config  # Explicitly mark as intentionally unused

    # 从环境变量获取配置
    brightdata_api_key = os.environ.get("BRIGHTDATA_API_KEY", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "http://150.109.16.195:8600/v1")
    openai_model = os.environ.get("OPENAI_MODEL", "deepseek/deepseek-chat-official")

    # 创建 auto_search 工具
    auto_search = create_auto_search_tool(
        brightdata_api_key=brightdata_api_key,
        auto_fetch_limit=3,
        enable_smart_extraction=True
    )

    # 加载 MCP 工具
    mcp_tools = []
    try:
        mcp_server_url = os.environ.get("MCP_SERVER_URL")
        if mcp_server_url:
            logger.info(f"正在从 {mcp_server_url} 加载 MCP 工具...")
            mcp_tools = await create_mcp_tools(server_url=mcp_server_url, timeout=30)
            logger.info(f"成功加载 {len(mcp_tools)} 个 MCP 工具")
    except Exception as e:
        logger.warning(f"加载 MCP 工具失败: {e}")

    # 组合所有工具
    all_tools = [auto_search] + mcp_tools

    # 创建模型
    model = ChatOpenAI(
        model=openai_model,
        temperature=0,
        api_key=openai_api_key,
        base_url=openai_base_url
    )

    # 创建并返回 agent
    return create_deep_agent(
        tools=all_tools,
        model=model,
        instructions="""You are a helpful research assistant with advanced search capabilities and access to external MCP tools.

## Available Tools

### 1. Auto Search Tool (`auto_search`)

You have access to the `auto_search` tool with two modes:

1. **Light Mode** (quick results):
   - Use `mode="light"` for fast SERP-only searches
   - Returns titles, URLs, and snippets
   - Best for: quick lookups, getting an overview

2. **Full Mode** (deep research):
   - Use `mode="full"` for complete content extraction
   - Automatically fetches and extracts full page content
   - Includes PDF document support
   - Best for: detailed analysis, research papers, documentation

3. **Parallel Search**:
   - Search multiple topics simultaneously: `"<search>Python|JavaScript|Go</search>"`
   - Significantly faster than sequential searches
   - Best for: comparative research, multi-topic exploration

### 2. MCP Tools (Dynamic)

You also have access to external MCP (Model Context Protocol) tools. These tools are dynamically loaded from the MCP server and will be prefixed with `mcp_`.

To see available MCP tools, check the tool names in your available tools list. Each MCP tool provides specialized capabilities from external services.

## Best Practices

- Start with Light mode search to identify relevant results
- Switch to Full mode when you need detailed content from web pages
- Use parallel search when researching multiple related topics
- Leverage MCP tools for specialized tasks beyond web search
- Always provide clear, structured summaries of your findings
"""
    )


async def async_deep_agent_factory(config: RunnableConfig):
    """
    LangGraph Platform 工厂函数 - 异步版本

    Args:
        config: RunnableConfig，由 LangGraph Platform 传入（预留用于未来扩展）

    Returns:
        创建好的 Deep Agent graph（异步）
    """
    # Note: config 参数由 LangGraph Platform 传入，预留用于未来配置扩展
    _ = config  # Explicitly mark as intentionally unused

    # 从环境变量获取配置
    brightdata_api_key = os.environ.get("BRIGHTDATA_API_KEY", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "http://150.109.16.195:8600/v1")
    openai_model = os.environ.get("OPENAI_MODEL", "deepseek/deepseek-chat-official")

    # 创建 auto_search 工具
    auto_search = create_auto_search_tool(
        brightdata_api_key=brightdata_api_key,
        auto_fetch_limit=3,
        enable_smart_extraction=True
    )

    # 加载 MCP 工具
    mcp_tools = []
    try:
        mcp_server_url = os.environ.get("MCP_SERVER_URL")
        if mcp_server_url:
            logger.info(f"正在从 {mcp_server_url} 加载 MCP 工具...")
            mcp_tools = await create_mcp_tools(server_url=mcp_server_url, timeout=30)
            logger.info(f"成功加载 {len(mcp_tools)} 个 MCP 工具")
    except Exception as e:
        logger.warning(f"加载 MCP 工具失败: {e}")

    # 组合所有工具
    all_tools = [auto_search] + mcp_tools

    # 创建模型
    model = ChatOpenAI(
        model=openai_model,
        temperature=0,
        api_key=openai_api_key,
        base_url=openai_base_url
    )

    # 创建并返回 agent（异步）
    return async_create_deep_agent(
        tools=all_tools,
        model=model,
        instructions="""You are a helpful research assistant with advanced search capabilities and access to external MCP tools.

## Available Tools

### 1. Auto Search Tool (`auto_search`)

You have access to the `auto_search` tool with two modes:

1. **Light Mode** (quick results):
   - Use `mode="light"` for fast SERP-only searches
   - Returns titles, URLs, and snippets
   - Best for: quick lookups, getting an overview

2. **Full Mode** (deep research):
   - Use `mode="full"` for complete content extraction
   - Automatically fetches and extracts full page content
   - Includes PDF document support
   - Best for: detailed analysis, research papers, documentation

3. **Parallel Search**:
   - Search multiple topics simultaneously: `"<search>Python|JavaScript|Go</search>"`
   - Significantly faster than sequential searches
   - Best for: comparative research, multi-topic exploration

### 2. MCP Tools (Dynamic)

You also have access to external MCP (Model Context Protocol) tools. These tools are dynamically loaded from the MCP server and will be prefixed with `mcp_`.

To see available MCP tools, check the tool names in your available tools list. Each MCP tool provides specialized capabilities from external services.

## Best Practices

- Start with Light mode search to identify relevant results
- Switch to Full mode when you need detailed content from web pages
- Use parallel search when researching multiple related topics
- Leverage MCP tools for specialized tasks beyond web search
- Always provide clear, structured summaries of your findings
"""
    )
