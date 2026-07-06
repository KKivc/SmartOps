"""MCP 模块导入测试"""
from unittest.mock import patch, MagicMock


def test_loki_mcp_import():
    from llm.mcp.loki_mcp import query_logs, analyze_errors, count_by_level
    assert query_logs is not None
    assert analyze_errors is not None
    assert count_by_level is not None


def test_prometheus_mcp_import():
    from llm.mcp.prometheus_mcp import query_metric, range_query, check_alerts
    assert query_metric is not None
    assert range_query is not None
    assert check_alerts is not None


def test_mcp_imports():
    from llm.mcp import CLOUD_LOKI_URL, CLOUD_PROMETHEUS_URL
    assert CLOUD_LOKI_URL is not None
    assert CLOUD_PROMETHEUS_URL is not None


@patch("llm.mcp.loki_mcp.requests.get")
def test_query_logs_called_as_tool(mock_get):
    """Loki query_logs 作为 LangChain tool 可调用"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"result": []}}
    mock_get.return_value = mock_resp

    from llm.mcp.loki_mcp import query_logs
    result = query_logs.invoke({"server_name": "web-01", "hours": 1})
    assert isinstance(result, str)


@patch("llm.mcp.prometheus_mcp.requests.get")
def test_query_metric_called_as_tool(mock_get):
    """Prometheus query_metric 作为 LangChain tool 可调用"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "success",
        "data": {"resultType": "vector", "result": []}
    }
    mock_get.return_value = mock_resp

    from llm.mcp.prometheus_mcp import query_metric
    result = query_metric.invoke({"metric_name": "test_metric"})
    assert "metric" in result
