"""传统工具函数测试"""
from unittest.mock import patch, MagicMock


@patch("llm.tools.get_session")
def test_get_server_list(mock_session):
    """get_server_list 返回格式化的服务器列表"""
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess

    from store.models import Server
    mock_server = MagicMock(spec=Server)
    mock_server.name = "web-01"
    mock_server.ip = "10.0.0.1"
    mock_server.status = "online"
    mock_server.os = "Ubuntu 22.04"
    mock_sess.query.return_value.all.return_value = [mock_server]

    from llm.tools import get_server_list
    result = get_server_list.invoke({})

    assert len(result) == 1
    assert result[0]["name"] == "web-01"
    assert result[0]["status"] == "online"


@patch("llm.tools.get_session")
def test_get_server_list_empty(mock_session):
    """get_server_list 无服务器时返回空列表"""
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess
    mock_sess.query.return_value.all.return_value = []

    from llm.tools import get_server_list
    result = get_server_list.invoke({})

    assert result == []


@patch("llm.tools.query_metric")
@patch("llm.tools.get_session")
def test_get_server_status(mock_session, mock_qm):
    """get_server_status 返回服务器实时指标"""
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess

    from store.models import Server
    mock_server = MagicMock(spec=Server)
    mock_server.name = "web-01"
    mock_server.ip = "10.0.0.1"
    mock_sess.query.return_value.filter_by.return_value.first.return_value = mock_server

    mock_qm.invoke.return_value = {"results": [{"value": "85.3", "instance": "10.0.0.1:9100"}]}

    from llm.tools import get_server_status
    result = get_server_status.invoke({"server_name": "web-01"})

    assert result["server_name"] == "web-01"


@patch("llm.tools.get_session")
def test_get_server_status_not_found(mock_session):
    """get_server_status 找不到服务器时返回错误"""
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess
    mock_sess.query.return_value.filter_by.return_value.first.return_value = None

    from llm.tools import get_server_status
    result = get_server_status.invoke({"server_name": "nonexistent"})

    assert "error" in result


@patch("llm.tools.kb_search")
def test_search_knowledge_base(mock_search):
    """search_knowledge_base 返回知识库搜索结果"""
    from langchain_core.documents import Document
    mock_search.return_value = [
        Document(page_content="nginx 配置指南", metadata={"source": "ops-guide"})
    ]

    from llm.tools import search_knowledge_base
    result = search_knowledge_base.invoke({"query": "nginx 配置", "top_k": 3})

    assert len(result) > 0
