# DeepAgents架构图与数据流转图

> **版本**: v1.0-20251017123000
> **最后更新**: 2025-10-17
> **遵循原则**: KISS (Keep It Simple, Stupid) & DRY (Don't Repeat Yourself)

---

## 目录

1. [系统架构概览](#系统架构概览)
2. [模块结构图](#模块结构图)
3. [数据流转图](#数据流转图)
4. [中间件管道](#中间件管道)
5. [SubAgent 调用流程](#subagent-调用流程)
6. [核心组件详解](#核心组件详解)
7. [Linus 式代码品味分析](#linus-式代码品味分析)

---

## 系统架构概览

### 高层架构 (从上到下)

```
┌─────────────────────────────────────────────────────────────┐
│                         用户层                                │
│         (User Input: messages, files, configs)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      API 入口层                               │
│   create_deep_agent() / async_create_deep_agent()           │
│                  (graph.py)                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Agent Builder 层                            │
│      agent_builder(tools, instructions, middleware...)       │
│         - 组装中间件栈                                         │
│         - 配置系统提示词                                        │
│         - 创建 LangGraph Agent                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   中间件栈 (Middleware Stack)                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. PlanningMiddleware                                │   │
│  │    - State: todos[]                                  │   │
│  │    - Tool: write_todos                               │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ 2. FilesystemMiddleware                              │   │
│  │    - State: files{path: content}                     │   │
│  │    - Tools: ls, read_file, write_file, edit_file     │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ 3. SubAgentMiddleware                                │   │
│  │    - Tool: task(description, subagent_type)          │   │
│  │    - 管理 SubAgent 生命周期                           │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ 4. SummarizationMiddleware                           │   │
│  │    - 当 tokens > 120k 时自动摘要                       │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ 5. AnthropicPromptCachingMiddleware                  │   │
│  │    - 提示词缓存 (TTL: 5min)                           │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ 6. HumanInTheLoopMiddleware (可选)                    │   │
│  │    - 工具调用拦截与审批                                │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ 7. Custom Middleware (用户自定义)                      │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               LangGraph Agent 核心                            │
│   create_agent(model, system_prompt, tools, middleware)     │
│         - 状态管理 (State Graph)                              │
│         - 工具路由                                            │
│         - 消息循环                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      工具层                                   │
│  ┌────────────────┬──────────────────┬────────────────┐    │
│  │   内置工具      │    用户工具       │   SubAgents    │    │
│  │                │                  │                │    │
│  │ • write_todos  │ • internet_search│ • general-     │    │
│  │ • ls           │ • custom_tools   │   purpose      │    │
│  │ • read_file    │ • ...            │ • research-    │    │
│  │ • write_file   │                  │   analyst      │    │
│  │ • edit_file    │                  │ • custom       │    │
│  │                │                  │   subagents    │    │
│  └────────────────┴──────────────────┴────────────────┘    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     模型层                                    │
│    LLM (默认: claude-sonnet-4-20250514)                      │
│    - 支持自定义模型                                            │
│    - 支持 per-subagent 模型覆盖                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 模块结构图

```
src/deepagents/
│
├── __init__.py                  # 导出公共 API
│   ├── create_deep_agent
│   ├── async_create_deep_agent
│   ├── PlanningMiddleware
│   ├── FilesystemMiddleware
│   ├── SubAgentMiddleware
│   ├── DeepAgentState
│   ├── SubAgent
│   └── CustomSubAgent
│
├── graph.py                     # Agent 构建器
│   ├── agent_builder()          # 统一构建器 (同步/异步)
│   ├── create_deep_agent()      # 同步 API
│   └── async_create_deep_agent()# 异步 API
│
├── middleware.py                # 三大核心中间件
│   ├── PlanningMiddleware       # TODO 规划
│   ├── FilesystemMiddleware     # 虚拟文件系统
│   ├── SubAgentMiddleware       # 子代理管理
│   ├── _get_agents()            # SubAgent 实例化
│   ├── _get_subagent_description()
│   └── create_task_tool()       # 动态创建 task 工具
│
├── state.py                     # 状态定义
│   ├── DeepAgentState           # 完整状态 (todos + files)
│   ├── PlanningState            # 规划状态 (todos)
│   ├── FilesystemState          # 文件系统状态 (files)
│   ├── Todo (TypedDict)         # TODO 数据结构
│   └── file_reducer()           # 文件状态合并函数
│
├── tools.py                     # 内置工具实现
│   ├── write_todos()            # 写入 TODO 列表
│   ├── ls()                     # 列出文件
│   ├── read_file()              # 读文件 (支持 offset/limit)
│   ├── write_file()             # 写文件
│   └── edit_file()              # 编辑文件 (字符串替换)
│
├── types.py                     # 类型定义
│   ├── SubAgent (TypedDict)     # 基于 Prompt 的 SubAgent
│   └── CustomSubAgent (TypedDict)# 基于 Graph 的 SubAgent
│
├── prompts.py                   # 系统提示词库 (25k+ 字符)
│   ├── BASE_AGENT_PROMPT
│   ├── WRITE_TODOS_SYSTEM_PROMPT
│   ├── TASK_SYSTEM_PROMPT
│   ├── FILESYSTEM_SYSTEM_PROMPT
│   ├── WRITE_TODOS_TOOL_DESCRIPTION
│   ├── TASK_TOOL_DESCRIPTION
│   └── ... (文件系统工具描述)
│
└── model.py                     # 默认模型配置
    └── get_default_model()      # 返回 claude-sonnet-4-20250514
```

---

## 数据流转图

### 完整请求-响应循环

```
┌─────────────────────────────────────────────────────────────┐
│  用户发起请求                                                  │
│  agent.invoke({                                              │
│      "messages": [{"role": "user", "content": "..."}],       │
│      "files": {"doc.txt": "initial content"}  # 可选         │
│  })                                                          │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 状态初始化                                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │ DeepAgentState {                                   │    │
│  │   messages: [UserMessage],                         │    │
│  │   todos: [],                                       │    │
│  │   files: {"doc.txt": "..."}                        │    │
│  │ }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 中间件预处理 (Pre-Model Hooks)                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │ modify_model_request() 调用链:                     │    │
│  │                                                    │    │
│  │ 1. PlanningMiddleware:                             │    │
│  │    system_prompt += WRITE_TODOS_SYSTEM_PROMPT      │    │
│  │                                                    │    │
│  │ 2. FilesystemMiddleware:                           │    │
│  │    system_prompt += FILESYSTEM_SYSTEM_PROMPT       │    │
│  │                                                    │    │
│  │ 3. SubAgentMiddleware:                             │    │
│  │    system_prompt += TASK_SYSTEM_PROMPT             │    │
│  │                                                    │    │
│  │ 最终提示词 = user_instructions +                   │    │
│  │              BASE_AGENT_PROMPT +                   │    │
│  │              中间件系统提示词                       │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: LLM 推理                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │ 输入:                                               │    │
│  │   - 完整系统提示词                                   │    │
│  │   - 消息历史                                        │    │
│  │   - 可用工具列表 (内置 + 用户)                       │    │
│  │                                                    │    │
│  │ 输出:                                               │    │
│  │   - AIMessage with tool_calls                      │    │
│  │   OR                                               │    │
│  │   - AIMessage with content (最终响应)               │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 工具调用路由                                         │
│                                                              │
│  如果 tool_calls 存在:                                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │ 并行执行所有 tool_calls:                            │    │
│  │                                                    │    │
│  │ • write_todos → 更新 state.todos                   │    │
│  │ • read_file   → 返回文件内容                        │    │
│  │ • write_file  → 更新 state.files                   │    │
│  │ • edit_file   → 更新 state.files                   │    │
│  │ • task        → 启动 SubAgent (见下图)             │    │
│  │ • internet_search → 返回搜索结果                    │    │
│  │ • ... 其他用户工具                                  │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 状态更新                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │ DeepAgentState {                                   │    │
│  │   messages: [                                      │    │
│  │     UserMessage,                                   │    │
│  │     AIMessage(tool_calls=[...]),                   │    │
│  │     ToolMessage(name="write_todos", ...),          │    │
│  │     ToolMessage(name="read_file", ...)             │    │
│  │   ],                                               │    │
│  │   todos: [                                         │    │
│  │     {content: "分析代码", status: "in_progress"},   │    │
│  │     {content: "写报告", status: "pending"}          │    │
│  │   ],                                               │    │
│  │   files: {                                         │    │
│  │     "doc.txt": "...",                              │    │
│  │     "report.md": "新生成的报告内容"                 │    │
│  │   }                                                │    │
│  │ }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             │ 循环回 Step 2 (直到 LLM 不再调用工具)
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: 最终响应                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │ 返回完整状态:                                       │    │
│  │ {                                                  │    │
│  │   "messages": [...],  # 完整对话历史                │    │
│  │   "todos": [...],     # 最终 TODO 列表              │    │
│  │   "files": {...}      # 所有文件（含新生成的）       │    │
│  │ }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 中间件管道

### 中间件执行时序图

```
Time ──────────────────────────────────────────────────────────▶

Request In
    │
    ├──► PlanningMiddleware.modify_model_request()
    │       │
    │       └─► 注入 WRITE_TODOS_SYSTEM_PROMPT
    │       └─► 注册 write_todos 工具
    │
    ├──► FilesystemMiddleware.modify_model_request()
    │       │
    │       └─► 注入 FILESYSTEM_SYSTEM_PROMPT
    │       └─► 注册 ls, read_file, write_file, edit_file
    │
    ├──► SubAgentMiddleware.modify_model_request()
    │       │
    │       └─► 注入 TASK_SYSTEM_PROMPT
    │       └─► 注册 task 工具
    │       └─► 初始化 SubAgent 池 (general-purpose + custom)
    │
    ├──► SummarizationMiddleware.modify_model_request()
    │       │
    │       └─► 检查 token 使用量
    │       └─► 如果 > 120k tokens，触发摘要
    │
    ├──► AnthropicPromptCachingMiddleware.modify_model_request()
    │       │
    │       └─► 添加缓存标记到系统提示词
    │
    ├──► HumanInTheLoopMiddleware (如果配置)
    │       │
    │       └─► 拦截配置的工具调用
    │       └─► 等待人工审批 (accept/edit/respond)
    │
    └──► 发送到 LLM
           │
           └──► Model Response
                  │
                  ├──► 工具调用执行
                  │
                  └──► 状态更新
```

### 关键数据结构传递

```python
# ModelRequest 对象在中间件链中传递
class ModelRequest:
    system_prompt: str        # 累积增长的系统提示词
    messages: list[Message]   # 对话历史
    tools: list[Tool]         # 累积增长的工具列表
    ...

# 每个中间件的 modify_model_request 接收并修改这个对象
def modify_model_request(
    self,
    request: ModelRequest,      # 输入：当前请求状态
    agent_state: AgentState,    # 输入：当前代理状态
    runtime: Runtime            # 运行时环境
) -> ModelRequest:              # 输出：修改后的请求
    request.system_prompt += self.extra_prompt
    return request
```

---

## SubAgent 调用流程

### Task 工具调用的完整生命周期

```
Main Agent 决定调用 task 工具
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  task(                                                       │
│      description="深入研究 LangGraph 架构",                   │
│      subagent_type="general-purpose"                         │
│  )                                                           │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: SubAgent 选择                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ 从 SubAgent 池中查找 "general-purpose":             │    │
│  │                                                    │    │
│  │ agents = {                                         │    │
│  │   "general-purpose": <Agent>,  # 默认存在          │    │
│  │   "research-analyst": <Agent>, # 用户自定义        │    │
│  │   "code-reviewer": <Agent>     # 用户自定义        │    │
│  │ }                                                  │    │
│  │                                                    │    │
│  │ 如果 subagent_type 不存在 → 返回错误                │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: SubAgent 状态隔离                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ 创建独立状态:                                       │    │
│  │                                                    │    │
│  │ sub_state = {                                      │    │
│  │   "messages": [                                    │    │
│  │     {                                              │    │
│  │       "role": "user",                              │    │
│  │       "content": "深入研究 LangGraph 架构"          │    │
│  │     }                                              │    │
│  │   ],                                               │    │
│  │   "files": {...},  # 从主 Agent 继承                │    │
│  │   "todos": []      # SubAgent 独立的 TODO          │    │
│  │ }                                                  │    │
│  │                                                    │    │
│  │ 注意: SubAgent 的 messages 是全新的，               │    │
│  │      不包含主 Agent 的对话历史                       │    │
│  │      → 实现 "context quarantine"                   │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: SubAgent 执行                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ sub_agent.invoke(sub_state)                        │    │
│  │                                                    │    │
│  │ SubAgent 自身也有完整的中间件栈:                    │    │
│  │ • PlanningMiddleware                               │    │
│  │ • FilesystemMiddleware                             │    │
│  │ • SummarizationMiddleware                          │    │
│  │ • AnthropicPromptCachingMiddleware                 │    │
│  │ • (注意: SubAgent 默认 *没有* SubAgentMiddleware)   │    │
│  │                                                    │    │
│  │ SubAgent 可以:                                     │    │
│  │ • 调用工具                                          │    │
│  │ • 更新 todos                                       │    │
│  │ • 读写文件                                          │    │
│  │ • 进行多轮推理                                      │    │
│  │                                                    │    │
│  │ 最终返回:                                           │    │
│  │ {                                                  │    │
│  │   "messages": [                                    │    │
│  │     UserMessage("深入研究 LangGraph 架构"),         │    │
│  │     AIMessage(...),                                │    │
│  │     ToolMessage(...),                              │    │
│  │     ...,                                           │    │
│  │     AIMessage("研究完成，以下是详细报告...")        │    │
│  │   ],                                               │    │
│  │   "files": {"research_report.md": "..."}           │    │
│  │ }                                                  │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 结果提取与状态合并                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ # 只取 SubAgent 最后一条消息作为工具返回值          │    │
│  │ tool_result = result["messages"][-1].content       │    │
│  │                                                    │    │
│  │ # 合并非消息状态 (如 files)                         │    │
│  │ state_update = {}                                  │    │
│  │ for k, v in result.items():                        │    │
│  │     if k not in ["todos", "messages"]:             │    │
│  │         state_update[k] = v  # 如 files            │    │
│  │                                                    │    │
│  │ # 返回 Command 更新主 Agent 状态                    │    │
│  │ return Command(                                    │    │
│  │     update={                                       │    │
│  │         **state_update,  # files 更新              │    │
│  │         "messages": [                              │    │
│  │             ToolMessage(                           │    │
│  │                 content=tool_result,               │    │
│  │                 tool_call_id=...                   │    │
│  │             )                                      │    │
│  │         ]                                          │    │
│  │     }                                              │    │
│  │ )                                                  │    │
│  │                                                    │    │
│  │ 注意: SubAgent 的中间推理过程被丢弃，                │    │
│  │      只保留最终输出 → 节省主 Agent 上下文             │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 主 Agent 继续                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ 主 Agent 看到的消息历史:                            │    │
│  │                                                    │    │
│  │ [                                                  │    │
│  │   UserMessage("帮我研究三个技术"),                  │    │
│  │   AIMessage(tool_calls=[                           │    │
│  │     {"name": "task", "args": {...}}                │    │
│  │   ]),                                              │    │
│  │   ToolMessage(                                     │    │
│  │     name="task",                                   │    │
│  │     content="研究完成，LangGraph 是..."  # 浓缩结果 │    │
│  │   )                                                │    │
│  │ ]                                                  │    │
│  │                                                    │    │
│  │ 主 Agent *看不到* SubAgent 的:                      │    │
│  │ • 中间工具调用                                      │    │
│  │ • 推理步骤                                          │    │
│  │ • SubAgent 的 todos                                │    │
│  │                                                    │    │
│  │ → 这就是 "context quarantine" 的实现               │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### SubAgent 并行调用示例

```python
# 用户请求: "研究 LangGraph, LangChain, LangSmith"

# Main Agent 的单次工具调用:
AIMessage(tool_calls=[
    {
        "name": "task",
        "args": {
            "description": "研究 LangGraph 架构和核心概念",
            "subagent_type": "general-purpose"
        }
    },
    {
        "name": "task",
        "args": {
            "description": "研究 LangChain 功能和生态",
            "subagent_type": "general-purpose"
        }
    },
    {
        "name": "task",
        "args": {
            "description": "研究 LangSmith 监控能力",
            "subagent_type": "general-purpose"
        }
    }
])

# 这三个 SubAgent 并行执行，各自独立:
# • 独立的消息历史
# • 独立的 todos
# • 共享的 files (通过 State)
# • 最终返回三个独立的 ToolMessage
```

---

## 核心组件详解

### 1. State 管理

```python
# state.py

class Todo(TypedDict):
    content: str                                      # TODO 内容
    status: Literal["pending", "in_progress", "completed"]  # 状态

class DeepAgentState(AgentState):
    todos: NotRequired[list[Todo]]                    # TODO 列表
    files: Annotated[NotRequired[dict[str, str]], file_reducer]
    #      ^^^^^^^^^                               ^^^^^^^^^^^^
    #      可选字段                                 自定义合并函数

def file_reducer(left, right):
    """合并文件字典的 Reducer"""
    if left is None:
        return right
    elif right is None:
        return left
    else:
        return {**left, **right}  # 浅合并，right 覆盖 left
```

**关键设计点**:
- `NotRequired` - 字段可选，允许用户不传 `files`
- `Annotated[..., file_reducer]` - LangGraph 使用此函数合并并行更新
- 所有状态字段都是不可变操作（返回新对象）

### 2. 工具实现

#### write_todos

```python
@tool(description=WRITE_TODOS_TOOL_DESCRIPTION)
def write_todos(
    todos: list[Todo],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    return Command(
        update={
            "todos": todos,  # 完全替换 todos 列表
            "messages": [
                ToolMessage(
                    f"Updated todo list to {todos}",
                    tool_call_id=tool_call_id
                )
            ],
        }
    )
```

**特点**:
- 返回 `Command` 而非字符串 → 直接更新状态
- 完全替换 todos（非增量更新）
- LLM 负责管理整个 todos 列表

#### read_file

```python
@tool(description=READ_FILE_TOOL_DESCRIPTION)
def read_file(
    file_path: str,
    state: Annotated[FilesystemState, InjectedState],  # 注入状态
    offset: int = 0,      # 行偏移
    limit: int = 2000,    # 最多读取行数
) -> str:
    mock_filesystem = state.get("files", {})

    if file_path not in mock_filesystem:
        return f"Error: File '{file_path}' not found"

    content = mock_filesystem[file_path]
    lines = content.splitlines()

    # 应用分页
    start_idx = offset
    end_idx = min(start_idx + limit, len(lines))

    # 格式化输出 (模拟 cat -n)
    result_lines = []
    for i in range(start_idx, end_idx):
        line_content = lines[i][:2000]  # 截断长行
        line_number = i + 1
        result_lines.append(f"{line_number:6d}\t{line_content}")

    return "\n".join(result_lines)
```

**关键点**:
- `InjectedState` - LangGraph 自动注入当前状态
- 支持大文件分页读取
- 返回带行号的格式（兼容 Claude Code 习惯）

#### edit_file

```python
@tool(description=EDIT_FILE_TOOL_DESCRIPTION)
def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    state: Annotated[FilesystemState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    replace_all: bool = False,
) -> Union[Command, str]:
    mock_filesystem = state.get("files", {})

    if file_path not in mock_filesystem:
        return f"Error: File '{file_path}' not found"

    content = mock_filesystem[file_path]

    # 唯一性检查
    if not replace_all:
        occurrences = content.count(old_string)
        if occurrences > 1:
            return f"Error: String appears {occurrences} times. Use replace_all=True"

    # 执行替换
    if replace_all:
        new_content = content.replace(old_string, new_string)
    else:
        new_content = content.replace(old_string, new_string, 1)

    mock_filesystem[file_path] = new_content

    return Command(
        update={
            "files": mock_filesystem,
            "messages": [ToolMessage("Success", tool_call_id=tool_call_id)]
        }
    )
```

**设计模式**:
- 字符串精确替换（非正则）
- 唯一性保护 - 避免误替换
- 返回类型 `Union[Command, str]` - 错误返回字符串，成功返回 Command

### 3. Middleware 架构

#### 基类接口

```python
class AgentMiddleware:
    state_schema: Type[AgentState] = None  # 扩展状态模式
    tools: list[BaseTool] = []             # 提供的工具

    def modify_model_request(
        self,
        request: ModelRequest,
        agent_state: AgentState,
        runtime: Runtime
    ) -> ModelRequest:
        """在调用模型前修改请求"""
        return request

    # 还有其他 hooks: before_tools, after_tools, etc.
```

#### PlanningMiddleware 实现

```python
class PlanningMiddleware(AgentMiddleware):
    state_schema = PlanningState  # 扩展 todos 字段
    tools = [write_todos]         # 提供工具

    def modify_model_request(
        self,
        request: ModelRequest,
        agent_state: PlanningState,
        runtime: Runtime
    ) -> ModelRequest:
        # 注入 TODO 管理指令
        request.system_prompt = (
            request.system_prompt +
            "\n\n" +
            WRITE_TODOS_SYSTEM_PROMPT
        )
        return request
```

**要点**:
- `state_schema` - 声明式状态扩展
- `tools` - 自动注册到 Agent
- `modify_model_request` - 修改系统提示词

#### SubAgentMiddleware 动态工具生成

```python
class SubAgentMiddleware(AgentMiddleware):
    def __init__(self, default_subagent_tools, subagents, model, is_async):
        super().__init__()
        # 动态创建 task 工具（闭包捕获 subagents）
        task_tool = create_task_tool(
            default_subagent_tools=default_subagent_tools,
            subagents=subagents,
            model=model,
            is_async=is_async,
        )
        self.tools = [task_tool]

def create_task_tool(default_subagent_tools, subagents, model, is_async):
    # 初始化所有 SubAgent 实例
    agents = _get_agents(default_subagent_tools, subagents, model)

    # 生成 SubAgent 描述字符串
    other_agents_string = _get_subagent_description(subagents)

    # 根据同步/异步返回不同实现
    if is_async:
        @tool(description=TASK_TOOL_DESCRIPTION.format(...))
        async def task(description, subagent_type, state, tool_call_id):
            sub_agent = agents[subagent_type]
            result = await sub_agent.ainvoke(...)
            return Command(update={...})
    else:
        @tool(description=TASK_TOOL_DESCRIPTION.format(...))
        def task(description, subagent_type, state, tool_call_id):
            sub_agent = agents[subagent_type]
            result = sub_agent.invoke(...)
            return Command(update={...})

    return task
```

**关键技术**:
- 动态 `@tool` 装饰器（运行时生成）
- 闭包捕获 `agents` 字典
- 同步/异步双实现

### 4. SubAgent 类型系统

#### 两种 SubAgent 类型

```python
# types.py

# 类型 1: 基于 Prompt 的 SubAgent (更常用)
class SubAgent(TypedDict):
    name: str                           # 如 "research-analyst"
    description: str                    # 给主 Agent 看的功能描述
    prompt: str                         # SubAgent 的系统提示词
    tools: NotRequired[list[BaseTool]]  # 可选工具列表
    model: NotRequired[Union[           # 可选模型覆盖
        LanguageModelLike,              #   - 模型实例
        dict[str, Any]                  #   - 或配置字典
    ]]
    middleware: NotRequired[list[AgentMiddleware]]  # 额外中间件

# 类型 2: 基于 Graph 的 SubAgent (高级用法)
class CustomSubAgent(TypedDict):
    name: str                           # 如 "complex-workflow"
    description: str                    # 给主 Agent 看的功能描述
    graph: Runnable                     # 预构建的 LangGraph 图
```

#### SubAgent 实例化逻辑

```python
def _get_agents(default_subagent_tools, subagents, model):
    # 默认中间件 (SubAgent 共享)
    default_subagent_middleware = [
        PlanningMiddleware(),
        FilesystemMiddleware(),
        # 注意: 没有 SubAgentMiddleware (避免无限递归)
        SummarizationMiddleware(...),
        AnthropicPromptCachingMiddleware(...)
    ]

    # 1. 创建内置 general-purpose SubAgent
    agents = {
        "general-purpose": create_agent(
            model,
            system_prompt=BASE_AGENT_PROMPT,
            tools=default_subagent_tools,  # 继承主 Agent 工具
            middleware=default_subagent_middleware,
            checkpointer=False  # SubAgent 不持久化
        )
    }

    # 2. 实例化用户自定义 SubAgents
    for _agent in subagents:
        if "graph" in _agent:
            # CustomSubAgent - 直接使用预构建图
            agents[_agent["name"]] = _agent["graph"]
            continue

        # SubAgent - 构建新 Agent
        _tools = _agent.get("tools", default_subagent_tools.copy())

        # 模型解析
        if "model" in _agent:
            agent_model = _agent["model"]
            if isinstance(agent_model, dict):
                # 字典配置 → 初始化模型
                sub_model = init_chat_model(**agent_model)
            else:
                # 模型实例 → 直接使用
                sub_model = agent_model
        else:
            # 继承主 Agent 模型
            sub_model = model

        # 中间件合并
        if "middleware" in _agent:
            _middleware = [
                *default_subagent_middleware,
                *_agent["middleware"]
            ]
        else:
            _middleware = default_subagent_middleware

        # 构建 SubAgent
        agents[_agent["name"]] = create_agent(
            sub_model,
            system_prompt=_agent["prompt"],
            tools=_tools,
            middleware=_middleware,
            checkpointer=False
        )

    return agents
```

---

## Linus 式代码品味分析

### ✅ 好品味 (Good Taste)

#### 1. **数据结构驱动设计**
```python
# state.py
class DeepAgentState(AgentState):
    todos: NotRequired[list[Todo]]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]
```

**评价**:
- ✅ 状态是第一公民，所有组件围绕 State 设计
- ✅ 使用 `Annotated` + Reducer 优雅处理并发更新
- ✅ `NotRequired` 让接口灵活但类型安全

#### 2. **工具返回 Command 而非副作用**
```python
# tools.py
@tool
def write_file(...) -> Command:
    return Command(
        update={
            "files": new_files,
            "messages": [ToolMessage(...)]
        }
    )
```

**评价**:
- ✅ 函数式设计 - 返回数据而非修改全局状态
- ✅ 可测试性强 - 工具是纯函数
- ✅ LangGraph 统一处理状态更新

#### 3. **中间件的声明式扩展**
```python
class PlanningMiddleware(AgentMiddleware):
    state_schema = PlanningState  # 声明扩展字段
    tools = [write_todos]         # 声明提供工具
```

**评价**:
- ✅ 组合优于继承
- ✅ 每个中间件职责单一
- ✅ 易于添加/删除功能

### 🟡 凑合 (Acceptable but Smelly)

#### 1. **SubAgent 双类型设计**
```python
class SubAgent(TypedDict): ...
class CustomSubAgent(TypedDict): ...

# 使用时需要条件判断
if "graph" in _agent:
    agents[name] = _agent["graph"]
else:
    agents[name] = create_agent(...)
```

**问题**:
- 🟡 运行时类型检查 (`if "graph" in _agent`)
- 🟡 两种配置方式增加认知负担

**Linus 建议**:
```python
# 统一接口
class SubAgent:
    name: str
    description: str

    @abstractmethod
    def get_executor(self) -> Runnable:
        pass

class PromptBasedSubAgent(SubAgent):
    def get_executor(self):
        return create_agent(...)

class GraphBasedSubAgent(SubAgent):
    def get_executor(self):
        return self.graph
```

#### 2. **同步/异步代码重复**
```python
# graph.py
def create_deep_agent(...):
    return agent_builder(..., is_async=False)

def async_create_deep_agent(...):
    return agent_builder(..., is_async=True)

# middleware.py
if is_async:
    @tool
    async def task(...):
        result = await sub_agent.ainvoke(...)
else:
    @tool
    def task(...):
        result = sub_agent.invoke(...)
```

**问题**:
- 🟡 代码重复 - 违反 DRY
- 🟡 维护成本 - 两处修改

**Linus 建议**:
```python
# 只提供异步版本
def create_deep_agent(...):
    return async_create_deep_agent(...)

# 或使用适配器模式
class SyncWrapper:
    def __init__(self, async_agent):
        self.agent = async_agent

    def invoke(self, *args, **kwargs):
        return asyncio.run(self.agent.ainvoke(*args, **kwargs))
```

### 🔴 糟糕 (Bad Taste)

#### 1. **过度依赖 Prompt Engineering**
```python
# prompts.py - 25KB+ 的提示词文件
WRITE_TODOS_SYSTEM_PROMPT = """
## When to Use This Tool
Use this tool in these scenarios:
1. Complex multi-step tasks...
2. Non-trivial and complex tasks...
...
(400+ lines of instructions)
"""
```

**问题**:
- 🔴 控制逻辑埋在自然语言里
- 🔴 难以测试和验证
- 🔴 Prompt 变化可能破坏行为

**Linus 观点**:
> "如果你的系统严重依赖一个 magic prompt 才能工作，那说明你的数据结构和控制流设计有问题。"

**重构方向**:
```python
class PlanningController:
    def should_create_todos(self, task: Task) -> bool:
        """代码逻辑决定何时使用 TODO"""
        return (
            task.step_count >= 3 or
            task.complexity > Complexity.MEDIUM or
            task.has_subtasks
        )

    def auto_decompose_task(self, task: Task) -> list[Todo]:
        """代码自动拆解任务，而非让 LLM 猜"""
        if task.type == TaskType.RESEARCH:
            return self._decompose_research(task)
        elif task.type == TaskType.CODING:
            return self._decompose_coding(task)
        ...
```

#### 2. **虚拟文件系统的命名不诚实**
```python
# 代码实现
files: dict[str, str]  # 只是一个字典

# 文档声明
"You have access to a local, private **filesystem**"
"Right now the 'file system' will only be one level deep (no sub directories)"
```

**问题**:
- 🔴 名字撒谎 - 这不是文件系统，是键值存储
- 🔴 用户期望文件系统功能（目录、路径、权限）但都不支持

**Linus 观点**:
> "如果你的东西不支持目录，就别叫它文件系统。叫它 'document store' 或 'artifact cache'。"

**正确命名**:
```python
class ArtifactStore(AgentMiddleware):
    """存储 Agent 生成的文档和数据"""
    state_schema = ArtifactState
    tools = [
        list_artifacts,
        read_artifact,
        write_artifact,
        update_artifact
    ]
```

#### 3. **文件只读检查缺失**
```python
# tools.py
@tool
def edit_file(file_path, old_string, new_string, state, ...):
    mock_filesystem = state.get("files", {})

    if file_path not in mock_filesystem:
        return "Error: File not found"

    # 直接修改，没有检查是否曾被读取
    content = mock_filesystem[file_path]
    new_content = content.replace(old_string, new_string)
    ...
```

**问题**:
- 🟡 文档说 "You must use Read tool before editing"
- 🟡 但代码没有强制检查
- 🟡 Prompt 要求 vs 代码实现不一致

**改进**:
```python
class FilesystemState(AgentState):
    files: dict[str, str]
    read_files: set[str]  # 跟踪已读文件

@tool
def edit_file(...):
    if file_path not in state.get("read_files", set()):
        return "Error: Must read file before editing. Use read_file first."
    ...
```

---

## 总结与改进方向

### 架构优势

1. **清晰的分层** - API → Builder → Middleware → Agent → Tools
2. **组合式设计** - 中间件独立可插拔
3. **状态隔离** - SubAgent 实现 context quarantine
4. **LangGraph 基础** - 复用成熟的 Agent 框架

### 关键缺陷

| 问题 | 影响 | 优先级 |
|------|------|--------|
| 过度依赖 Prompt | 不可预测、难测试 | 🔴 P0 |
| 虚拟文件系统命名不诚实 | 误导用户期望 | 🟡 P1 |
| 同步/异步代码重复 | 维护成本高 | 🟡 P1 |
| SubAgent 双类型 | 增加复杂度 | 🟡 P2 |
| 缺少编程式控制流 | 依赖 LLM"猜" | 🔴 P0 |

### Linus 的终极建议

> **"这个项目的方向对，但别把 Prompt 当万能药。"**
>
> **三个关键改进：**
> 1. 把控制逻辑从 Prompt 移到代码里 - 用 `PlanningController`, `TaskDecomposer` 等类
> 2. 诚实命名 - `ArtifactStore` 不是 `Filesystem`
> 3. 消除特殊情况 - 统一 SubAgent 接口，只提供 async API
>
> **品味提升路径：凑合 (6/10) → 好 (8/10)**
> - 数据结构已经不错
> - 但控制流还在 Prompt 里晃荡
> - 把它们拉到类型安全的代码里，这个项目就能成为教科书级别的设计

---

## 附录: 快速参考

### 创建 Agent 流程

```python
# 1. 定义工具
def my_tool(query: str) -> str:
    return do_something(query)

# 2. 定义 SubAgent (可选)
subagents = [{
    "name": "analyst",
    "description": "数据分析专家",
    "prompt": "你是数据分析专家...",
    "tools": [my_tool]
}]

# 3. 创建 Agent
from deepagents import create_deep_agent

agent = create_deep_agent(
    tools=[my_tool],
    instructions="你是一个研究助手",
    subagents=subagents
)

# 4. 调用
result = agent.invoke({
    "messages": [{"role": "user", "content": "帮我研究 X"}]
})

# 5. 访问结果
print(result["messages"][-1].content)  # 最终响应
print(result["files"])                  # 生成的文件
print(result["todos"])                  # TODO 状态
```

### 状态流转速查表

| 阶段 | State Keys | 操作 |
|------|-----------|------|
| 输入 | `messages`, `files?` | 用户提供 |
| 规划 | `+todos` | PlanningMiddleware 添加 |
| 工具调用 | `messages+`, `files*`, `todos*` | 工具更新 |
| SubAgent | 隔离 `messages` | SubAgentMiddleware |
| 输出 | `messages`, `todos`, `files` | 完整状态 |

*注: `+` 追加, `*` 修改, `?` 可选*

---

**文档版本**: v1.0-20251017123000
**基于代码**: `/Users/gump_m2/Documents/Agent-RL/xDAN-DeepAgent-People-Searching/src/deepagents`
**符合标准**: KISS, DRY, Linus 好品味原则
