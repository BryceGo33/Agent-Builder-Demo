"""
Agent Builder (PrimaryAgent) 模块

负责整个自动化 Agent 生成流程的调度与决策。
包含三个 Middleware：
- TodoListMiddleware: 跟踪待办事项和进度
- FilesystemMiddleware: 管理配置文件的读写
- SubAgentMiddleware: 委托任务给专门的 SubAgent
"""
