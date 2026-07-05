# Architecture — SmartOps 多 Agent + MCP

## 总体架构

```
用户 → Flask API → Supervisor (LangGraph StateGraph)
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    Log Worker   Infra Worker  Knowledge Worker
          │            │            │
     Loki MCP    Prom MCP      RAG 知识库
     （进程内）    + SSH 探活   （ChromaDB + BM25）
```

## 文件结构

```
llm/mcp/__init__.py           MCP 包入口
llm/mcp/loki_mcp.py           Loki MCP — query_logs, analyze_errors
llm/mcp/prometheus_mcp.py     Prometheus MCP — query_metric, range_query
llm/supervisor.py             LangGraph Supervisor（替代旧 agent.py 角色）
llm/workers.py                子 Worker 工具函数
llm/agent.py                  保留入口，内部转发 Supervisor
llm/tools.py                  Agent 工具列表（精简后）
```

## LangGraph StateGraph 设计

### State 结构
```python
class AgentState(TypedDict):
    messages: list                    # 对话历史
    next: Literal["FINISH", "log_worker", "infra_worker", "knowledge_worker"]
    intermediate_results: dict        # {worker_name: result}
    final_report: str                 # RCA 报告
```

### 工作循环
```
用户输入 → Supervisor 节点（LLM 推理）
  ├→ 不需要查数据 → 直接回答 → FINISH
  ├→ 需要日志分析 → log_worker → 回到 Supervisor
  ├→ 需要指标分析 → infra_worker → 回到 Supervisor
  ├→ 需要查知识库 → knowledge_worker → 回到 Supervisor
  └→ 信息够了 → 生成 RCA 报告 → FINISH
```

### 最大循环次数
Supervisor 设 `MAX_ITERATIONS = 10`，防止死循环。

## Worker 设计原则

- Worker 是**工具函数**，不是独立 Agent（不调 LLM）
- 只负责"查数据、做分析"，不负责"决策下一步"
- 异常时返回错误信息，不阻塞 Supervisor 状态机
