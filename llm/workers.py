"""Worker 工具函数 / ReAct Agent — 供 Supervisor StateGraph 调用

每个 Worker 可以是:
  1. 独立 ReAct Agent（主力模式）：create_react_agent + LLM + system prompt + tools
     自主理解用户意图，自主选择调哪些工具
  2. 纯工具函数（兼容模式）：保留原有函数签名，方便单元测试

使用方式:
  # ReAct Agent 模式（主力）
  from llm.workers import log_worker_agent
  result = log_worker_agent.invoke({"messages": [("human", "问题")]})

  # 函数模式（测试/兼容）
  from llm.workers import log_worker
  result = log_worker("web-01")
"""

import os
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from llm.mcp.loki_mcp import query_logs, analyze_errors, count_by_level
from llm.mcp.prometheus_mcp import query_metric, range_query, check_alerts
from llm.tools import search_knowledge_base

# ── 公共 LLM ────────────────────────────────────────────────

_LLM = ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://opencode.ai/zen/go/v1",
    api_key=os.getenv("OPENCODE_API_KEY"),
)

# ── Log Worker Agent ────────────────────────────────────────

_LOG_PROMPT = """你是一个运维日志分析专家，通过 Loki 日志系统排查问题。

可用工具：
- **query_logs**(server_name, hours, level) — 查询原始日志文本
- **analyze_errors**(server_name, hours) — 统计错误码分布
- **count_by_level**(server_name, hours) — 按日志级别统计数量

工作流程：
1. 先用 count_by_level 了解整体日志分布
2. 有 error/warn 时调 analyze_errors 看错误码
3. 需要看具体内容时调 query_logs，用 level/keywords 精确过滤
4. 从问题中提取时间范围（默认 1h）和服务器名
5. 返回结构化分析结论

注意：如果 query_logs 返回"无日志"，可能是服务器名不对或时间范围无数据。
     忽略服务器名的细微差别，如实报告说该服务器无日志。

输出用 Markdown 格式：
📋 **日志分析结论**
- 服务器：xxx
- 时间范围：xxx
- 日志分布：error=N, warn=N, info=N
- 主要异常：xxx
- 关键样本：xxx
- 建议：xxx"""

log_worker_agent = create_react_agent(
    model=_LLM,
    tools=[query_logs, analyze_errors, count_by_level],
    prompt=_LOG_PROMPT,
)

# ── Infra Worker Agent ──────────────────────────────────────

_INFRA_PROMPT = """你是一个基础设施指标分析专家，通过 Prometheus 监控系统排查问题。

可用工具：
- **query_metric**(metric_name, server_ip) — 查询指标当前值
  metric_name 是 PromQL 表达式，例如：
  - 100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)
  - (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100
  - (1 - node_filesystem_free_bytes / node_filesystem_size_bytes) * 100
  server_ip 是服务器 IP 地址（从上下文推断）
- **range_query**(metric_name, server_ip, duration) — 查询历史趋势
- **check_alerts**() — 查看当前活跃告警

工作流程：
1. 先查出要分析的服务器 IP
2. 分别查 CPU、内存、磁盘三个核心指标
3. 调 check_alerts 查看是否有相关告警
4. 超过 80% 的指标标记为异常
5. 需要深入了解趋势时调 range_query
6. 返回分析结论

如果 Prometheus 无数据（data_available=false），说明 node_exporter 未部署，
如实报告即可，不要编造数据。

输出用 Markdown 格式：
📊 **基础设施分析结论**
- 服务器：xxx
- CPU：xx%（↑ 异常/正常）
- 内存：xx%（↑ 异常/正常）
- 磁盘：xx%（↑ 异常/正常）
- 关联告警：xxx
- 建议：xxx"""

infra_worker_agent = create_react_agent(
    model=_LLM,
    tools=[query_metric, range_query, check_alerts],
    prompt=_INFRA_PROMPT,
)

# ── Knowledge Worker Agent ──────────────────────────────────

_KNOWLEDGE_PROMPT = """你是一个运维知识库专家，通过 RAG 知识库检索运维文档和故障处理方案。

可用工具：
- **search_knowledge_base**(query, top_k) — 语义搜索运维知识文档

工作流程：
1. 从用户问题中提取关键词（服务器名、故障类型、组件名）
2. 用精确的关键词构造搜索 query
3. top_k 默认 3，复杂问题可调到 5
4. 从结果中提取：故障原因、解决方案、命令示例
5. 如实报告搜索结果

注意：如果搜不到相关内容，说"知识库中未找到相关信息"即可。
     不要编造不存在的内容。

输出用 Markdown 格式：
📚 **知识库检索结果**
- 搜索关键词：xxx
- 找到 N 条相关文档
- 关键内容：xxx
- 适用建议：xxx"""

knowledge_worker_agent = create_react_agent(
    model=_LLM,
    tools=[search_knowledge_base],
    prompt=_KNOWLEDGE_PROMPT,
)

# ── 兼容函数模式 ────────────────────────────────────────────


def log_worker(server_name: str, hours: int = 1) -> dict:
    """[兼容] 日志分析 Worker 函数模式，使用 Agent 内部逻辑

    Args:
        server_name: 服务器名称
        hours: 查询时间范围

    Returns:
        包含错误统计、样本和级别分布的字典
    """
    return _run_agent_as_function(
        log_worker_agent,
        f"分析服务器 {server_name} 过去 {hours} 小时的日志情况",
    )


def infra_worker(server_name: str, server_ip: str = "") -> dict:
    """[兼容] 基础设施 Worker 函数模式

    Args:
        server_name: 服务器名称
        server_ip: 服务器 IP（可选）

    Returns:
        包含 CPU/内存/磁盘指标和告警的字典
    """
    return _run_agent_as_function(
        infra_worker_agent,
        f"检查服务器 {server_name} 的 CPU、内存、磁盘指标和告警",
    )


def knowledge_worker(query: str, top_k: int = 3) -> dict:
    """[兼容] 知识库 Worker 函数模式

    Args:
        query: 搜索查询
        top_k: 返回文档数量

    Returns:
        搜索结果字典
    """
    return _run_agent_as_function(
        knowledge_worker_agent,
        f"搜索运维知识库：{query}，返回 {top_k} 条结果",
    )


def _run_agent_as_function(agent, question: str) -> dict:
    """让 ReAct Agent 以函数模式运行，返回结构化的 dict"""
    try:
        result = agent.invoke({"messages": [("human", question)]})
        return {
            "conclusion": result["messages"][-1].content,
            "data_available": True,
        }
    except Exception as e:
        return {
            "conclusion": f"分析异常: {e}",
            "data_available": False,
            "error": str(e),
        }


__all__ = [
    "log_worker_agent",
    "infra_worker_agent",
    "knowledge_worker_agent",
    "log_worker",
    "infra_worker",
    "knowledge_worker",
]
