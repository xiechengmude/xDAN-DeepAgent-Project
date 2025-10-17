"""
简化的搜索工具对比测试
直接在项目根目录运行
"""

import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加 src 到路径
sys.path.insert(0, "src")

# 导入
from tavily import TavilyClient
from deepagents.auto_search_tool.auto_search_tool import create_auto_search_tool


async def test_comparison():
    """运行对比测试"""

    print("\n" + "="*60)
    print("搜索工具对比测试")
    print("="*60)

    # 测试查询
    query = "LangGraph architecture and features 2024"

    # ========== Tavily 测试 ==========
    print(f"\n{'#'*60}")
    print("# 测试 1: Tavily")
    print(f"{'#'*60}")
    print(f"查询: {query}")

    tavily_client = TavilyClient(api_key=os.environ["TAVILY_KEY"])

    tavily_start = datetime.now()
    try:
        tavily_result = tavily_client.search(
            query=query,
            max_results=5,
            include_raw_content=False,
            topic="general"
        )
        tavily_elapsed = (datetime.now() - tavily_start).total_seconds()

        print(f"\n✅ Tavily 成功")
        print(f"   耗时: {tavily_elapsed:.2f}秒")
        print(f"   结果数: {len(tavily_result.get('results', []))}")

        for i, item in enumerate(tavily_result.get('results', [])[:3], 1):
            print(f"\n   [{i}] {item.get('title', 'No title')[:60]}...")
            print(f"       URL: {item.get('url', '')[:70]}...")
            print(f"       Score: {item.get('score', 0):.3f}")
            content = item.get('content', '')
            print(f"       Content: {len(content)} 字符")
            print(f"       Preview: {content[:100]}...")

    except Exception as e:
        tavily_elapsed = (datetime.now() - tavily_start).total_seconds()
        print(f"\n❌ Tavily 失败: {str(e)}")
        tavily_result = None

    # ========== Auto Search Light 模式测试 ==========
    print(f"\n{'#'*60}")
    print("# 测试 2: Auto Search (Light 模式)")
    print(f"{'#'*60}")
    print(f"查询: {query}")

    auto_search = create_auto_search_tool(
        brightdata_api_key=os.environ["BRIGHTDATA_API_KEY"],
        auto_fetch_limit=5,
        enable_smart_extraction=True
    )

    auto_light_start = datetime.now()
    try:
        auto_light_result = await auto_search.ainvoke({
            "query": f"<search>{query}</search>",
            "num_results": 5,
            "mode": "light"
        })
        auto_light_elapsed = (datetime.now() - auto_light_start).total_seconds()

        print(f"\n✅ Auto Search (Light) 成功")
        print(f"   耗时: {auto_light_elapsed:.2f}秒")
        print(f"   结果数: {len(auto_light_result.get('results', []))}")

        stats = auto_light_result.get('statistics', {})
        print(f"   统计: {stats}")

        for i, item in enumerate(auto_light_result.get('results', [])[:3], 1):
            print(f"\n   [{i}] {item.get('title', 'No title')[:60]}...")
            print(f"       URL: {item.get('url', '')[:70]}...")
            print(f"       Snippet: {len(item.get('snippet', '') or '')} 字符")
            content = item.get('content', '') or ''
            print(f"       Content: {content[:100]}...")

    except Exception as e:
        auto_light_elapsed = (datetime.now() - auto_light_start).total_seconds()
        print(f"\n❌ Auto Search (Light) 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        auto_light_result = None

    # ========== Auto Search Full 模式测试 ==========
    print(f"\n{'#'*60}")
    print("# 测试 3: Auto Search (Full 模式)")
    print(f"{'#'*60}")
    print(f"查询: {query}")

    auto_full_start = datetime.now()
    try:
        auto_full_result = await auto_search.ainvoke({
            "query": f"<search>{query}</search>",
            "num_results": 5,
            "mode": "full"
        })
        auto_full_elapsed = (datetime.now() - auto_full_start).total_seconds()

        print(f"\n✅ Auto Search (Full) 成功")
        print(f"   耗时: {auto_full_elapsed:.2f}秒")
        print(f"   结果数: {len(auto_full_result.get('results', []))}")

        stats = auto_full_result.get('statistics', {})
        print(f"   统计:")
        print(f"      - 总结果: {stats.get('total_results', 0)}")
        print(f"      - 自动抓取: {stats.get('auto_fetched', 0)}")
        print(f"      - 抓取成功: {stats.get('fetch_success', 0)}")
        print(f"      - PDF文档: {stats.get('pdf_count', 0)}")

        for i, item in enumerate(auto_full_result.get('results', [])[:3], 1):
            print(f"\n   [{i}] {item.get('title', 'No title')[:60]}...")
            print(f"       URL: {item.get('url', '')[:70]}...")

            if item.get('fetch_success'):
                print(f"       ✅ 内容抓取成功")
                print(f"          长度: {item.get('content_length', 0)} 字符")
                print(f"          Tokens: {item.get('estimated_tokens', 0)}")
                print(f"          方法: {item.get('extraction_method', 'unknown')}")
                print(f"          PDF: {'是' if item.get('is_pdf') else '否'}")
                content = item.get('content', '')
                print(f"          预览: {content[:150]}...")
            else:
                print(f"       ❌ 抓取失败: {item.get('fetch_error', 'Unknown')}")

    except Exception as e:
        auto_full_elapsed = (datetime.now() - auto_full_start).total_seconds()
        print(f"\n❌ Auto Search (Full) 失败: {str(e)}")
        import traceback
        traceback.print_exc()
        auto_full_result = None

    # ========== 并行搜索测试 ==========
    print(f"\n{'#'*60}")
    print("# 测试 4: Auto Search 并行搜索")
    print(f"{'#'*60}")

    parallel_queries = [
        "LangGraph architecture",
        "LangChain agents",
        "RAG optimization 2024"
    ]
    parallel_query = "<search>" + "|".join(parallel_queries) + "</search>"
    print(f"并行查询: {parallel_queries}")

    parallel_start = datetime.now()
    try:
        parallel_result = await auto_search.ainvoke({
            "query": parallel_query,
            "num_results": 12,
            "mode": "light"
        })
        parallel_elapsed = (datetime.now() - parallel_start).total_seconds()

        print(f"\n✅ 并行搜索成功")
        print(f"   耗时: {parallel_elapsed:.2f}秒")

        stats = parallel_result.get('statistics', {})
        print(f"   统计:")
        print(f"      - 总查询: {stats.get('total_queries', 0)}")
        print(f"      - 成功查询: {stats.get('successful_queries', 0)}")
        print(f"      - 总结果: {stats.get('total_results', 0)}")

        for detail in stats.get('query_details', []):
            print(f"\n   [{detail['query_index']}] {detail['query']}")
            print(f"       成功: {'✅' if detail['success'] else '❌'}")
            if detail['success']:
                print(f"       结果数: {detail.get('results_count', 0)}")

        # 计算性能提升
        if tavily_result:
            estimated_serial = tavily_elapsed * len(parallel_queries)
            time_saved = estimated_serial - parallel_elapsed
            print(f"\n   性能对比:")
            print(f"      Tavily 串行时间估算: {estimated_serial:.2f}秒")
            print(f"      Auto Search 并行: {parallel_elapsed:.2f}秒")
            print(f"      节省时间: {time_saved:.2f}秒 ({time_saved/estimated_serial*100:.1f}%)")

    except Exception as e:
        parallel_elapsed = (datetime.now() - parallel_start).total_seconds()
        print(f"\n❌ 并行搜索失败: {str(e)}")
        import traceback
        traceback.print_exc()

    # ========== 总结对比 ==========
    print(f"\n{'='*60}")
    print("总结对比")
    print(f"{'='*60}")

    if tavily_result and auto_full_result:
        print(f"\n⏱️  性能:")
        print(f"   Tavily:            {tavily_elapsed:.2f}秒")
        print(f"   Auto Search Light: {auto_light_elapsed:.2f}秒")
        print(f"   Auto Search Full:  {auto_full_elapsed:.2f}秒")

        print(f"\n✨ 功能:")
        print(f"   PDF 支持:")
        print(f"      Tavily:      ❌")
        print(f"      Auto Search: ✅ ({auto_full_result['statistics'].get('pdf_count', 0)} 个)")

        print(f"   完整内容:")
        print(f"      Tavily:      ❌ (仅snippet)")
        print(f"      Auto Search: ✅ ({auto_full_result['statistics'].get('fetch_success', 0)}/{auto_full_result['statistics'].get('auto_fetched', 0)})")

        print(f"   并行搜索:")
        print(f"      Tavily:      ❌")
        print(f"      Auto Search: ✅")

        print(f"\n💡 建议:")
        print(f"   - 快速预览: Tavily 或 Auto Search Light")
        print(f"   - 深度研究: Auto Search Full")
        print(f"   - 多主题: Auto Search 并行")
        print(f"   - PDF 文档: Auto Search Full")

    print(f"\n✅ 测试完成!")


if __name__ == "__main__":
    asyncio.run(test_comparison())
