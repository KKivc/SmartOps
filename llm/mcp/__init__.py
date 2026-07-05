# SmartOps MCP (Model Context Protocol) 封装层
#
# 提供监控基础设施的 MCP 风格工具接口：
# - Loki MCP: 日志查询与分析
# - Prometheus MCP: 指标查询与告警
#
# 每个子模块通过 HTTP API 调用对应服务，不另起进程。

from llm.mcp.loki_mcp import LokiMCPServer

# prometheus_mcp 在 B3 实现
# from llm.mcp.prometheus_mcp import PrometheusMCPServer

__all__ = [
    "LokiMCPServer",
    # "PrometheusMCPServer",
]
