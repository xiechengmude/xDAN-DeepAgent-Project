"""
搜索工具对比测试
===================
对比 Tavily 和 Auto Search Tool 的性能和结果质量
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入搜索工具
from tavily import TavilyClient

# 直接导入 auto_search_tool 模块，避免通过 deepagents
import importlib.util
auto_search_spec = importlib.util.spec_from_file_location(
    "auto_search_tool",
    str(project_root / "src" / "deepagents" / "tools" / "auto_search_tool.py")
)
auto_search_module = importlib.util.module_from_spec(auto_search_spec)
auto_search_spec.loader.exec_module(auto_search_module)
create_auto_search_tool = auto_search_module.create_auto_search_tool


class SearchComparison:
    """搜索工具对比测试类"""

    def __init__(self):
        # 初始化 Tavily
        self.tavily_client = TavilyClient(api_key=os.environ["TAVILY_KEY"])

        # 初始化 Auto Search Tool
        self.auto_search = create_auto_search_tool(
            brightdata_api_key=os.environ["BRIGHTDATA_API_KEY"],
            firecrawl_api_key=os.environ.get("FIRECRAWL_API_KEY"),
            auto_fetch_limit=5,
            enable_smart_extraction=True,
            confidence_threshold=0.7
        )

        print("✅ 搜索工具初始化完成")
        print(f"   - Tavily API Key: {os.environ['TAVILY_KEY'][:20]}...")
        print(f"   - BrightData API Key: {os.environ['BRIGHTDATA_API_KEY'][:20]}...")

    def test_tavily(self, query: str, max_results: int = 5):
        """测试 Tavily 搜索"""
        print(f"\n{'='*60}")
        print(f"🔍 Tavily 搜索: {query}")
        print(f"{'='*60}")

        start_time = datetime.now()

        try:
            result = self.tavily_client.search(
                query=query,
                max_results=max_results,
                include_raw_content=False,
                topic="general"
            )

            elapsed = (datetime.now() - start_time).total_seconds()

            print(f"\n⏱️  耗时: {elapsed:.2f}秒")
            print(f"📊 结果数量: {len(result.get('results', []))}")

            # 显示结果摘要
            for i, item in enumerate(result.get('results', [])[:3], 1):
                print(f"\n[{i}] {item.get('title', 'No title')}")
                print(f"    URL: {item.get('url', 'No URL')}")
                print(f"    Score: {item.get('score', 0):.3f}")
                snippet = item.get('content', '')[:150]
                print(f"    Snippet: {snippet}...")

            return {
                'success': True,
                'tool': 'tavily',
                'query': query,
                'elapsed': elapsed,
                'results_count': len(result.get('results', [])),
                'results': result.get('results', []),
                'raw_response': result
            }

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n❌ Tavily 搜索失败: {str(e)}")
            return {
                'success': False,
                'tool': 'tavily',
                'query': query,
                'error': str(e),
                'elapsed': elapsed
            }

    async def test_auto_search(self, query: str, num_results: int = 5, mode: str = "full"):
        """测试 Auto Search Tool"""
        print(f"\n{'='*60}")
        print(f"🔍 Auto Search ({mode} 模式): {query}")
        print(f"{'='*60}")

        start_time = datetime.now()

        try:
            # 使用 <search> 标签包装查询
            formatted_query = f"<search>{query}</search>"

            result = await self.auto_search.ainvoke({
                "query": formatted_query,
                "num_results": num_results,
                "mode": mode
            })

            elapsed = (datetime.now() - start_time).total_seconds()

            print(f"\n⏱️  耗时: {elapsed:.2f}秒")
            print(f"📊 结果数量: {len(result.get('results', []))}")

            stats = result.get('statistics', {})
            print(f"📈 统计:")
            print(f"   - 总结果: {stats.get('total_results', 0)}")
            print(f"   - 自动抓取: {stats.get('auto_fetched', 0)}")
            print(f"   - 抓取成功: {stats.get('fetch_success', 0)}")
            print(f"   - PDF文档: {stats.get('pdf_count', 0)}")

            # 显示结果摘要
            for i, item in enumerate(result.get('results', [])[:3], 1):
                print(f"\n[{i}] {item.get('title', 'No title')}")
                print(f"    URL: {item.get('url', 'No URL')}")
                print(f"    Position: {item.get('position', 0)}")

                if item.get('fetch_success'):
                    print(f"    ✅ 内容抓取成功")
                    print(f"       - 长度: {item.get('content_length', 0)} 字符")
                    print(f"       - Tokens: {item.get('estimated_tokens', 0)}")
                    print(f"       - 方法: {item.get('extraction_method', 'unknown')}")
                    print(f"       - PDF: {'是' if item.get('is_pdf') else '否'}")

                    # 显示内容预览
                    content = item.get('content', '')
                    preview = content[:150] + '...' if len(content) > 150 else content
                    print(f"       - 预览: {preview}")
                else:
                    print(f"    ❌ 内容抓取失败: {item.get('fetch_error', 'Unknown')}")
                    snippet = item.get('snippet', '')[:150]
                    print(f"       - Snippet: {snippet}...")

            return {
                'success': True,
                'tool': 'auto_search',
                'query': query,
                'mode': mode,
                'elapsed': elapsed,
                'results_count': len(result.get('results', [])),
                'statistics': stats,
                'results': result.get('results', []),
                'raw_response': result
            }

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n❌ Auto Search 失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'tool': 'auto_search',
                'query': query,
                'mode': mode,
                'error': str(e),
                'elapsed': elapsed
            }

    async def test_parallel_search(self, queries: list[str], num_results: int = 10):
        """测试并行搜索功能（Auto Search 独有）"""
        print(f"\n{'='*60}")
        print(f"🚀 Auto Search 并行搜索测试")
        print(f"{'='*60}")

        # 构建并行查询
        parallel_query = "<search>" + "|".join(queries) + "</search>"
        print(f"查询: {parallel_query}")

        start_time = datetime.now()

        try:
            result = await self.auto_search.ainvoke({
                "query": parallel_query,
                "num_results": num_results,
                "mode": "light"  # 并行搜索用 light 模式更快
            })

            elapsed = (datetime.now() - start_time).total_seconds()

            print(f"\n⏱️  耗时: {elapsed:.2f}秒")
            print(f"🔄 并行查询: {len(queries)} 个")

            stats = result.get('statistics', {})
            print(f"📈 统计:")
            print(f"   - 总查询: {stats.get('total_queries', 0)}")
            print(f"   - 成功查询: {stats.get('successful_queries', 0)}")
            print(f"   - 总结果: {stats.get('total_results', 0)}")

            # 显示每个查询的结果
            for detail in stats.get('query_details', []):
                print(f"\n   查询 [{detail['query_index']}]: {detail['query']}")
                print(f"      - 成功: {'✅' if detail['success'] else '❌'}")
                if detail['success']:
                    print(f"      - 结果数: {detail.get('results_count', 0)}")
                else:
                    print(f"      - 错误: {detail.get('error', 'Unknown')}")

            return {
                'success': True,
                'tool': 'auto_search_parallel',
                'queries': queries,
                'elapsed': elapsed,
                'statistics': stats,
                'raw_response': result
            }

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n❌ 并行搜索失败: {str(e)}")
            return {
                'success': False,
                'tool': 'auto_search_parallel',
                'queries': queries,
                'error': str(e),
                'elapsed': elapsed
            }

    def compare_results(self, tavily_result, auto_search_result):
        """对比两个工具的结果"""
        print(f"\n{'='*60}")
        print(f"📊 结果对比")
        print(f"{'='*60}")

        if tavily_result['success'] and auto_search_result['success']:
            print(f"\n⏱️  性能对比:")
            print(f"   Tavily:      {tavily_result['elapsed']:.2f}秒")
            print(f"   Auto Search: {auto_search_result['elapsed']:.2f}秒")
            print(f"   差异:        {auto_search_result['elapsed'] - tavily_result['elapsed']:.2f}秒")

            print(f"\n📊 结果数量:")
            print(f"   Tavily:      {tavily_result['results_count']} 个")
            print(f"   Auto Search: {auto_search_result['results_count']} 个")

            print(f"\n✨ 功能对比:")
            print(f"   PDF 解析:")
            print(f"      Tavily:      ❌")
            print(f"      Auto Search: ✅ ({auto_search_result['statistics'].get('pdf_count', 0)} 个)")

            print(f"   完整内容抓取:")
            print(f"      Tavily:      ❌ (仅 snippet)")
            print(f"      Auto Search: ✅ ({auto_search_result['statistics'].get('fetch_success', 0)}/{auto_search_result['statistics'].get('auto_fetched', 0)} 成功)")

            print(f"   并行搜索:")
            print(f"      Tavily:      ❌")
            print(f"      Auto Search: ✅")

            # URL 重叠分析
            tavily_urls = set(r.get('url', '') for r in tavily_result['results'])
            auto_urls = set(r.get('url', '') for r in auto_search_result['results'])
            overlap = tavily_urls & auto_urls

            print(f"\n🔗 URL 重叠:")
            print(f"   共同 URL: {len(overlap)} 个")
            if overlap:
                print(f"   重叠率: {len(overlap)/min(len(tavily_urls), len(auto_urls))*100:.1f}%")
                print(f"   重叠 URL:")
                for url in list(overlap)[:3]:
                    print(f"      - {url}")
        else:
            if not tavily_result['success']:
                print(f"\n❌ Tavily 失败: {tavily_result.get('error', 'Unknown')}")
            if not auto_search_result['success']:
                print(f"\n❌ Auto Search 失败: {auto_search_result.get('error', 'Unknown')}")


async def main():
    """主测试流程"""
    print(f"\n{'#'*60}")
    print(f"# 搜索工具对比测试")
    print(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # 创建测试实例
    comparison = SearchComparison()

    # 测试查询
    test_queries = [
        "LangGraph architecture and features",
        "RAG optimization techniques 2024",
        "DeepSeek AI model capabilities"
    ]

    # 测试 1: 单一查询对比
    print(f"\n\n{'#'*60}")
    print(f"# 测试 1: 单一查询对比")
    print(f"{'#'*60}")

    query = test_queries[0]

    # Tavily 测试
    tavily_result = comparison.test_tavily(query, max_results=5)

    # Auto Search Light 模式测试
    auto_light_result = await comparison.test_auto_search(query, num_results=5, mode="light")

    # Auto Search Full 模式测试
    auto_full_result = await comparison.test_auto_search(query, num_results=5, mode="full")

    # 对比结果
    if tavily_result['success'] and auto_full_result['success']:
        comparison.compare_results(tavily_result, auto_full_result)

    # 测试 2: 并行搜索（Auto Search 独有功能）
    print(f"\n\n{'#'*60}")
    print(f"# 测试 2: 并行搜索 (Auto Search 独有)")
    print(f"{'#'*60}")

    parallel_queries = test_queries
    parallel_result = await comparison.test_parallel_search(parallel_queries, num_results=12)

    if parallel_result['success']:
        print(f"\n✅ 并行搜索成功完成")
        print(f"   相比串行执行 Tavily {len(parallel_queries)} 次:")
        estimated_tavily_time = tavily_result['elapsed'] * len(parallel_queries)
        time_saved = estimated_tavily_time - parallel_result['elapsed']
        print(f"   估算 Tavily 串行时间: {estimated_tavily_time:.2f}秒")
        print(f"   Auto Search 并行时间: {parallel_result['elapsed']:.2f}秒")
        print(f"   节省时间: {time_saved:.2f}秒 ({time_saved/estimated_tavily_time*100:.1f}%)")

    # 测试 3: 内容质量对比
    print(f"\n\n{'#'*60}")
    print(f"# 测试 3: 内容质量对比")
    print(f"{'#'*60}")

    if tavily_result['success'] and auto_full_result['success']:
        print(f"\nTavily 内容示例 (第1个结果):")
        tavily_first = tavily_result['results'][0] if tavily_result['results'] else {}
        print(f"   Title: {tavily_first.get('title', 'N/A')[:60]}...")
        print(f"   Content: {tavily_first.get('content', 'N/A')[:200]}...")
        print(f"   Content Length: {len(tavily_first.get('content', ''))} 字符")

        print(f"\nAuto Search 内容示例 (第1个结果):")
        auto_first = auto_full_result['results'][0] if auto_full_result['results'] else {}
        print(f"   Title: {auto_first.get('title', 'N/A')[:60]}...")
        if auto_first.get('fetch_success'):
            content = auto_first.get('content', 'N/A')
            print(f"   Content: {content[:200]}...")
            print(f"   Content Length: {len(content)} 字符")
            print(f"   Estimated Tokens: {auto_first.get('estimated_tokens', 0)}")
            print(f"   Extraction Method: {auto_first.get('extraction_method', 'unknown')}")
        else:
            print(f"   ❌ 抓取失败")

    # 保存测试结果
    results_dir = project_root / "tests" / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = results_dir / f"search_comparison_{timestamp}.json"

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'test_queries': test_queries,
            'tavily_result': {k: v for k, v in tavily_result.items() if k != 'raw_response'},
            'auto_light_result': {k: v for k, v in auto_light_result.items() if k != 'raw_response'},
            'auto_full_result': {k: v for k, v in auto_full_result.items() if k != 'raw_response'},
            'parallel_result': {k: v for k, v in parallel_result.items() if k != 'raw_response'},
        }, f, indent=2, ensure_ascii=False)

    print(f"\n\n{'#'*60}")
    print(f"# 测试完成")
    print(f"{'#'*60}")
    print(f"\n📁 结果已保存到: {results_file}")

    # 总结
    print(f"\n📊 总结:")
    print(f"   ✅ Tavily: 速度快，集成简单，但功能有限")
    print(f"   ✅ Auto Search (Light): 速度接近 Tavily，支持更多功能")
    print(f"   ✅ Auto Search (Full): 深度内容抓取，PDF 解析，完全自主")
    print(f"   🚀 Auto Search (Parallel): 独有功能，显著提升效率")

    print(f"\n💡 建议:")
    print(f"   - 快速预览: 使用 Tavily 或 Auto Search Light 模式")
    print(f"   - 深度研究: 使用 Auto Search Full 模式")
    print(f"   - 多主题研究: 使用 Auto Search 并行搜索")
    print(f"   - 需要 PDF: 必须使用 Auto Search")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())
