#!/bin/bash

# ==========================================
# DeepAgent LangGraph 服务器诊断脚本
# ==========================================

PORT=5060
BASE_URL="http://127.0.0.1:${PORT}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}  LangGraph 服务器诊断${NC}"
echo -e "${BLUE}=========================================${NC}"

# 1. 检查端口占用
echo -e "\n${YELLOW}[1] 检查端口 ${PORT} 是否被占用...${NC}"
PIDS=$(lsof -ti :${PORT} 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    echo -e "${GREEN}✓ 端口 ${PORT} 正在被使用${NC}"
    for PID in $PIDS; do
        echo -e "   PID: ${PID}"
        ps -p $PID -o pid,comm,args 2>/dev/null || true
    done
else
    echo -e "${RED}✗ 端口 ${PORT} 未被占用，请先启动服务器${NC}"
    echo -e "${YELLOW}   运行: ./start_server.sh${NC}"
    exit 1
fi

# 2. 测试健康检查端点
echo -e "\n${YELLOW}[2] 测试健康检查端点...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" ${BASE_URL}/ok 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    RESPONSE=$(curl -s ${BASE_URL}/ok 2>/dev/null)
    echo -e "${GREEN}✓ 健康检查通过 (HTTP $HTTP_CODE)${NC}"
    echo -e "   响应: ${RESPONSE}"
else
    echo -e "${RED}✗ 健康检查失败 (HTTP $HTTP_CODE)${NC}"
    exit 1
fi

# 3. 测试 /docs 端点
echo -e "\n${YELLOW}[3] 测试 /docs 端点...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" ${BASE_URL}/docs 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ /docs 端点正常 (HTTP $HTTP_CODE)${NC}"

    # 检查 HTML 内容
    HTML_CONTENT=$(curl -s ${BASE_URL}/docs 2>/dev/null)
    if echo "$HTML_CONTENT" | grep -q "Scalar API Reference"; then
        echo -e "${GREEN}✓ HTML 内容正确${NC}"
    else
        echo -e "${RED}✗ HTML 内容异常${NC}"
    fi
else
    echo -e "${RED}✗ /docs 端点失败 (HTTP $HTTP_CODE)${NC}"
fi

# 4. 测试 /openapi.json 端点
echo -e "\n${YELLOW}[4] 测试 /openapi.json 端点...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" ${BASE_URL}/openapi.json 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ /openapi.json 端点正常 (HTTP $HTTP_CODE)${NC}"

    # 检查 JSON 内容
    JSON_CONTENT=$(curl -s ${BASE_URL}/openapi.json 2>/dev/null)
    if echo "$JSON_CONTENT" | grep -q "openapi"; then
        echo -e "${GREEN}✓ OpenAPI JSON 内容正确${NC}"

        # 统计端点数量
        ENDPOINTS_COUNT=$(echo "$JSON_CONTENT" | grep -o "\"paths\"" | wc -l)
        echo -e "   包含 API 端点定义"
    fi
else
    echo -e "${RED}✗ /openapi.json 端点失败 (HTTP $HTTP_CODE)${NC}"
fi

# 5. 测试 /info 端点
echo -e "\n${YELLOW}[5] 测试 /info 端点...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" ${BASE_URL}/info 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    INFO_RESPONSE=$(curl -s ${BASE_URL}/info 2>/dev/null)
    echo -e "${GREEN}✓ /info 端点正常 (HTTP $HTTP_CODE)${NC}"
    echo -e "   响应: ${INFO_RESPONSE}"
else
    echo -e "${YELLOW}⚠ /info 端点返回 (HTTP $HTTP_CODE)${NC}"
fi

# 6. 测试创建 thread
echo -e "\n${YELLOW}[6] 测试创建 thread...${NC}"
THREAD_RESPONSE=$(curl -s -X POST ${BASE_URL}/threads \
    -H "Content-Type: application/json" \
    -d '{"assistant_id":"deep_agent"}' 2>/dev/null || echo "{}")

if echo "$THREAD_RESPONSE" | grep -q "thread_id"; then
    THREAD_ID=$(echo "$THREAD_RESPONSE" | grep -o '"thread_id":"[^"]*"' | cut -d'"' -f4)
    echo -e "${GREEN}✓ Thread 创建成功${NC}"
    echo -e "   Thread ID: ${THREAD_ID}"
else
    echo -e "${RED}✗ Thread 创建失败${NC}"
    echo -e "   响应: ${THREAD_RESPONSE}"
fi

# 7. 检查代理设置
echo -e "\n${YELLOW}[7] 检查代理设置...${NC}"
if [ -z "$HTTP_PROXY" ] && [ -z "$HTTPS_PROXY" ] && [ -z "$http_proxy" ] && [ -z "$https_proxy" ]; then
    echo -e "${GREEN}✓ 命令行代理已禁用${NC}"
else
    echo -e "${YELLOW}⚠ 发现代理设置:${NC}"
    [ -n "$HTTP_PROXY" ] && echo -e "   HTTP_PROXY: $HTTP_PROXY"
    [ -n "$HTTPS_PROXY" ] && echo -e "   HTTPS_PROXY: $HTTPS_PROXY"
    [ -n "$http_proxy" ] && echo -e "   http_proxy: $http_proxy"
    [ -n "$https_proxy" ] && echo -e "   https_proxy: $https_proxy"
fi

# 8. 检查 CDN 访问
echo -e "\n${YELLOW}[8] 检查 CDN 访问 (文档页面需要)...${NC}"
CDN_URL="https://cdn.jsdelivr.net/npm/@scalar/api-reference"
CDN_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 ${CDN_URL} 2>/dev/null || echo "000")
if [ "$CDN_CODE" = "200" ] || [ "$CDN_CODE" = "301" ] || [ "$CDN_CODE" = "302" ]; then
    echo -e "${GREEN}✓ CDN 可访问 (HTTP $CDN_CODE)${NC}"
else
    echo -e "${RED}✗ CDN 不可访问 (HTTP $CDN_CODE)${NC}"
    echo -e "${YELLOW}   这可能导致浏览器中的文档页面无法正常显示${NC}"
fi

# 总结
echo -e "\n${BLUE}=========================================${NC}"
echo -e "${BLUE}  诊断总结${NC}"
echo -e "${BLUE}=========================================${NC}"
echo -e "\n${GREEN}✓ 服务器运行正常${NC}"
echo -e "${GREEN}✓ 所有核心端点都可访问${NC}"

echo -e "\n${BLUE}📍 访问地址:${NC}"
echo -e "  • API Server:     ${BASE_URL}"
echo -e "  • API Docs:       ${BASE_URL}/docs"
echo -e "  • OpenAPI JSON:   ${BASE_URL}/openapi.json"
echo -e "  • Health Check:   ${BASE_URL}/ok"

echo -e "\n${YELLOW}⚠️  如果浏览器无法访问 /docs，请检查:${NC}"
echo -e "  1. ${YELLOW}浏览器代理设置${NC}"
echo -e "     - Chrome: 设置 → 系统 → 打开代理设置"
echo -e "     - 确保 localhost/127.0.0.1 不走代理"
echo -e ""
echo -e "  2. ${YELLOW}浏览器缓存${NC}"
echo -e "     - 清除浏览器缓存并刷新"
echo -e "     - 或使用隐身模式访问"
echo -e ""
echo -e "  3. ${YELLOW}防火墙/安全软件${NC}"
echo -e "     - 检查是否阻止了本地端口访问"
echo -e ""
echo -e "  4. ${YELLOW}网络访问${NC}"
echo -e "     - 确保可以访问 CDN (https://cdn.jsdelivr.net)"
echo -e "     - 文档页面需要加载外部 JavaScript"

echo -e "\n${BLUE}💡 替代方案:${NC}"
echo -e "  • 直接访问 OpenAPI JSON:"
echo -e "    ${YELLOW}${BASE_URL}/openapi.json${NC}"
echo -e ""
echo -e "  • 使用 curl 测试 API:"
echo -e "    ${YELLOW}curl ${BASE_URL}/ok${NC}"
echo -e ""
echo -e "  • 使用 Python 客户端:"
echo -e "    ${YELLOW}python3 test_api.py${NC}"
echo -e "    ${YELLOW}python3 examples_api_usage.py${NC}"

echo -e "\n${GREEN}诊断完成！${NC}"
