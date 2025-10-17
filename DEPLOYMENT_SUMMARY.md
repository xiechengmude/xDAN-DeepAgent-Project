# DeepAgent LangGraph 部署总结

## 🎯 当前部署状态

### ✅ 服务器信息
- **端口**: `5080`（从 5060 迁移）
- **进程 PID**: `41796`
- **启动时间**: 2025-10-17 15:24:05
- **日志文件**: `logs/langgraph_dev_20251017_152404.log`
- **监听地址**: `0.0.0.0:5080`（允许局域网访问）

### ✅ 可用的 Agents
- `deep_agent` - 同步版本（推荐）
- `async_deep_agent` - 异步版本

---

## 📍 访问地址

### 主要端点
```
API Server:     http://127.0.0.1:5080
API Docs:       http://127.0.0.1:5080/docs
Health Check:   http://127.0.0.1:5080/ok
OpenAPI JSON:   http://127.0.0.1:5080/openapi.json
Studio UI:      https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:5080
```

### 局域网访问（如果需要）
```
http://192.168.31.22:5080/docs
```

---

## 🔍 之前的问题分析

### 问题 1：浏览器无法访问
**原因**：ClashX Pro 代理配置未绕过 localhost

**解决方案**：
1. 使用局域网 IP 访问（绕过代理）：`http://192.168.31.22:5080/docs`
2. 配置 Clash bypass 规则
3. 暂时关闭代理测试

### 问题 2：多个服务器实例冲突
**原因**：5060 端口有多个 langgraph dev 进程同时运行

**解决方案**：
1. 清理所有旧进程：`kill -9 $(lsof -ti :5060)`
2. 使用新端口 5080 避免冲突

### 问题 3：curl 测试误导
**原因**：curl 命令继承了 shell 的代理环境变量

**表现**：
```bash
# 错误的测试方式（使用了代理）
curl http://127.0.0.1:5080/ok
# 输出：* Uses proxy env variable http_proxy == 'http://127.0.0.1:7890'

# 正确的测试方式（禁用代理）
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
curl http://127.0.0.1:5080/ok
# 输出：{"ok":true}
```

---

## 📝 正确的测试命令

### 1. 健康检查
```bash
# 禁用代理后测试
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
curl http://127.0.0.1:5080/ok
```

**预期输出**：
```json
{"ok":true}
```

### 2. 获取服务器信息
```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
curl http://127.0.0.1:5080/info
```

**预期输出**：
```json
{
  "version": "0.4.43",
  "langgraph_py_version": "1.0.0rc1",
  ...
}
```

### 3. 创建 Thread
```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
curl -X POST http://127.0.0.1:5080/threads \
  -H "Content-Type: application/json" \
  -d '{"assistant_id":"deep_agent"}'
```

**预期输出**：
```json
{
  "thread_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  ...
}
```

### 4. 运行 Agent
```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
THREAD_ID="your-thread-id"

curl -X POST http://127.0.0.1:5080/threads/${THREAD_ID}/runs \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "deep_agent",
    "input": {
      "messages": [{
        "role": "user",
        "content": "你好，请介绍一下你的功能"
      }]
    }
  }'
```

### 5. 获取 Thread 状态
```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
curl http://127.0.0.1:5080/threads/${THREAD_ID}/state
```

---

## 🛠️ 管理命令

### 启动服务器
```bash
./start_server.sh
```

### 查看服务器状态
```bash
ps -p 41796
```

### 查看实时日志
```bash
tail -f logs/langgraph_dev_20251017_152404.log
```

### 停止服务器
```bash
kill 41796
# 或使用
kill $(cat logs/server.pid)
```

### 诊断服务器
```bash
./diagnose_server.sh
```

### 测试代理影响
```bash
./test_proxy_impact.sh
```

---

## 🧪 使用 Python 客户端测试

### 基本测试
```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
python3 test_api.py
```

### 完整示例测试
```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
python3 examples_api_usage.py
```

### 详细测试
```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
python3 test_examples_detailed.py
```

---

## 📊 环境变量说明

### 代理相关（已禁用）
```bash
# 这些变量在启动脚本中已经 unset
HTTP_PROXY      # 已清除
HTTPS_PROXY     # 已清除
http_proxy      # 已清除
https_proxy     # 已清除
```

### 项目配置（来自 .env）
```bash
OPENAI_API_KEY           # OpenAI API 密钥
OPENAI_BASE_URL          # 模型 API 地址
OPENAI_MODEL             # 使用的模型
BRIGHTDATA_API_KEY       # BrightData 搜索 API 密钥
```

---

## 🎨 浏览器访问建议

### 方案 1：配置 Clash 绕过本地地址
1. 打开 ClashX Pro
2. 配置 → 设置 → 绕过代理
3. 添加：`localhost, 127.0.0.1, *.local`

### 方案 2：使用局域网 IP（推荐）⭐
```
http://192.168.31.22:5080/docs
```

### 方案 3：暂时关闭代理
1. ClashX Pro 图标 → 取消勾选"设置为系统代理"
2. 访问 `http://127.0.0.1:5080/docs`
3. 测试完后重新启用

---

## 📚 API 使用示例

### Python 示例
```python
import requests

# 禁用代理（重要！）
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

BASE_URL = "http://127.0.0.1:5080"

# 1. 健康检查
response = requests.get(f"{BASE_URL}/ok")
print(response.json())  # {"ok": true}

# 2. 创建 Thread
response = requests.post(
    f"{BASE_URL}/threads",
    json={"assistant_id": "deep_agent"}
)
thread_id = response.json()["thread_id"]

# 3. 发送消息
response = requests.post(
    f"{BASE_URL}/threads/{thread_id}/runs",
    json={
        "assistant_id": "deep_agent",
        "input": {
            "messages": [{
                "role": "user",
                "content": "你好"
            }]
        }
    }
)

# 4. 获取状态
response = requests.get(f"{BASE_URL}/threads/{thread_id}/state")
state = response.json()
messages = state["values"]["messages"]
```

### JavaScript/Node.js 示例
```javascript
const BASE_URL = "http://127.0.0.1:5080";

// 健康检查
const response = await fetch(`${BASE_URL}/ok`);
const data = await response.json();
console.log(data); // {"ok": true}

// 创建 Thread
const threadResponse = await fetch(`${BASE_URL}/threads`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ assistant_id: "deep_agent" })
});
const { thread_id } = await threadResponse.json();

// 发送消息
const runResponse = await fetch(`${BASE_URL}/threads/${thread_id}/runs`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    assistant_id: "deep_agent",
    input: {
      messages: [{ role: "user", content: "你好" }]
    }
  })
});
```

---

## 🔧 故障排查

### 问题：浏览器显示 "无法连接"
**检查清单**：
1. ✅ 服务器是否运行：`ps -p 41796`
2. ✅ 端口是否监听：`lsof -i :5080`
3. ✅ 健康检查是否通过：`unset HTTP_PROXY && curl http://127.0.0.1:5080/ok`
4. ❌ 浏览器代理设置：尝试方案 2（使用局域网 IP）

### 问题：curl 提示使用代理
**症状**：
```
* Uses proxy env variable http_proxy == 'http://127.0.0.1:7890'
```

**解决**：
```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
curl http://127.0.0.1:5080/ok
```

### 问题：Python 脚本连接失败
**解决**：
```python
import os
# 清除代理环境变量
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(key, None)
```

---

## 📄 相关文件

| 文件 | 说明 |
|------|------|
| `start_server.sh` | 启动脚本（端口 5080） |
| `diagnose_server.sh` | 诊断脚本 |
| `test_proxy_impact.sh` | 代理影响测试 |
| `test_api.py` | 简单 API 测试 |
| `examples_api_usage.py` | 完整 API 示例 |
| `test_examples_detailed.py` | 详细测试脚本 |
| `langgraph.json` | LangGraph 配置 |
| `src/deepagents/factory.py` | Agent 工厂函数 |
| `API_USAGE_GUIDE.md` | API 使用指南 |
| `FIX_BROWSER_PROXY.md` | 代理问题解决方案 |
| `logs/server.pid` | 服务器 PID |
| `logs/langgraph_dev_*.log` | 服务器日志 |

---

## ✅ 验证清单

部署完成后，请验证：

- [x] 服务器启动成功（端口 5080）
- [x] 健康检查通过：`curl http://127.0.0.1:5080/ok`
- [x] 可以创建 Thread
- [x] Agent 可以响应消息
- [ ] 浏览器可以访问文档页面（需配置代理bypass）
- [x] Python 客户端可以正常调用

---

**最后更新**：2025-10-17 15:24:10
**服务器 PID**：41796
**端口**：5080
**状态**：✅ 正常运行
