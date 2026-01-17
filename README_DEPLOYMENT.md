# Agent Builder Demo - Deployment Guide

## 本地运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件并添加你的 API keys：

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. 运行应用

```bash
streamlit run app.py
```

应用将在 `http://localhost:8501` 启动。

## 免费云部署到 Streamlit Community Cloud

### 前置条件

1. GitHub 账号
2. Streamlit Community Cloud 账号（使用 GitHub 登录）

### 部署步骤

#### 1. 推送代码到 GitHub

```bash
git add .
git commit -m "Add Streamlit frontend"
git push origin main
```

#### 2. 登录 Streamlit Community Cloud

访问 [share.streamlit.io](https://share.streamlit.io) 并使用 GitHub 账号登录。

#### 3. 部署应用

1. 点击 "New app"
2. 选择你的 GitHub 仓库
3. 选择分支（通常是 `main`）
4. 设置主文件路径：`app.py`
5. 点击 "Advanced settings" 添加环境变量：
   - `OPENAI_API_KEY`: 你的 OpenAI API key
6. 点击 "Deploy!"

#### 4. 等待部署完成

部署通常需要 2-5 分钟。完成后，你会得到一个公开的 URL，例如：
```
https://your-app-name.streamlit.app
```

### 注意事项

- **免费额度**：Streamlit Community Cloud 提供免费的公开应用托管
- **资源限制**：免费版有 CPU 和内存限制，适合演示和测试
- **隐私**：应用默认是公开的，任何人都可以访问
- **环境变量**：敏感信息（如 API keys）通过 Streamlit 的 Secrets 管理，不会暴露在代码中

## 应用功能

### 三个主要区域

1. **左侧 - Agent Builder 对话框**
   - 与 Agent Builder 交互
   - 描述你想要创建的 agent
   - 确认配置和构建

2. **右上 - Mock Conversations 展示**
   - 显示生成的示例对话
   - 帮助理解 agent 的预期行为

3. **右下 - Entrance Agent 对话框**
   - 与创建的 agent 进行实时对话
   - 测试 agent 的功能

### 使用流程

1. 在左侧 Agent Builder 中描述你想要的 agent
2. 等待 Agent Builder 生成配置
3. 确认配置后，系统会自动创建 Entrance Agent
4. 在右上查看生成的 Mock Conversations
5. 在右下与 Entrance Agent 进行对话测试

## 故障排除

### 应用无法启动

- 检查 `requirements.txt` 中的依赖版本
- 确保环境变量正确设置

### API 调用失败

- 检查 OpenAI API key 是否有效
- 确认 API 配额是否充足

### 部署失败

- 检查 GitHub 仓库是否包含所有必要文件
- 查看 Streamlit Cloud 的部署日志

## 技术栈

- **前端框架**: Streamlit
- **AI 框架**: LangChain, LangGraph
- **Agent 框架**: DeepAgents
- **部署平台**: Streamlit Community Cloud (免费)
