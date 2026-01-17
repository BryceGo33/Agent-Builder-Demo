# Agent Builder Demo

基于 LangChain DeepAgents 框架的智能 Agent 构建工具。通过对话式交互帮助用户快速创建和配置功能完整的 Entrance Agent（入口代理）。

## 功能特性

- 🤖 **对话式构建**：通过自然语言对话创建 Agent
- 📋 **实时配置预览**：实时展示 Agent 配置结构
- ⚡ **智能技能识别**：自动分析需求并推荐技能
- 🎯 **即时测试**：创建后立即测试 Entrance Agent
- 💬 **Mock 对话展示**：自动生成示例对话展示 Agent 能力

## 技术栈

- **Python**: 3.12+
- **包管理**: uv
- **前端框架**: Streamlit
- **Agent 框架**: LangChain DeepAgents
- **主要 LLM**: Claude Sonnet 4.5
- **监控工具**: LangSmith (可选)

## 快速开始

### 1. 环境配置

```bash
# 克隆项目
git clone <repository-url>
cd agent-builder-demo

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，添加你的 ANTHROPIC_AUTH_TOKEN
```

### 2. 运行应用

```bash
# 运行 Streamlit 应用
streamlit run app.py

# 或使用 uv
uv run streamlit run app.py
```

应用将在浏览器中打开 `http://localhost:8501`

## 使用指南

### 创建 Agent 的基本流程

1. **启动对话**
   - 在左侧对话框中描述你想要创建的 Agent
   - 例如："帮我创建一个酒店预约助手"

2. **查看配置预览**
   - 右侧会实时显示生成的 Agent 配置
   - 包括名称、描述、系统提示词和技能配置

3. **创建 Entrance Agent**
   - 配置完成后，点击"🚀 创建 Entrance Agent"按钮
   - 系统会根据配置创建可运行的 Agent 实例

4. **测试 Agent**
   - 在底部的测试区域与创建的 Agent 对话
   - 验证 Agent 的功能是否符合预期

### 示例对话

```
用户: 帮我创建一个酒店预约助手

Agent Builder: 好的！我来帮你创建一个酒店预约助手。
让我先了解一下需求...

[Agent Builder 会自动：]
- 生成 Agent 名称
- 分析所需技能
- 配置工具和提示词
- 生成完整配置
```

## 项目结构

```
agent-builder-demo/
├── app.py                      # Streamlit 应用入口（增强版）
├── app_enhanced.py             # 备用增强版应用
├── main.py                     # 命令行入口
├── src/
│   ├── agent_builder/          # Agent Builder 核心
│   │   ├── agent.py           # PrimaryAgent 和 SubAgents
│   │   ├── prompts.py         # System Prompts
│   │   └── subagents/
│   │       └── tools.py       # SubAgent 工具函数
│   ├── entrance_agent/         # Entrance Agent 模块
│   │   └── creator.py         # Agent 创建和实例化
│   ├── config/                 # 配置模块
│   │   ├── schema.py          # Pydantic Schema
│   │   └── env.py             # 环境配置
│   └── ui/                     # UI 组件
│       └── components.py      # Streamlit 可复用组件
├── docs/                       # 文档
│   └── 项目需求文档.md
├── CLAUDE.md                   # Claude Code 指南
└── README.md                   # 本文件
```

## 核心架构

### 四层架构

1. **Streamlit 前端界面** (`app.py`)
   - Agent Builder 对话界面
   - Entrance Agent 配置预览
   - Entrance Agent 测试对话

2. **Agent Builder (PrimaryAgent)** (`src/agent_builder/agent.py`)
   - 主控制器，负责创建和配置 Entrance Agent
   - 包含三个内置 Middleware：
     - TodoListMiddleware: 任务规划
     - FilesystemMiddleware: 配置文件管理
     - SubAgentMiddleware: 子代理委托

3. **SubAgents 层**
   - FileParserAgent: 文件解析
   - WebSearchAgent: 网页搜索
   - ClarifierAgent: 信息澄清
   - ConfigManagerAgent: 配置管理
   - MockConversationAgent: Mock 对话生成

4. **工具层** (`src/agent_builder/subagents/tools.py`)
   - 使用 `@tool` 装饰器定义
   - Demo 阶段返回模拟数据

## 配置说明

### Entrance Agent 配置结构

```json
{
  "name": "Agent名称",
  "description": "功能描述",
  "system_prompt": "系统提示词",
  "skills": [
    {
      "name": "技能名称",
      "when_to_use": "使用场景描述",
      "prompt": "技能提示词",
      "tools": [
        {
          "tool_id": "工具ID",
          "name": "工具名称",
          "config": {}
        }
      ]
    }
  ]
}
```

**重要限制**：每个 Entrance Agent 只能配置**一个 skill**

## 开发说明

### 添加新的 SubAgent

1. 在 `src/agent_builder/subagents/tools.py` 定义工具函数
2. 在 `src/agent_builder/agent.py:create_subagents()` 中创建 agent
3. 使用 `CompiledSubAgent` 包装并添加到返回列表

### 修改 Agent Builder 行为

编辑 `src/agent_builder/prompts.py` 中的 `AGENT_BUILDER_SYSTEM_PROMPT`

### Demo 阶段限制

- 所有 SubAgent 工具返回模拟数据
- Entrance Agent 的 skill 中的工具不需要实际实现
- 不实现交互协议（confirm 类型交互）
- 不实现中断恢复机制
- 不实现技能广场、工具市场、知识库

## 环境变量

在 `.env` 文件中配置：

```bash
# 必需配置
ANTHROPIC_AUTH_TOKEN=your_api_key

# 可选配置
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=agent-builder-demo
LANGCHAIN_TRACING_V2=true
```

## 故障排除

### 常见问题

1. **ANTHROPIC_AUTH_TOKEN 未配置**
   - 在 `.env` 文件中设置 `ANTHROPIC_AUTH_TOKEN`

2. **Python 版本不匹配**
   - 必须使用 Python 3.12+

3. **依赖安装失败**
   - 使用 `uv sync` 重新安装依赖

4. **Streamlit 界面无响应**
   - 检查 LangSmith 追踪确认 Agent 是否正常执行
   - 查看终端日志中的错误信息

## 参考资料

- [DeepAgents GitHub](https://github.com/langchain-ai/deepagents)
- [DeepAgents 文档](https://context7.com/langchain-ai/deepagents)
- [LangSmith](https://docs.langchain.com/langsmith)
- [LangGraph](https://langchain-ai.github.io/langgraph/)

## License

MIT
