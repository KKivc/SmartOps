"""Tests for Loki MCP module."""

from unittest.mock import patch, MagicMock


def test_loki_mcp_import():
    from llm.mcp.loki_mcp import LokiMCPServer
    assert LokiMCPServer is not None


def test_loki_mcp_init():
    from llm.mcp.loki_mcp import LokiMCPServer
    server = LokiMCPServer(url="http://localhost:3100")
    assert server.url == "http://localhost:3100"


def test_tools_list():
    from llm.mcp.loki_mcp import LokiMCPServer
    server = LokiMCPServer(url="http://localhost:3100")
    tools = server.get_tools()
    assert len(tools) == 3
    assert tools[0]["name"] == "query_logs"


@patch("llm.mcp.loki_mcp.requests.get")
def test_analyze_errors(mock_get):
    """测试 analyze_errors 正确解析 Loki 返回数据。"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "result": [
                {
                    "stream": {"server": "web-01"},
                    "values": [
                        ["1710000000000000000", "ERROR: 500 Internal Server Error"],
                        ["1710000001000000000", "INFO: Request completed"],
                        ["1710000002000000000", "ERROR: 502 Bad Gateway upstream timed out"],
                    ],
                }
            ]
        }
    }
    mock_get.return_value = mock_resp

    from llm.mcp.loki_mcp import LokiMCPServer
    server = LokiMCPServer(url="http://loki:3100")
    result = server.analyze_errors("web-01", hours=1)

    assert result["total_errors"] == 2
    assert result["error_codes"]["500"] == 1
    assert result["error_codes"]["502"] == 1
    assert len(result["error_samples"]) == 2
