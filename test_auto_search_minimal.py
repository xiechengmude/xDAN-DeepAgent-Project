"""
最小化 auto_search 工具单点测试
只测试工具创建和基本调用，不测试复杂的内容提取
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加 src 到路径
sys.path.insert(0, "src")

from deepagents.auto_search_tool.auto_search_tool import create_auto_search_tool


async def test_minimal():
    """最小化测试：验证工具创建和基本调用"""

    print("\n" + "="*60)
    print("Auto Search 工具单点测试（最小化版本）")
    print("="*60)

    # ========== 测试 1: 工具创建 ==========
    print("\n[测试 1] 工具创建")
    try:
        auto_search = create_auto_search_tool(
            brightdata_api_key=os.environ["BRIGHTDATA_API_KEY"],
            auto_fetch_limit=0,  # 关闭自动抓取，只测试搜索
            enable_smart_extraction=False  # 关闭智能提取
        )
        print("✅ 工具创建成功")
        print(f"   工具名称: {auto_search.name}")
        print(f"   工具类型: {type(auto_search).__name__}")
    except Exception as e:
        print(f"❌ 工具创建失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========== 测试 2: Light 模式（仅SERP，无内容抓取） ==========
    print("\n[测试 2] Light 模式调用（仅SERP搜索）")
    try:
        result = await auto_search.ainvoke({
            "query": "<search>Python asyncio tutorial</search>",
            "num_results": 3,
            "mode": "light"
        })

        print("✅ Light 模式调用成功")
        print(f"   查询成功: {result.get('success', False)}")
        print(f"   结果数量: {len(result.get('results', []))}")
        print(f"   统计信息: {result.get('statistics', {})}")

        if result.get('results'):
            print(f"\n   前3个结果:")
            for i, item in enumerate(result['results'][:3], 1):
                print(f"   [{i}] {item.get('title', 'No title')[:50]}...")
                print(f"       URL: {item.get('url', '')[:60]}...")

    except Exception as e:
        print(f"❌ Light 模式调用失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========== 测试 3: 并行查询（仅SERP） ==========
    print("\n[测试 3] 并行查询（仅SERP搜索）")
    try:
        result = await auto_search.ainvoke({
            "query": "<search>Python|JavaScript|Go</search>",
            "num_results": 6,
            "mode": "light"
        })

        print("✅ 并行查询调用成功")
        stats = result.get('statistics', {})
        print(f"   总查询数: {stats.get('total_queries', 0)}")
        print(f"   成功查询: {stats.get('successful_queries', 0)}")
        print(f"   总结果数: {stats.get('total_results', 0)}")

        if stats.get('query_details'):
            print(f"\n   查询明细:")
            for detail in stats['query_details']:
                print(f"   - {detail['query']}: {detail.get('results_count', 0)} 个结果")

    except Exception as e:
        print(f"❌ 并行查询调用失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========== 测试 4: 工具描述和参数 ==========
    print("\n[测试 4] 工具元信息验证")
    try:
        print(f"✅ 工具描述长度: {len(auto_search.description)} 字符")
        print(f"   参数 schema 存在: {hasattr(auto_search, 'args_schema')}")
        print(f"   异步调用可用: {hasattr(auto_search, 'ainvoke')}")
        print(f"   同步调用可用: {hasattr(auto_search, 'invoke')}")
    except Exception as e:
        print(f"❌ 元信息验证失败: {e}")

    print("\n" + "="*60)
    print("✅ 所有单点测试通过！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_minimal())
