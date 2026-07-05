"""LangGraph Supervisor — 多 Agent 状态机

架构:
  用户输入 → Supervisor（LLM 决策路由）
    ├→ log_worker → 回到 Supervisor
    ├→ infra_worker → 回到 Supervisor
    ├→ knowledge_worker → 回到 Supervisor
    └→ FINISH → 生成 RCA 报告

工作流程:
  1. Supervisor 节点用 LLM 推理，输出 next 路由
  2. 对应 Worker 执行数据查询，存入 intermediate_results
  3. 回到 Supervisor 继续推理，直到 next=FINISH
  4. 生成 final_report
"""

import json
from typing import Annotated, Literal, Sequence, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from llm.workers import infra_worker, knowledge_worker, log_worker

# LLM 实例（复用 agent.py 的配置）
import os
_LLM = ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://opencode.ai/zen/go/v1",
    api_key=os.getenv("OPENCODE_API_KEY"),
)

MAX_ITERATIONS = 10


class AgentState(TypedDict):
    """StateGraph 全局状态"""
    messages: Annotated[Sequence[dict], add_messages]
    next: Literal["FINISH", "log_worker", "infra_worker", "knowledge_worker"]
    intermediate_results: dict
    final_report: str
    iteration: int


def _make_supervisor_prompt() -> str:
    """生成 Supervisor 系统提示词"""
    return """你是一个运维指挥中心的主管（Supervisor）。你的团队有三个工人：
1. **log_worker** — 查 Loki 日志（查询日志、分析错误码、按级别统计）
2. **infra_worker** — 查 Prometheus 指标 + 告警（CPU/内存/磁盘）
3. **knowledge_worker** — 查知识库（运维文档、历史故障）

【决策规则】
- 如果需要分析日志问题 → next = log_worker
- 如果需要查看系统指标 → next = infra_worker
- 如果需要查运维知识 → next = knowledge_worker
- 如果信息已经足够 → next = FINISH

【当前迭代次数】{iteration}/{MAX_ITERATIONS}
【已收集数据】{info}

【输出格式】
只输出一个 JSON 对象：
{{"next": "worker_name", "reason": "为什么选这个worker"}}
或
{{"next": "FINISH", "reason": "为什么结束", "report": "RCA 报告内容"}}
"""


def supervisor_node(state: AgentState) -> dict:
    """Supervisor LLM 节点 — 决定下一步路由"""
    info_summary = _summarize_results(state["intermediate_results"])
    iteration = state.get("iteration", 0)
    prompt = _make_supervisor_prompt().format(
        iteration=iteration + 1,
        MAX_ITERATIONS=MAX_ITERATIONS,
        info=info_summary or "尚无数据",
    )

    llm = _LLM

    try:
        resp = llm.invoke([("system", prompt), *state["messages"]])
        decision = json.loads(resp.content.strip().strip("```json").strip("```").strip())
    except Exception:
        # 解析失败时终止
        return {
            "next": "FINISH",
            "final_report": f"【Supervisor 决策异常】已收集的数据：{info_summary or '无'}",
        }

    if decision.get("next") == "FINISH":
        report = decision.get("report", _auto_report(state["intermediate_results"]))
        return {"next": "FINISH", "final_report": report}

    return {"next": decision["next"]}


def _summarize_results(results: dict) -> str:
    """将 intermediate_results 简化为带关键数值的描述文本"""
    if not results:
        return ""
    parts = []
    for worker, data in results.items():
        if isinstance(data, dict):
            # 提取关键数值字段，忽略 metadata 字段
            vals = []
            for k, v in data.items():
                if v is None or k in ("server_name", "server_ip"):
                    continue
                if isinstance(v, (int, float)):
                    vals.append(f"{k}={v:.1f}" if isinstance(v, float) else f"{k}={v}")
                elif isinstance(v, str) and v:
                    vals.append(f"{k}={v[:30]}")
                elif isinstance(v, bool):
                    vals.append(f"{k}={v}")
            if vals:
                parts.append(f"{worker}: {', '.join(vals)}")
            else:
                parts.append(f"{worker}: 无数据")
        else:
            parts.append(f"{worker}: {str(data)[:100]}")
    return "; ".join(parts)


def _auto_report(results: dict) -> str:
    """当 LLM 未生成 report 时的兜底报告"""
    lines = ["# 诊断报告", ""]
    for worker, data in results.items():
        lines.append(f"## {worker.replace('_', ' ').title()}")
        if isinstance(data, dict):
            if data.get("data_available") is False:
                lines.append("- Prometheus 暂无指标数据，请确认 node_exporter 已安装")
            elif data.get("error"):
                lines.append(f"- 错误: {data['error']}")
            else:
                for k, v in data.items():
                    if k in ("server_name", "server_ip", "data_available"):
                        continue
                    if v is None:
                        lines.append(f"- {k}: 无数据")
                    elif isinstance(v, (int, float)):
                        lines.append(f"- {k}: {v:.1f}%")
                    else:
                        lines.append(f"- {k}: {str(v)[:200]}")
        else:
            lines.append(f"- {str(data)[:200]}")
    lines.append("")
    lines.append("_报告由 Supervisor 自动生成_")
    return "\n".join(lines)


def log_worker_node(state: AgentState) -> dict:
    """日志 Worker 节点"""
    last_msg = state["messages"][-1].content if state["messages"] else ""
    # 从用户消息中尝试提取服务器名
    server_name = _extract_server(last_msg)

    try:
        result = log_worker(server_name)
    except Exception as e:
        result = {"error": str(e)}
    return {
        "intermediate_results": {**state.get("intermediate_results", {}), "log_worker": result},
        "iteration": state.get("iteration", 0) + 1,
    }


def infra_worker_node(state: AgentState) -> dict:
    """基础设施 Worker 节点"""
    last_msg = state["messages"][-1].content if state["messages"] else ""
    server_name = _extract_server(last_msg)

    try:
        result = infra_worker(server_name)
    except Exception as e:
        result = {"error": str(e)}
    return {
        "intermediate_results": {**state.get("intermediate_results", {}), "infra_worker": result},
        "iteration": state.get("iteration", 0) + 1,
    }


def knowledge_worker_node(state: AgentState) -> dict:
    """知识库 Worker 节点"""
    last_msg = state["messages"][-1].content if state["messages"] else ""
    try:
        result = knowledge_worker(last_msg)
    except Exception as e:
        result = {"error": str(e)}
    return {
        "intermediate_results": {**state.get("intermediate_results", {}), "knowledge_worker": result},
        "iteration": state.get("iteration", 0) + 1,
    }


def _extract_server(text: str) -> str:
    """从用户输入中尝试提取服务器名，兜底返回 'unknown'"""
    if not text:
        return "unknown"
    # 简单启发式：找 server/服务器 后的词
    import re
    m = re.search(r"(?:server|服务器|主机)[s:]?\s*(\S+)", text, re.IGNORECASE)
    return m.group(1) if m else "unknown"


def should_continue(state: AgentState) -> Literal["continue", "end"]:
    """条件边：判断是否继续循环"""
    if state.get("next") == "FINISH":
        return "end"
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        return "end"
    return "continue"


def build_supervisor() -> StateGraph:
    """构建并返回 Supervisor StateGraph"""
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("log_worker", log_worker_node)
    graph.add_node("infra_worker", infra_worker_node)
    graph.add_node("knowledge_worker", knowledge_worker_node)

    # 入口 → Supervisor
    graph.set_entry_point("supervisor")

    # Supervisor → Worker (根据 next 字段路由)
    graph.add_conditional_edges(
        "supervisor",
        lambda s: s.get("next", "FINISH"),
        {
            "log_worker": "log_worker",
            "infra_worker": "infra_worker",
            "knowledge_worker": "knowledge_worker",
            "FINISH": END,
        },
    )

    # Worker → Supervisor（每个 Worker 执行完都回到 Supervisor）
    for worker in ("log_worker", "infra_worker", "knowledge_worker"):
        graph.add_conditional_edges(
            worker,
            should_continue,
            {"continue": "supervisor", "end": END},
        )

    return graph.compile()
