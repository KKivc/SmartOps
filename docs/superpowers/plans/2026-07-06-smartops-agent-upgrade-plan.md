# SmartOps Agent 升级实施计划

> **Goal:** 将 3 个 Worker 从纯工具函数改造为独立的 `create_react_agent`，每个拥有 LLM + system prompt + 工具集

## Task 1：重写 workers.py — 3 个 ReAct Agent

- [ ] 1.1 导入 `create_react_agent` + 公共 LLM 配置
- [ ] 1.2 定义 `log_worker_agent`
- [ ] 1.3 定义 `infra_worker_agent`
- [ ] 1.4 定义 `knowledge_worker_agent`
- [ ] 1.5 保留兼容旧签名：`log_worker()`, `infra_worker()`, `knowledge_worker()`

## Task 2：修改 supervisor.py — Worker 节点调用 Agent

- [ ] 2.1 修改 3 个 Worker 节点函数（调用 agent 而非函数）
- [ ] 2.2 调整 intermediate_results 存文本
- [ ] 2.3 更新 Supervisor prompt 适应文本输入
- [ ] 2.4 更新 RCA 报告生成

## Task 3：测试

- [ ] 3.1 更新 `test_workers.py`
- [ ] 3.2 运行端到端测试：找一条真实问题跑完整的 Supervisor 链路
