# Tech Stack — SmartOps 技术栈与依赖

## 核心依赖

| 包 | 用途 | 当前版本 | 备注 |
|----|------|---------|------|
| flask | Web 框架 | — | 保留，不重构 |
| langgraph | 多 Agent 状态机 | >=0.4 | **新增** |
| langchain-openai | LLM 调用 | — | 已有，deepseek 兼容 |
| chromadb | 向量存储 | — | 已有 |
| rank_bm25 | 关键词检索 | — | 已有 |
| paramiko | SSH 连接 | — | 已有 |
| requests | HTTP 调用 | — | 已有 |
| sqlalchemy | ORM | — | 已有 |

## MCP 封装层约定

MCP Server 封装在 `llm/mcp/` 下，每个模块：
1. 暴露 `tools` 列表（MCP 风格的工具定义）
2. 每个工具函数带类型注解和 docstring
3. 内部通过 `requests` 调用对应服务的 HTTP API
4. 不另起进程，在 Flask 进程内运行

### Loki MCP 接口

```python
def query_logs(server_name: str, hours: int = 1, level: str = ""):
def analyze_errors(server_name: str, hours: int = 1) -> dict:
def count_by_level(server_name: str, hours: int = 1) -> dict:
```

### Prometheus MCP 接口

```python
def query_metric(metric_name: str, server_ip: str = "") -> dict:
def range_query(metric_name: str, server_ip: str, duration: str = "1h"):
def check_alerts() -> list[dict]:
```

## 部署

```yaml
# docker-compose.yml（云服务器）
services:
  loki:     # port 3100
  prometheus: # port 9090
```

- `.env` 新增 `CLOUD_LOKI_URL`、`CLOUD_PROMETHEUS_URL`
- SSH 采集器只保留心跳
