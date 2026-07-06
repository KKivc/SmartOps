"""Worker 工具函数测试 — Workers 使用 ReAct Agent 模式"""
from unittest.mock import patch, MagicMock


def test_log_worker_agent_import():
    """log_worker_agent 是 ReAct Agent，可导入"""
    from llm.workers import log_worker_agent
    assert log_worker_agent is not None


def test_infra_worker_agent_import():
    """infra_worker_agent 是 ReAct Agent，可导入"""
    from llm.workers import infra_worker_agent
    assert infra_worker_agent is not None


def test_knowledge_worker_agent_import():
    """knowledge_worker_agent 是 ReAct Agent，可导入"""
    from llm.workers import knowledge_worker_agent
    assert knowledge_worker_agent is not None


@patch("llm.workers.log_worker_agent")
def test_log_worker_function_mode(mock_agent):
    """log_worker 函数模式通过 ReAct Agent 返回结论"""
    import json
    mock_agent.invoke.return_value = {
        "messages": [MagicMock(), MagicMock(content="📋 **日志分析结论**\n- 服务器：web-01\n- 错误数量：2")]
    }

    from llm.workers import log_worker
    result = log_worker("web-01", hours=2)

    assert result["data_available"] is True
    assert "结论" in result["conclusion"]


@patch("llm.workers.infra_worker_agent")
def test_infra_worker_function_mode(mock_agent):
    """infra_worker 函数模式通过 ReAct Agent 返回指标分析"""
    mock_agent.invoke.return_value = {
        "messages": [MagicMock(), MagicMock(content="📊 **基础设施分析结论**\n- CPU：45%\n- 内存：62%")]
    }

    from llm.workers import infra_worker
    result = infra_worker("web-01", server_ip="10.0.0.1")

    assert result["data_available"] is True
    assert "CPU" in result["conclusion"]


@patch("llm.workers.knowledge_worker_agent")
def test_knowledge_worker_function_mode(mock_agent):
    """knowledge_worker 函数模式通过 ReAct Agent 返回知识库检索结果"""
    mock_agent.invoke.return_value = {
        "messages": [MagicMock(), MagicMock(content="📚 **知识库检索结果**\n- 找到 2 条相关文档")]
    }

    from llm.workers import knowledge_worker
    result = knowledge_worker("CPU 过高怎么办", top_k=2)

    assert result["data_available"] is True


@patch("llm.workers.log_worker_agent")
def test_log_worker_error(mock_agent):
    """log_worker Agent 异常时返回错误信息"""
    mock_agent.invoke.side_effect = Exception("API 超时")

    from llm.workers import log_worker
    result = log_worker("web-01")

    assert result["data_available"] is False
    assert "error" in result


@patch("llm.workers.knowledge_worker_agent")
def test_knowledge_worker_error(mock_agent):
    """knowledge_worker Agent 异常时返回错误信息"""
    mock_agent.invoke.side_effect = Exception("知识库连接失败")

    from llm.workers import knowledge_worker
    result = knowledge_worker("test")

    assert result["data_available"] is False
    assert "error" in result
