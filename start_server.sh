#!/bin/bash

# ==========================================
# DeepAgent LangGraph 服务器启动脚本
# ==========================================
# 功能：
# 1. 禁用本地代理
# 2. 清理占用 5080 端口的旧进程
# 3. 启动 LangGraph 开发服务器
# 4. 保留日志到文件
# ==========================================

set -e  # 遇到错误立即退出

# 配置
PORT=5080
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/langgraph_dev_$(date +%Y%m%d_%H%M%S).log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}  DeepAgent LangGraph 服务器启动${NC}"
echo -e "${BLUE}=========================================${NC}"

# 1. 禁用本地代理
echo -e "\n${YELLOW}[1/4] 禁用本地代理...${NC}"
unset HTTP_PROXY
unset HTTPS_PROXY
unset http_proxy
unset https_proxy
echo -e "${GREEN}✓ 代理已禁用${NC}"

# 2. 创建日志目录
echo -e "\n${YELLOW}[2/4] 创建日志目录...${NC}"
mkdir -p "${LOG_DIR}"
echo -e "${GREEN}✓ 日志目录: ${LOG_DIR}${NC}"
echo -e "${GREEN}✓ 日志文件: ${LOG_FILE}${NC}"

# 3. 清理占用端口的旧进程
echo -e "\n${YELLOW}[3/4] 检查并清理 ${PORT} 端口...${NC}"

# 查找占用端口的进程
PIDS=$(lsof -ti :${PORT} 2>/dev/null || true)

if [ -n "$PIDS" ]; then
    echo -e "${YELLOW}发现以下进程占用端口 ${PORT}:${NC}"
    for PID in $PIDS; do
        # 显示进程信息
        ps -p $PID -o pid,comm,args 2>/dev/null || true
    done

    echo -e "${YELLOW}正在终止这些进程...${NC}"
    for PID in $PIDS; do
        kill -9 $PID 2>/dev/null || true
        echo -e "${GREEN}✓ 已终止进程 PID: $PID${NC}"
    done

    # 等待端口释放
    sleep 2
    echo -e "${GREEN}✓ 端口 ${PORT} 已释放${NC}"
else
    echo -e "${GREEN}✓ 端口 ${PORT} 未被占用${NC}"
fi

# 4. 启动 LangGraph 服务器
echo -e "\n${YELLOW}[4/4] 启动 LangGraph 服务器...${NC}"
echo -e "${BLUE}端口: ${PORT}${NC}"
echo -e "${BLUE}日志: ${LOG_FILE}${NC}"
echo -e "${BLUE}后台运行，日志实时写入文件${NC}"

# 启动服务器（后台运行）
nohup uv run langgraph dev --host 0.0.0.0 --port ${PORT} > "${LOG_FILE}" 2>&1 &
SERVER_PID=$!

# 等待服务器启动
echo -e "\n${YELLOW}等待服务器启动...${NC}"
sleep 5

# 检查服务器是否成功启动
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo -e "\n${GREEN}=========================================${NC}"
    echo -e "${GREEN}  ✓ 服务器启动成功！${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}进程 PID: ${SERVER_PID}${NC}"
    echo -e "${GREEN}端口: ${PORT}${NC}"
    echo -e "${GREEN}日志文件: ${LOG_FILE}${NC}"
    echo -e "\n${BLUE}📍 访问地址:${NC}"
    echo -e "  • API Server:     ${BLUE}http://127.0.0.1:${PORT}${NC}"
    echo -e "  • API Docs:       ${BLUE}http://127.0.0.1:${PORT}/docs${NC}"
    echo -e "  • Health Check:   ${BLUE}http://127.0.0.1:${PORT}/ok${NC}"
    echo -e "  • Studio UI:      ${BLUE}https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:${PORT}${NC}"

    echo -e "\n${BLUE}📝 常用命令:${NC}"
    echo -e "  • 查看实时日志:   ${YELLOW}tail -f ${LOG_FILE}${NC}"
    echo -e "  • 查看进程状态:   ${YELLOW}ps -p ${SERVER_PID}${NC}"
    echo -e "  • 停止服务器:     ${YELLOW}kill ${SERVER_PID}${NC}"
    echo -e "  • 健康检查:       ${YELLOW}curl http://127.0.0.1:${PORT}/ok${NC}"

    # 将 PID 写入文件，方便后续停止
    echo $SERVER_PID > "${LOG_DIR}/server.pid"
    echo -e "\n${GREEN}PID 已保存到: ${LOG_DIR}/server.pid${NC}"

    # 显示最近的日志
    echo -e "\n${BLUE}📋 启动日志 (最近 20 行):${NC}"
    echo -e "${YELLOW}----------------------------------------${NC}"
    tail -n 20 "${LOG_FILE}"
    echo -e "${YELLOW}----------------------------------------${NC}"

else
    echo -e "\n${RED}=========================================${NC}"
    echo -e "${RED}  ✗ 服务器启动失败！${NC}"
    echo -e "${RED}=========================================${NC}"
    echo -e "${RED}请检查日志文件: ${LOG_FILE}${NC}"
    exit 1
fi

echo -e "\n${GREEN}启动完成！服务器正在后台运行。${NC}"
