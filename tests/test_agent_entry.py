"""Agent 入口模块测试 — chat() 内部使用 supervisor.invoke()"""
from unittest.mock import patch, MagicMock


@patch("llm.agent._supervisor")
@patch("llm.agent.get_session")
def test_chat_returns_string(mock_session, mock_sv):
    """chat() 返回字符串"""
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess
    mock_sess.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    mock_sv.invoke.return_value = {"final_report": "服务器 web-01 运行正常，CPU 45%，内存 62%"}

    from llm.agent import chat
    result = chat(conversation_id=1, user_input="web-01 状态如何？")

    assert isinstance(result, str)
    assert len(result) > 0
    mock_sv.invoke.assert_called_once()


@patch("llm.agent._supervisor")
@patch("llm.agent.get_session")
def test_chat_saves_messages(mock_session, mock_sv):
    """chat() 正确保存用户消息和助手的回答"""
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess
    mock_sess.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    mock_sv.invoke.return_value = {"final_report": "回复内容"}

    from llm.agent import chat
    chat(conversation_id=1, user_input="你好")

    assert mock_sess.add.call_count == 2


@patch("llm.agent._supervisor")
@patch("llm.agent.get_session")
def test_chat_catches_exception(mock_session, mock_sv):
    """chat() 异常时返回友好提示"""
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess
    mock_sess.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    mock_sv.invoke.side_effect = Exception("LLM API 超时")

    from llm.agent import chat
    result = chat(conversation_id=1, user_input="你好")

    assert "系统错误" in result or "异常" in result
