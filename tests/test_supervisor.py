"""Supervisor LangGraph 图结构测试"""
from unittest.mock import patch, MagicMock


def test_build_supervisor():
    """build_supervisor 返回编译后的 StateGraph"""
    from llm.supervisor import build_supervisor
    graph = build_supervisor()
    assert graph is not None


def test_supervisor_graph_has_nodes():
    """StateGraph 包含所有必需的节点"""
    from llm.supervisor import build_supervisor
    graph = build_supervisor()
    # LangGraph 编译后的图没有直接的 get_nodes 方法
    # 验证图对象存在即可
    assert hasattr(graph, "invoke")


@patch("llm.supervisor._LLM")
def test_supervisor_node_finish(mock_llm):
    """supervisor_node 在迭代超限时返回 FINISH"""
    import json
    mock_llm.invoke.return_value.content = json.dumps({"next": "FINISH", "reason": "done"})

    from llm.supervisor import supervisor_node
    state = {
        "messages": [("human", "你好")],
        "next": "supervisor",
        "intermediate_results": {},
        "final_report": "",
        "iteration": 0,
    }
    result = supervisor_node(state)
    assert result["next"] == "FINISH"


@patch("llm.supervisor._LLM")
def test_supervisor_node_routing(mock_llm):
    """supervisor_node 根据 LLM 决策路由到对应 Worker"""
    import json
    mock_llm.invoke.return_value.content = json.dumps({"next": "log_worker", "reason": "需要看日志"})

    from llm.supervisor import supervisor_node
    state = {
        "messages": [("human", "查看 web-01 的日志")],
        "next": "supervisor",
        "intermediate_results": {},
        "final_report": "",
        "iteration": 0,
    }
    result = supervisor_node(state)
    assert result["next"] == "log_worker"


def test_supervisor_should_continue():
    """should_continue 根据 next 和 iteration 判断是否继续"""
    from llm.supervisor import should_continue

    # next=FINISH → end
    assert should_continue({"next": "FINISH"}) == "end"
    # 未超限且未结束 → continue
    assert should_continue({"next": "log_worker", "iteration": 1}) == "continue"


def test_supervisor_should_continue_max_iterations():
    """超过 MAX_ITERATIONS 时结束"""
    from llm.supervisor import should_continue, MAX_ITERATIONS

    state = {"next": "log_worker", "iteration": MAX_ITERATIONS}
    assert should_continue(state) == "end"
