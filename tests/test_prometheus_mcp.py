"""Prometheus MCP 模块测试"""
from unittest.mock import patch, MagicMock


@patch("llm.mcp.prometheus_mcp.requests.get")
def test_query_metric_single_result(mock_get):
    """query_metric 正确解析 Prometheus 即时查询结果"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"instance": "10.0.0.1:9100", "job": "node"},
                 "value": [1710000000, "85.3"]}
            ],
        },
    }
    mock_get.return_value = mock_resp

    from llm.mcp.prometheus_mcp import query_metric
    result = query_metric.invoke({"metric_name": "node_cpu_percent", "server_ip": "10.0.0.1"})

    assert result["metric"] == "node_cpu_percent"
    assert len(result["results"]) == 1
    assert result["results"][0]["value"] == "85.3"


@patch("llm.mcp.prometheus_mcp.requests.get")
def test_query_metric_no_results(mock_get):
    """query_metric 无数据时返回空 results 列表"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "success",
        "data": {"resultType": "vector", "result": []},
    }
    mock_get.return_value = mock_resp

    from llm.mcp.prometheus_mcp import query_metric
    result = query_metric.invoke({"metric_name": "nonexistent_metric"})

    assert result["results"] == []


@patch("llm.mcp.prometheus_mcp.requests.get")
def test_range_query(mock_get):
    """range_query 正确解析范围查询结果"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"instance": "10.0.0.1:9100"},
                    "values": [
                        [1710000000, "45.2"],
                        [1710000060, "46.1"],
                    ],
                }
            ],
        },
    }
    mock_get.return_value = mock_resp

    from llm.mcp.prometheus_mcp import range_query
    result = range_query.invoke({"metric_name": "node_cpu_percent", "duration": "1h"})

    assert len(result["results"]) == 1
    assert len(result["results"][0]["values"]) == 2


@patch("llm.mcp.prometheus_mcp.requests.get")
def test_check_alerts(mock_get):
    """check_alerts 正确解析告警列表"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "success",
        "data": {
            "alerts": [
                {
                    "labels": {"alertname": "HighCPU", "severity": "critical", "instance": "10.0.0.1:9100"},
                    "state": "firing",
                    "activeAt": "2026-07-05T10:00:00Z",
                    "annotations": {"summary": "CPU > 90%", "description": "CPU at 95%"},
                }
            ]
        },
    }
    mock_get.return_value = mock_resp

    from llm.mcp.prometheus_mcp import check_alerts
    result = check_alerts.invoke({})

    assert len(result) == 1
    assert result[0]["name"] == "HighCPU"
    assert result[0]["severity"] == "critical"


@patch("llm.mcp.prometheus_mcp.requests.get")
def test_query_metric_prometheus_error(mock_get):
    """Prometheus 返回异常状态时返回错误信息"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "error", "error": "bad request"}
    mock_get.return_value = mock_resp

    from llm.mcp.prometheus_mcp import query_metric
    result = query_metric.invoke({"metric_name": "test"})

    assert "error" in result


@patch("llm.mcp.prometheus_mcp.requests.get")
def test_check_alerts_no_alerts(mock_get):
    """无告警时返回空列表"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "success",
        "data": {"alerts": []},
    }
    mock_get.return_value = mock_resp

    from llm.mcp.prometheus_mcp import check_alerts
    result = check_alerts.invoke({})

    assert result == []
