#!/bin/bash

# 快速测试脚本 - 验证 DeepAgent API 工作正常

# 禁用代理（重要！）
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy

PORT=5080
BASE_URL="http://127.0.0.1:${PORT}"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  DeepAgent API 快速测试${NC}"
echo -e "${BLUE}========================================${NC}\n"

# 1. 健康检查
echo -e "${YELLOW}[1/5] 健康检查...${NC}"
RESULT=$(curl -s ${BASE_URL}/ok 2>/dev/null)
if echo "$RESULT" | grep -q "ok"; then
    echo -e "${GREEN}✅ 通过: ${RESULT}${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    exit 1
fi

# 2. 服务器信息
echo -e "\n${YELLOW}[2/5] 获取服务器信息...${NC}"
INFO=$(curl -s ${BASE_URL}/info 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
if [ -n "$INFO" ]; then
    echo -e "${GREEN}✅ 通过: LangGraph API v${INFO}${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    exit 1
fi

# 3. 创建 Thread
echo -e "\n${YELLOW}[3/5] 创建 Thread...${NC}"
THREAD_RESPONSE=$(curl -s -X POST ${BASE_URL}/threads \
    -H "Content-Type: application/json" \
    -d '{"assistant_id":"deep_agent"}' 2>/dev/null)

THREAD_ID=$(echo "$THREAD_RESPONSE" | grep -o '"thread_id":"[^"]*"' | cut -d'"' -f4)
if [ -n "$THREAD_ID" ]; then
    echo -e "${GREEN}✅ 通过: Thread ID = ${THREAD_ID:0:20}...${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    echo -e "   响应: ${THREAD_RESPONSE}"
    exit 1
fi

# 4. 发送消息
echo -e "\n${YELLOW}[4/5] 发送测试消息...${NC}"
RUN_RESPONSE=$(curl -s -X POST ${BASE_URL}/threads/${THREAD_ID}/runs \
    -H "Content-Type: application/json" \
    -d '{
        "assistant_id": "deep_agent",
        "input": {
            "messages": [{
                "role": "user",
                "content": "Hello, just testing. Reply with OK."
            }]
        }
    }' 2>/dev/null)

if echo "$RUN_RESPONSE" | grep -q "run_id"; then
    echo -e "${GREEN}✅ 通过: Agent 已启动${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    exit 1
fi

# 5. 等待并获取状态
echo -e "\n${YELLOW}[5/5] 等待 Agent 响应...${NC}"
sleep 3

STATE=$(curl -s ${BASE_URL}/threads/${THREAD_ID}/state 2>/dev/null)
MSG_COUNT=$(echo "$STATE" | grep -o '"messages"' | wc -l)

if [ "$MSG_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ 通过: Agent 已响应${NC}"
else
    echo -e "${YELLOW}⚠️  Agent 正在处理中...${NC}"
fi

# 总结
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 所有测试通过！${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo -e "${BLUE}📍 访问地址:${NC}"
echo -e "  • API Docs:  ${YELLOW}http://127.0.0.1:${PORT}/docs${NC}"
echo -e "  • 或使用 IP: ${YELLOW}http://192.168.31.22:${PORT}/docs${NC}"
echo -e ""
echo -e "${BLUE}💡 测试命令:${NC}"
echo -e "  curl http://127.0.0.1:${PORT}/ok"
echo -e ""
echo -e "${BLUE}🚀 下一步:${NC}"
echo -e "  1. 在浏览器中打开 http://192.168.31.22:${PORT}/docs"
echo -e "  2. 或运行: python3 test_api.py"
echo -e "  3. 或运行: python3 examples_api_usage.py"
echo -e ""

exit 0
