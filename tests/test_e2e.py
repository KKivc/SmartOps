"""端到端集成测试"""
from unittest.mock import patch, MagicMock


@patch("llm.agent._supervisor")
@patch("llm.agent.get_session")
def test_full_chat_flow(mock_session, mock_sv):
    """完整对话流程：用户输入 → Agent → 返回回复"""
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess
    mock_sess.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    mock_sv.invoke.return_value = {"final_report": "分析完成：web-01 CPU 使用率 45%，内存 62%，状态正常。"}

    from llm.agent import chat
    result = chat(conversation_id=1, user_input="web-01 状态如何？")

    assert "CPU" in result
    assert "内存" in result


@patch("llm.workers.log_worker_agent")
@patch("llm.workers.infra_worker_agent")
@patch("llm.workers.knowledge_worker_agent")
def test_all_worker_agents_importable(mock_kw, mock_iw, mock_lw):
    """三个 Worker Agent 均可导入"""
    from llm.workers import log_worker_agent, infra_worker_agent, knowledge_worker_agent
    assert log_worker_agent is not None
    assert infra_worker_agent is not None
    assert knowledge_worker_agent is not None


@patch("llm.workers.log_worker_agent")
def test_log_worker_via_agent(mock_agent):
    """log_worker 通过 ReAct Agent 调用"""
    mock_agent.invoke.return_value = {
        "messages": [MagicMock(), MagicMock(content="📋 **日志分析结论**\n- 错误数量：5")]
    }

    from llm.workers import log_worker
    result = log_worker("web-01", hours=2)

    assert result["data_available"] is True
    assert "错误" in result["conclusion"]


@patch("llm.workers.infra_worker_agent")
def test_infra_worker_via_agent(mock_agent):
    """infra_worker 通过 ReAct Agent 调用"""
    mock_agent.invoke.return_value = {
        "messages": [MagicMock(), MagicMock(content="📊 **指标分析**\n- CPU: 85.3%")]
    }

    from llm.workers import infra_worker
    result = infra_worker("web-01")

    assert result["data_available"] is True


@patch("llm.workers.knowledge_worker_agent")
def test_knowledge_worker_via_agent(mock_agent):
    """knowledge_worker 通过 ReAct Agent 调用"""
    mock_agent.invoke.return_value = {
        "messages": [MagicMock(), MagicMock(content="📚 **知识库结果**\n- 找到 1 条文档")]
    }

    from llm.workers import knowledge_worker
    result = knowledge_worker("nginx 配置")

    assert result["data_available"] is True


def test_mcp_tools_import():
    """MCP 工具可全部导入"""
    from llm.mcp.loki_mcp import query_logs, analyze_errors, count_by_level
    from llm.mcp.prometheus_mcp import query_metric, range_query, check_alerts
    assert all(hasattr(t, 'invoke') for t in [
        query_logs, analyze_errors, count_by_level,
        query_metric, range_query, check_alerts,
    ])


def test_supervisor_graph_structure():
    """Supervisor 的 StateGraph 结构正确"""
    from llm.supervisor import build_supervisor, MAX_ITERATIONS
    graph = build_supervisor()
    assert graph is not None
    assert MAX_ITERATIONS == 10
