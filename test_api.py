"""
测试 LangGraph API 服务器
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:5060"

def test_api():
    print("=" * 60)
    print("LangGraph API 完整流程测试")
    print("=" * 60)

    # 1. 检查服务器健康状态
    print("\n[1] 检查服务器健康状态...")
    try:
        response = requests.get(f"{BASE_URL}/ok")
        print(f"✅ 服务器健康: {response.json()}")
    except Exception as e:
        print(f"❌ 服务器连接失败: {e}")
        return

    # 2. 获取服务器信息
    print("\n[2] 获取服务器信息...")
    try:
        response = requests.get(f"{BASE_URL}/info")
        info = response.json()
        print(f"✅ 服务器信息:")
        print(f"   版本: {info['version']}")
        print(f"   LangGraph 版本: {info['langgraph_py_version']}")
    except Exception as e:
        print(f"❌ 获取信息失败: {e}")

    # 3. 创建 Thread
    print("\n[3] 创建 Thread...")
    try:
        response = requests.post(
            f"{BASE_URL}/threads",
            json={
                "assistant_id": "deep_agent",
                "metadata": {"test": "api_test"}
            }
        )
        thread_data = response.json()
        thread_id = thread_data["thread_id"]
        print(f"✅ Thread 创建成功!")
        print(f"   Thread ID: {thread_id}")
    except Exception as e:
        print(f"❌ Thread 创建失败: {e}")
        print(f"   响应: {response.text if 'response' in locals() else 'N/A'}")
        return

    # 4. 发送消息并运行 Agent (简单测试，不使用搜索)
    print("\n[4] 发送消息给 Agent...")
    try:
        response = requests.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            json={
                "assistant_id": "deep_agent",
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": "你好，请简单介绍一下你自己的功能"
                    }]
                }
            },
            stream=False
        )

        if response.status_code == 200:
            print(f"✅ Agent 运行成功!")

            # 等待一下让 agent 完成
            time.sleep(2)

            # 获取 thread 状态
            state_response = requests.get(f"{BASE_URL}/threads/{thread_id}/state")
            if state_response.status_code == 200:
                state = state_response.json()
                messages = state.get('values', {}).get('messages', [])

                print(f"\n   消息数量: {len(messages)}")

                # 显示最后的 AI 响应
                for msg in reversed(messages):
                    if isinstance(msg, dict):
                        msg_type = msg.get('type', 'unknown')
                        if msg_type == 'ai':
                            content = msg.get('content', '')
                            print(f"\n   AI 回复:")
                            print(f"   {content[:300]}...")
                            break
                        elif hasattr(msg, 'type'):
                            if msg.type == 'ai':
                                print(f"\n   AI 回复:")
                                print(f"   {msg.content[:300]}...")
                                break
        else:
            print(f"❌ Agent 运行失败")
            print(f"   状态码: {response.status_code}")
            print(f"   响应: {response.text[:500]}")

    except Exception as e:
        print(f"❌ 消息发送失败: {e}")
        import traceback
        traceback.print_exc()

    # 5. 测试搜索功能 (可选)
    print("\n" + "=" * 60)
    print("[5] 测试搜索功能 (Light 模式)...")
    print("=" * 60)

    try:
        # 创建新的 thread
        response = requests.post(
            f"{BASE_URL}/threads",
            json={"assistant_id": "deep_agent"}
        )
        search_thread_id = response.json()["thread_id"]
        print(f"✅ 搜索 Thread 创建: {search_thread_id}")

        # 发送搜索请求
        print("\n   发送搜索请求: 'Search for Python asyncio'...")
        response = requests.post(
            f"{BASE_URL}/threads/{search_thread_id}/runs",
            json={
                "assistant_id": "deep_agent",
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": "Search for Python asyncio using light mode"
                    }]
                }
            }
        )

        if response.status_code == 200:
            print(f"✅ 搜索请求已发送")
            print(f"   注意: 实际搜索可能需要几秒钟...")
            print(f"   可以通过 GET /threads/{search_thread_id}/state 查看结果")

    except Exception as e:
        print(f"⚠️  搜索测试跳过: {e}")

    print("\n" + "=" * 60)
    print("✅ API 测试完成!")
    print("=" * 60)
    print(f"\n💡 提示:")
    print(f"   - API 文档: {BASE_URL}/docs")
    print(f"   - Studio UI: https://smith.langchain.com/studio/?baseUrl={BASE_URL}")
    print(f"   - Thread ID (简单测试): {thread_id}")
    if 'search_thread_id' in locals():
        print(f"   - Thread ID (搜索测试): {search_thread_id}")

if __name__ == "__main__":
    test_api()
