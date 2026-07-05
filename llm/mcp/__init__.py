"""MCP 封装层 — 进程内服务封装，不另起进程

每个子模块暴露 `tools` 列表（langchain_core.tools.Tool 列表），
供 Agent 工具注册使用。

当前已注册：
  - loki_mcp      日志查询、错误分析
  - prometheus_mcp 指标查询、告警检查
"""

import os
from dotenv import load_dotenv

load_dotenv()

CLOUD_LOKI_URL = os.getenv("CLOUD_LOKI_URL", "http://localhost:3100")
CLOUD_PROMETHEUS_URL = os.getenv("CLOUD_PROMETHEUS_URL", "http://localhost:9090")

__all__ = ["tools", "CLOUD_LOKI_URL", "CLOUD_PROMETHEUS_URL"]

tools = []
"""统一工具列表，由各子模块注册"""


def _lazy_load():
    """延迟加载子模块工具，避免导入时依赖未创建的文件"""
    # pylint: disable=import-outside-toplevel
    for mod_name in ("loki_mcp", "prometheus_mcp"):
        try:
            mod = __import__(f"llm.mcp.{mod_name}", fromlist=["tools"])
            if hasattr(mod, "tools"):
                tools.extend(mod.tools)
        except (ImportError, ModuleNotFoundError):
            pass
