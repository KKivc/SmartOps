"""Loki MCP 模块测试"""
from unittest.mock import patch, MagicMock


@patch("llm.mcp.loki_mcp.requests.get")
def test_query_logs_with_results(mock_get):
    """query_logs 正确解析 Loki 返回的多条日志"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "result": [
                {
                    "stream": {"server": "web-01"},
                    "values": [
                        ["1710000000000000000", "ERROR: 500 Internal Server Error"],
                        ["1710000001000000000", "INFO: Request completed"],
                    ],
                }
            ]
        }
    }
    mock_get.return_value = mock_resp

    from llm.mcp.loki_mcp import query_logs
    result = query_logs.invoke({"server_name": "web-01", "hours": 1})

    assert "ERROR" in result
    assert "INFO" in result


@patch("llm.mcp.loki_mcp.requests.get")
def test_query_logs_no_results(mock_get):
    """query_logs 无日志时返回提示信息"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"result": []}}
    mock_get.return_value = mock_resp

    from llm.mcp.loki_mcp import query_logs
    result = query_logs.invoke({"server_name": "web-01", "hours": 1})

    assert "无日志" in result


@patch("llm.mcp.loki_mcp.requests.get")
def test_query_logs_level_filter(mock_get):
    """query_logs 的 level 参数被传递给 Loki 查询"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {"result": []}}
    mock_get.return_value = mock_resp

    from llm.mcp.loki_mcp import query_logs
    query_logs.invoke({"server_name": "web-01", "hours": 1, "level": "error"})

    # 验证请求 URL 包含 level 过滤
    call_kwargs = mock_get.call_args[1]
    assert "query" in call_kwargs["params"]
    assert "error" in call_kwargs["params"]["query"]


@patch("llm.mcp.loki_mcp.requests.get")
def test_analyze_errors_stats(mock_get):
    """analyze_errors 正确统计错误码"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "result": [
                {
                    "stream": {"server": "web-01"},
                    "values": [
                        ["1710000000000000000", "ERROR: 500 Internal Server Error"],
                        ["1710000001000000000", "ERROR: 500 Timeout"],
                        ["1710000002000000000", "ERROR: 502 Bad Gateway"],
                    ],
                }
            ]
        }
    }
    mock_get.return_value = mock_resp

    from llm.mcp.loki_mcp import analyze_errors
    result = analyze_errors.invoke({"server_name": "web-01", "hours": 1})

    assert result["total_errors"] == 3
    assert result["error_codes"]["500"] == 2
    assert result["error_codes"]["502"] == 1


@patch("llm.mcp.loki_mcp.requests.get")
def test_count_by_level(mock_get):
    """count_by_level 按级别统计数量"""
    def side_effect(*args, **kwargs):
        mock = MagicMock()
        level = kwargs.get("params", {}).get("query", "")
        if 'error' in level:
            mock.json.return_value = {"data": {"result": [{"stream": {}, "values": [["0", "error"]]}]}}
        else:
            mock.json.return_value = {"data": {"result": []}}
        return mock

    mock_get.side_effect = side_effect

    from llm.mcp.loki_mcp import count_by_level
    result = count_by_level.invoke({"server_name": "web-01", "hours": 1})

    assert "total" in result
    assert "levels" in result


@patch("llm.mcp.loki_mcp.requests.get")
def test_query_logs_connection_error(mock_get):
    """Loki 连接失败时异常上抛"""
    import requests
    mock_get.side_effect = requests.ConnectionError("Connection refused")

    from llm.mcp.loki_mcp import query_logs
    import pytest
    with pytest.raises(RuntimeError, match="Loki 查询失败"):
        query_logs.invoke({"server_name": "web-01", "hours": 1})
