# DeepAgents Prompts Directory

This directory contains all prompt templates used by the DeepAgents system, separated into individual Markdown files for easier maintenance and version control.

## 文件结构

```
prompts/
├── README.md                          # 本文件
│
├── base/                              # 基础提示词
│   └── base_agent_prompt.md          # 基础 Agent 提示词
│
├── system_tool/                       # 系统工具描述
│   ├── write_todos_tool_description.md
│   ├── task_tool_description.md
│   ├── list_files_tool_description.md
│   ├── read_file_tool_description.md
│   ├── write_file_tool_description.md
│   └── edit_file_tool_description.md
│
└── system/                            # 系统提示词
    ├── write_todos_system_prompt.md
    ├── task_system_prompt.md
    └── filesystem_system_prompt.md
```

### 目录分类说明

- **`base/`** - 所有 Agent 共享的基础指令
- **`system_tool/`** - 系统工具的使用说明
- **`system/`** - 注入到系统提示词中的功能指令

## 使用方法

### 在代码中引用

```python
from deepagents.prompts import (
    WRITE_TODOS_TOOL_DESCRIPTION,
    TASK_TOOL_DESCRIPTION,
    BASE_AGENT_PROMPT,
    # ... 其他 prompts
)

# 使用方式与之前完全相同
@tool(description=WRITE_TODOS_TOOL_DESCRIPTION)
def write_todos(...):
    ...
```

### 编辑 Prompt

1. **直接编辑对应的 .md 文件**
   - 文件位置: `src/deepagents/prompts/<prompt_name>.md`
   - 使用任何文本编辑器或 IDE

2. **无需重新编译**
   - Prompt 在运行时加载
   - 修改后重启应用即可生效

3. **版本控制友好**
   - 每个 prompt 独立文件，Git diff 清晰
   - 易于追踪修改历史
   - 支持独立的 PR 和 review

## 添加新 Prompt

### 1. 选择合适的分类目录

```bash
# 系统工具描述
cd src/deepagents/prompts/system_tool/

# 或系统提示词
cd src/deepagents/prompts/system/

# 或基础提示词
cd src/deepagents/prompts/base/
```

### 2. 创建新的 .md 文件

```bash
touch my_new_prompt.md
```

### 3. 编辑内容

```markdown
Your prompt content here...
```

### 4. 在 prompts.py 中注册

编辑 `src/deepagents/prompts.py`:

```python
# 添加加载语句 (指定分类目录)
MY_NEW_PROMPT = _load_prompt("system_tool", "my_new_prompt")
# 或
MY_NEW_PROMPT = _load_prompt("system", "my_new_prompt")
# 或
MY_NEW_PROMPT = _load_prompt("base", "my_new_prompt")

# 添加到 __all__ 列表
__all__ = [
    # ... existing exports
    "MY_NEW_PROMPT",
]
```

### 4. 在代码中使用

```python
from deepagents.prompts import MY_NEW_PROMPT
```

## 最佳实践

### 1. **使用 Markdown 格式**
- 支持标题、列表、代码块
- 提高可读性
- 易于在文档中复用

### 2. **保持模块化**
- 每个 prompt 只做一件事
- 避免在一个文件中混合多个用途

### 3. **添加注释**
```markdown
<!-- Purpose: Describe when to use the write_todos tool -->
<!-- Last updated: 2025-10-17 -->

Your prompt content...
```

### 4. **使用变量占位符**
对于需要动态内容的 prompt，使用 `{variable}` 占位符：

```markdown
Available agent types:
{other_agents}
```

在代码中使用 `.format()`:
```python
prompt = TASK_TOOL_DESCRIPTION.format(other_agents=agent_list)
```

## Prompt 类型说明

### Tool Descriptions (工具描述)
- **用途**: 传递给 LLM 的工具说明
- **格式**: 清晰的使用指南 + 示例
- **命名**: `<tool_name>_tool_description.md`

### System Prompts (系统提示词)
- **用途**: 注入到系统提示词中的指令
- **格式**: 简洁的使用说明
- **命名**: `<feature>_system_prompt.md`

### Base Prompts (基础提示词)
- **用途**: 所有 Agent 共享的基础指令
- **格式**: 通用性说明
- **命名**: `base_<purpose>_prompt.md`

## 维护指南

### 文件大小建议
- ✅ **小文件 (<100 行)**: 易于维护
- ⚠️ **中等文件 (100-300 行)**: 考虑拆分
- ❌ **大文件 (>300 行)**: 应该拆分成多个文件

### 拆分示例
如果 `write_todos_tool_description.md` 过大：

```
write_todos_tool_description/
├── main.md              # 主要说明
├── when_to_use.md       # 使用场景
├── examples.md          # 示例
└── best_practices.md    # 最佳实践
```

然后在 `prompts.py` 中组合：
```python
def _load_prompt_parts(base_name: str, parts: list[str]) -> str:
    """Load and combine multiple prompt parts"""
    content = []
    for part in parts:
        filepath = _PROMPTS_DIR / base_name / f"{part}.md"
        with open(filepath, 'r') as f:
            content.append(f.read())
    return "\n\n".join(content)
```

## 测试

运行测试确保所有 prompt 加载正确：

```bash
# 在项目根目录
python -c "from deepagents.prompts import *; print('All prompts loaded successfully!')"
```

## 向后兼容性

这个重构**完全向后兼容**：

- ✅ 所有现有导入语句无需修改
- ✅ 所有常量名保持不变
- ✅ API 完全相同

唯一变化：prompt 内容现在从文件加载，而非硬编码在 Python 中。

## 优势

### 开发体验
- 🎯 **专注编辑**: 在编辑器中只看到 prompt 内容
- 🔍 **语法高亮**: Markdown 高亮比 Python 字符串更清晰
- 📝 **实时预览**: Markdown 预览工具可用

### 团队协作
- 👥 **分工明确**: 可以分配不同 prompt 给不同人维护
- 🔄 **减少冲突**: 每个文件独立，减少 Git 冲突
- 📊 **清晰 Diff**: 修改历史一目了然

### 可维护性
- 🧩 **模块化**: 每个关注点独立
- 🔧 **易于调试**: 快速定位问题 prompt
- 📦 **易于复用**: 可以在文档中引用相同的文件

---

**遵循原则**: KISS (Keep It Simple, Stupid) & DRY (Don't Repeat Yourself)
**版本**: v1.0-20251017130000
