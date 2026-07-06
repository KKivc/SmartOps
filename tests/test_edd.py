"""
Agent EDD（Evaluation-Driven Development）评估脚本

评估维度：
  A-01 工具调用正确性 — Supervisor 路由决策和 Worker 工具注册
  A-02 信息覆盖率 — Agent 输出是否覆盖关键信息
  A-03 RCA 结构完整性 — 诊断报告格式

运行方式：
  python tests/test_edd.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 评分计数器 ────────────────────────────────────────────────

results = {"pass": 0, "fail": 0, "total": 0}


def check(name: str, condition: bool, detail: str = ""):
    results["total"] += 1
    status = "[PASS]" if condition else "[FAIL]"
    results["pass" if condition else "fail"] += 1
    print(f"  {status} {name}")
    if not condition and detail:
        print(f"     -> {detail}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════
# A-01: 工具调用正确性
# ═══════════════════════════════════════════════════════════════

section("A-01: 工具调用正确性")


def check_supervisor_routing():
    """用 mock LLM 验证 Supervisor 路由决策"""
    from unittest.mock import patch, MagicMock
    from llm.supervisor import supervisor_node

    test_cases = [
        {
            "name": "日志查询 → log_worker",
            "query": "查看 web-01 的日志",
            "expected_next": "log_worker",
            "llm_response": json.dumps({"next": "log_worker", "reason": "需要看日志", "sub_question": "分析 web-01 的日志"}),
        },
        {
            "name": "指标查询 → infra_worker",
            "query": "查看 web-01 的 CPU",
            "expected_next": "infra_worker",
            "llm_response": json.dumps({"next": "infra_worker", "reason": "需要查CPU", "sub_question": "检查 web-01 的 CPU 指标"}),
        },
        {
            "name": "知识查询 → knowledge_worker",
            "query": "nginx 怎么配置",
            "expected_next": "knowledge_worker",
            "llm_response": json.dumps({"next": "knowledge_worker", "reason": "查知识库", "sub_question": "搜索 nginx 配置方案"}),
        },
        {
            "name": "普通对话 → FINISH",
            "query": "你好",
            "expected_next": "FINISH",
            "llm_response": json.dumps({"next": "FINISH", "reason": "无需查数据"}),
        },
    ]

    with patch("llm.supervisor._LLM") as mock_llm:
        for tc in test_cases:
            mock_resp = MagicMock()
            mock_resp.content = tc["llm_response"]
            mock_llm.invoke.return_value = mock_resp

            state = {
                "messages": [("human", tc["query"])],
                "next": "supervisor",
                "intermediate_results": {},
                "final_report": "",
                "iteration": 0,
            }
            result = supervisor_node(state)
            check(
                f"路由测试: {tc['name']}",
                result.get("next") == tc["expected_next"],
                f"期望 {tc['expected_next']}, 得到 {result.get('next')}",
            )


def check_worker_tool_registration():
    """验证每个 Worker Agent 创建成功且工具正确注册"""
    from llm.workers import log_worker_agent, infra_worker_agent, knowledge_worker_agent

    # Agent 是 CompiledStateGraph，验证可调用
    check("Log Worker Agent 可调用", hasattr(log_worker_agent, "invoke"))
    check("Infra Worker Agent 可调用", hasattr(infra_worker_agent, "invoke"))
    check("Knowledge Worker Agent 可调用", hasattr(knowledge_worker_agent, "invoke"))

    # 直接在 workers 模块中检查 prompt 常量
    import llm.workers as w

    lp = str(w._LOG_PROMPT)
    check("Log Worker prompt 描述 query_logs", "query_logs" in lp)
    check("Log Worker prompt 描述 analyze_errors", "analyze_errors" in lp)
    check("Log Worker prompt 描述 count_by_level", "count_by_level" in lp)

    ip = str(w._INFRA_PROMPT)
    check("Infra Worker prompt 描述 query_metric", "query_metric" in ip)
    check("Infra Worker prompt 描述 range_query", "range_query" in ip)
    check("Infra Worker prompt 描述 check_alerts", "check_alerts" in ip)
    check("Infra Worker prompt 描述 get_server_list（名称→IP）", "get_server_list" in ip,
          f"实际: infra_worker prompt 缺 get_server_list")

    kp = str(w._KNOWLEDGE_PROMPT)
    check("Knowledge Worker prompt 描述 search_knowledge_base", "search_knowledge_base" in kp)


def check_worker_prompts():
    """验证 Worker Prompt 格式修复是否生效"""
    import llm.workers as w

    ip = str(w._INFRA_PROMPT)
    # 验证 PromQL 修复：prompt 里用裸指标名而非长 PromQL 表达式
    check("Infra Worker prompt 用裸指标名（如 node_cpu_seconds_total）",
          "node_cpu_seconds_total" in ip and "100 - (avg" not in ip)
    check("Infra Worker prompt 不含错误的长 PromQL",
          "100 - (avg by(instance)" not in ip)


def check_supervisor_sub_question():
    """验证 Supervisor 的 sub_question 机制"""
    from unittest.mock import patch, MagicMock
    from llm.supervisor import (
        supervisor_node, log_worker_node,
        infra_worker_node, knowledge_worker_node,
    )

    with patch("llm.supervisor._LLM") as mock_llm:
        mock_resp = MagicMock()
        mock_resp.content = json.dumps({
            "next": "log_worker",
            "reason": "需要分析日志",
            "sub_question": "检查 web-01 过去 1 小时的 500 错误",
        })
        mock_llm.invoke.return_value = mock_resp

        state = {
            "messages": [("human", "查一下 web-01 的 500 错误")],
            "next": "supervisor",
            "intermediate_results": {},
            "final_report": "",
            "iteration": 0,
        }
        result = supervisor_node(state)
        check("Supervisor 提取 sub_question",
              result.get("sub_question") == "检查 web-01 过去 1 小时的 500 错误",
              f"实际: {result.get('sub_question')}")

    # 验证 Worker 节点优先使用 sub_question
    with patch("llm.supervisor.log_worker_agent") as mock_agent:
        mock_agent.invoke.return_value = {"messages": [MagicMock(), MagicMock(content="结论")]}
        worker_state = {
            "sub_question": "检查 web-01 past 1h 500 error",
            "messages": [("human", "很长很复杂的原始问题")],
            "intermediate_results": {},
            "iteration": 0,
        }
        log_worker_node(worker_state)
        call_arg = mock_agent.invoke.call_args[0][0]["messages"][0][1]
        check("Worker 节点使用 sub_question 而非原始问题",
              "检查 web-01" in call_arg and "很长很复杂" not in call_arg,
              f"实际传入 Worker: {call_arg[:60]}...")


check_supervisor_routing()
check_worker_tool_registration()
check_worker_prompts()
check_supervisor_sub_question()


# ═══════════════════════════════════════════════════════════════
# A-02: 信息覆盖率（静态验证）
# ═══════════════════════════════════════════════════════════════

section("A-02: 信息覆盖率")


def check_prompt_coverage():
    """检查各 Worker prompt 要求输出的关键信息点"""
    import llm.workers as w

    lp = str(w._LOG_PROMPT)
    check("Log Worker prompt 要求输出错误分布", "error" in lp)
    check("Log Worker prompt 要求输出日志级别", "级别" in lp or "error=" in lp)
    check("Log Worker prompt 要求输出样本", "样本" in lp or "关键" in lp)

    ip = str(w._INFRA_PROMPT)
    check("Infra Worker prompt 要求输出 CPU", "CPU" in ip)
    check("Infra Worker prompt 要求输出内存", "内存" in ip)
    check("Infra Worker prompt 要求输出磁盘", "磁盘" in ip)
    check("Infra Worker prompt 要求输出告警", "告警" in ip and ("check_alerts" in ip or "alerts" in ip))
    check("Infra Worker prompt 要求输出异常标记", "异常" in ip)

    kp = str(w._KNOWLEDGE_PROMPT)
    check("Knowledge Worker prompt 要求输出搜索关键词", "关键词" in kp or "query" in kp)
    check("Knowledge Worker prompt 要求输出解决建议", "建议" in kp or "solution" in kp)


def check_finish_node_coverage():
    """检查 finish_node 的 RCA prompt 要求的关键信息"""
    from llm.supervisor import _auto_report, AgentState, finish_node

    # 测试 _auto_report
    test_results = {
        "log_worker": "发现 23 个错误，500=15",
        "infra_worker": "CPU 95%，内存 72%",
    }
    report = _auto_report(test_results)
    check("_auto_report 包含 Worker 结论文本",
          "Log Worker" in report and "Infra Worker" in report)
    check("_auto_report 包含原始数据", "23" in report and "95%" in report)

    # 测试 finish_node 的 RCA prompt 格式
    # 注意：实际 graph 执行时消息会被 add_messages 转为对象
    # 测试中直接用 HumanMessage
    from langchain_core.messages import HumanMessage
    state: AgentState = {
        "messages": [HumanMessage(content="web-01 出了什么问题？")],
        "next": "FINISH",
        "intermediate_results": test_results,
        "final_report": "",
        "iteration": 3,
    }

    from unittest.mock import patch, MagicMock
    with patch("llm.supervisor._LLM") as mock_llm:
        mock_resp = MagicMock()
        mock_resp.content = "# RCA 诊断报告\n\n## 📋 概要\n502 错误"
        mock_llm.invoke.return_value = mock_resp

        result = finish_node(state)
        report_out = result.get("final_report", "")
        check("finish_node 生成报告", len(report_out) > 0)


check_prompt_coverage()
check_finish_node_coverage()


# ═══════════════════════════════════════════════════════════════
# A-03: RCA 结构完整性
# ═══════════════════════════════════════════════════════════════

section("A-03: RCA 结构完整性")


def check_rca_prompt_structure():
    """检查 RCA 生成 prompt 是否要求完整结构"""
    from llm.supervisor import finish_node

    # 读取 finish_node 中的 RCA prompt（通过检查函数源码字符串）
    import inspect
    source = inspect.getsource(finish_node)

    required_sections = [
        ("RCA 诊断报告", "# RCA"),
        ("根因分析", "根因"),
        ("修复建议", "修复建议"),
        ("预防措施", "预防措施"),
        ("概要/摘要", "概要"),
    ]
    for name, keyword in required_sections:
        check(f"RCA prompt 要求 {name}", keyword in source, f"未找到 '{keyword}'")


def check_rca_output_format():
    """验证在已有数据时 finish_node 能输出正确格式"""
    from unittest.mock import patch, MagicMock
    from llm.supervisor import finish_node, _auto_report
    from langchain_core.messages import HumanMessage

    # 测试 _auto_report 兜底
    empty_report = _auto_report({})
    check("空数据 _auto_report 含友好提示", "暂无数据" in empty_report)

    full_results = {
        "log_worker": "发现 23 个错误，500=15, 502=5, 504=3",
        "infra_worker": "CPU 95%（异常），内存 72%（正常）",
        "knowledge_worker": "nginx upstream 超时的常见原因及处理",
    }
    full_report = _auto_report(full_results)
    check("_auto_report 包含三个 Worker",
          "Log Worker" in full_report and "Infra Worker" in full_report and "Knowledge Worker" in full_report)
    check("_auto_report 包含关键数据", "500=15" in full_report and "95%" in full_report)

    # 测试 finish_node 用 LLM 生成报告
    with patch("llm.supervisor._LLM") as mock_llm:
        mock_resp = MagicMock()
        mock_resp.content = "# RCA 诊断报告\n\n## 📋 概要\n502 错误\n\n## 🔍 根因\n上游超时\n\n## 🔧 修复建议\n1. 增大 timeout"
        mock_llm.invoke.return_value = mock_resp

        state = {
            "messages": [HumanMessage(content="web-01 502 报错")],
            "next": "FINISH",
            "intermediate_results": full_results,
            "final_report": "",
            "iteration": 3,
        }
        result = finish_node(state)
        report = result.get("final_report", "")
        check("finish_node LLM 报告含根因", "根因" in report or "上游" in report)
        check("finish_node LLM 报告含修复建议", "修复" in report or "建议" in report or "timeout" in report)


def check_rca_fallback_for_normal_qa():
    """非故障场景不需要 RCA 格式"""
    from llm.supervisor import finish_node
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content="你好")],
        "next": "FINISH",
        "intermediate_results": {},
        "final_report": "",
        "iteration": 0,
    }
    result = finish_node(state)
    check("普通问答返回友好回复", "助手" in result.get("final_report", ""))


check_rca_prompt_structure()
check_rca_output_format()
check_rca_fallback_for_normal_qa()


# ═══════════════════════════════════════════════════════════════
# 结果汇总
# ═══════════════════════════════════════════════════════════════

section("结果汇总")
print(f"  总计: {results['total']}  |  ✅ 通过: {results['pass']}  |  ❌ 失败: {results['fail']}")
print(f"  通过率: {results['pass']/results['total']*100:.1f}%" if results['total'] > 0 else "  无测试项")

exit(0 if results["fail"] == 0 else 1)
