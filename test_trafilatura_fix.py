"""
测试 Trafilatura signal 修复
验证不会再出现 "signal only works in main thread" 错误
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


async def test_signal_fix():
    """测试 Trafilatura signal 修复"""

    print("\n" + "="*60)
    print("Trafilatura Signal 修复验证")
    print("="*60)

    # 创建工具（启用内容抓取）
    auto_search = create_auto_search_tool(
        brightdata_api_key=os.environ["BRIGHTDATA_API_KEY"],
        auto_fetch_limit=3,  # 抓取前3个结果
        enable_smart_extraction=True
    )

    # 测试 Full 模式（会触发 Trafilatura）
    print("\n[测试] Full 模式内容抓取（应该不会有 signal 警告）")
    try:
        result = await auto_search.ainvoke({
            "query": "<search>Python programming</search>",
            "num_results": 3,
            "mode": "full"
        })

        print(f"\n✅ 测试完成")
        print(f"   成功: {result.get('success', False)}")
        print(f"   结果数: {len(result.get('results', []))}")

        stats = result.get('statistics', {})
        print(f"\n   统计:")
        print(f"      总结果: {stats.get('total_results', 0)}")
        print(f"      自动抓取: {stats.get('auto_fetched', 0)}")
        print(f"      抓取成功: {stats.get('fetch_success', 0)}")
        print(f"      SERP Fallback: {stats.get('auto_fetched', 0) - stats.get('fetch_success', 0)}")

        # 检查是否有 signal 错误
        has_signal_error = False
        for item in result.get('results', []):
            if 'fetch_error' in item:
                if 'signal only works in main thread' in item['fetch_error']:
                    has_signal_error = True
                    print(f"\n❌ 仍然存在 signal 错误: {item['url']}")

        if not has_signal_error:
            print(f"\n🎉 signal 问题已解决！没有发现 'signal only works in main thread' 错误")

        # 显示详细结果
        print(f"\n   结果详情:")
        for i, item in enumerate(result.get('results', [])[:3], 1):
            print(f"\n   [{i}] {item.get('title', 'No title')[:50]}...")
            print(f"       URL: {item.get('url', '')[:60]}...")

            if item.get('fetch_success'):
                print(f"       ✅ 内容抓取成功")
                print(f"          方法: {item.get('extraction_method', 'unknown')}")
                print(f"          长度: {item.get('content_length', 0)} 字符")
            elif item.get('is_serp_fallback'):
                print(f"       ⚠️  使用 SERP Fallback")
                print(f"          原因: {item.get('fetch_error', 'Unknown')[:50]}...")
            else:
                print(f"       ❌ 抓取失败")
                error = item.get('fetch_error', 'Unknown')
                print(f"          错误: {error[:80]}...")

                # 特别标记 signal 错误
                if 'signal only works in main thread' in error:
                    print(f"          ⚠️⚠️⚠️  SIGNAL ERROR DETECTED ⚠️⚠️⚠️")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(test_signal_fix())
