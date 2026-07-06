"""LangGraph Supervisor — 多 Agent 状态机

架构:
  用户输入 → Supervisor（LLM 决策路由）
    ├→ log_worker_agent → 回到 Supervisor
    ├→ infra_worker_agent → 回到 Supervisor
    ├→ knowledge_worker_agent → 回到 Supervisor
    └→ FINISH → 生成 RCA 报告

每个 Worker 是独立 ReAct Agent（LLM + system prompt + tools），
自主理解用户意图并执行分析，返回分析结论文本。
"""

import json
import os
from typing import Annotated, Literal, Sequence, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from llm.workers import (
    infra_worker_agent,
    knowledge_worker_agent,
    log_worker_agent,
)

# LLM 实例
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
    intermediate_results: dict       # {worker_name: "分析结论文本"}
    final_report: str
    iteration: int


def _make_supervisor_prompt() -> str:
    """生成 Supervisor 系统提示词"""
    return """你是一个运维指挥中心的主管（Supervisor）。你的团队有三个专家：
1. **log_worker** — 日志分析专家，通过 Loki 查日志、分析错误码、统计级别
2. **infra_worker** — 基础设施专家，通过 Prometheus 查 CPU/内存/磁盘/告警
3. **knowledge_worker** — 知识库专家，检索运维文档和故障处理方案

【决策规则】
- 如果需要分析日志 → next = log_worker
- 如果需要查看系统指标或告警 → next = infra_worker
- 如果需要查运维知识或故障处理方案 → next = knowledge_worker
- 如果各专家的信息已经足够回答用户 → next = FINISH
- 如果用户问题不需要任何数据查询 → next = FINISH

【已有数据】
各专家返回的分析结论如下：
{info}

【当前轮次】{iteration}/{MAX_ITERATIONS}

【输出格式】
只输出一行 JSON：
{{"next": "worker_name", "reason": "为什么选这个worker"}}
或当信息足够时：
{{"next": "FINISH", "reason": "为什么结束", "report": "RCA 报告内容"}}

RCA 报告请用 Markdown 格式：
# RCA 诊断报告
## 📋 概要
## 🕐 时间线
## 🔍 根因
## 📊 证据（引用各专家结论）
## 🔧 修复建议
## 💡 预防措施"""


def supervisor_node(state: AgentState) -> dict:
    """Supervisor LLM 节点 — 决定下一步路由"""
    info_summary = _summarize_results(state.get("intermediate_results", {}))
    iteration = state.get("iteration", 0)
    prompt = _make_supervisor_prompt().format(
        iteration=iteration + 1,
        MAX_ITERATIONS=MAX_ITERATIONS,
        info=info_summary or "尚无数据，尚无专家报告",
    )

    try:
        resp = _LLM.invoke([("system", prompt), *state["messages"]])
        decision = json.loads(
            resp.content.strip().strip("```json").strip("```").strip()
        )
    except Exception as e:
        import traceback

        print(f"[supervisor] LLM 决策失败: {e}\n{traceback.format_exc()}", flush=True)
        fallback = _auto_report(state.get("intermediate_results", {}))
        return {
            "next": "FINISH",
            "final_report": f"【诊断报告（自动生成）】\n{fallback}",
        }

    decision_next = decision.get("next", "FINISH")

    if decision_next == "FINISH":
        report = decision.get("report", _auto_report(state["intermediate_results"]))
        return {"next": "FINISH", "final_report": report}

    return {"next": decision_next}


def _summarize_results(results: dict) -> str:
    """将 intermediate_results（各专家文本结论）简化为摘要"""
    if not results:
        return ""
    parts = []
    for worker, text in results.items():
        if not text:
            parts.append(f"【{worker}】无数据")
        else:
            # 取前 300 字作为摘要
            summary = text[:300]
            if len(text) > 300:
                summary += "...（以下省略）"
            parts.append(f"【{worker}】\n{summary}")
    return "\n\n".join(parts)


def _auto_report(results: dict) -> str:
    """当 LLM 未生成 report 时的兜底报告"""
    if not results:
        return "暂无数据可生成报告。"
    lines = ["# 诊断报告（自动生成）", ""]
    for worker, text in results.items():
        readable = worker.replace("_", " ").title()
        lines.append(f"## {readable}")
        lines.append(text if text else "无数据")
        lines.append("")
    lines.append("_报告由 Supervisor 自动汇总_")
    return "\n".join(lines)


# ── Worker 节点（调用 ReAct Agent） ──────────────────────────


def log_worker_node(state: AgentState) -> dict:
    """日志 Worker 节点 — 调用 log_worker_agent"""
    question = state["messages"][-1].content if state["messages"] else "分析日志"
    try:
        result = log_worker_agent.invoke({"messages": [("human", question)]})
        response = result["messages"][-1].content
    except Exception as e:
        response = f"❌ 日志分析 Agent 异常: {e}"

    return {
        "intermediate_results": {
            **state.get("intermediate_results", {}),
            "log_worker": response,
        },
        "iteration": state.get("iteration", 0) + 1,
    }


def infra_worker_node(state: AgentState) -> dict:
    """基础设施 Worker 节点 — 调用 infra_worker_agent"""
    question = state["messages"][-1].content if state["messages"] else "检查服务器指标"
    try:
        result = infra_worker_agent.invoke({"messages": [("human", question)]})
        response = result["messages"][-1].content
    except Exception as e:
        response = f"❌ 基础设施分析 Agent 异常: {e}"

    return {
        "intermediate_results": {
            **state.get("intermediate_results", {}),
            "infra_worker": response,
        },
        "iteration": state.get("iteration", 0) + 1,
    }


def knowledge_worker_node(state: AgentState) -> dict:
    """知识库 Worker 节点 — 调用 knowledge_worker_agent"""
    question = state["messages"][-1].content if state["messages"] else "搜索运维知识"
    try:
        result = knowledge_worker_agent.invoke({"messages": [("human", question)]})
        response = result["messages"][-1].content
    except Exception as e:
        response = f"❌ 知识库检索 Agent 异常: {e}"

    return {
        "intermediate_results": {
            **state.get("intermediate_results", {}),
            "knowledge_worker": response,
        },
        "iteration": state.get("iteration", 0) + 1,
    }


def should_continue(state: AgentState) -> Literal["continue", "end"]:
    """条件边：判断是否继续循环"""
    if state.get("next") == "FINISH":
        return "end"
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        return "end"
    return "continue"


def finish_node(state: AgentState) -> dict:
    """结束节点 — 确保 final_report 进入最终状态"""
    report = state.get("final_report", "")
    if not report:
        report = _auto_report(state.get("intermediate_results", {}))
    return {"final_report": report}


# ── 构建图 ──────────────────────────────────────────────────


def build_supervisor() -> StateGraph:
    """构建并返回 Supervisor StateGraph"""
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("log_worker", log_worker_node)
    graph.add_node("infra_worker", infra_worker_node)
    graph.add_node("knowledge_worker", knowledge_worker_node)
    graph.add_node("finish", finish_node)

    # 入口 → Supervisor
    graph.set_entry_point("supervisor")

    # Supervisor → Worker（根据 next 字段路由）
    graph.add_conditional_edges(
        "supervisor",
        lambda s: s.get("next", "FINISH"),
        {
            "log_worker": "log_worker",
            "infra_worker": "infra_worker",
            "knowledge_worker": "knowledge_worker",
            "FINISH": "finish",
        },
    )

    # Worker → Supervisor（每个 Worker 执行完都回到 Supervisor）
    for worker in ("log_worker", "infra_worker", "knowledge_worker"):
        graph.add_conditional_edges(
            worker,
            should_continue,
            {"continue": "supervisor", "end": "finish"},
        )

    # finish → END
    graph.add_edge("finish", END)

    return graph.compile()
