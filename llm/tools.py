from store.db import get_session
from store.models import Server
from langchain_core.tools import tool
from llm.retriever import hybrid_search as kb_search
from llm.mcp.prometheus_mcp import query_metric


@tool
def get_server_list():
    """
    返回服务器列表
    """
    result = []
    session = get_session()
    servers = session.query(Server).all()
    for s in servers:
        result.append({
            "name": s.name,
            "ip": s.ip,
            "status": s.status,
            "os": s.os
        })

    session.close()

    return result


@tool
def get_server_status(server_name: str):
    """
    查询指定服务器的最新状态指标（从 Prometheus 获取）
    """
    session = get_session()
    server = session.query(Server).filter_by(name=server_name).first()
    session.close()

    if not server:
        return {"error": f"{server_name} not found"}

    # 从 Prometheus 查实时指标
    cpu = query_metric.invoke({"metric_name": "node_cpu_seconds_total", "server_ip": server.ip})
    memory = query_metric.invoke({"metric_name": "node_memory_MemAvailable_bytes", "server_ip": server.ip})

    return {
        "server_name": server.name,
        "server_ip": server.ip,
        "cpu": cpu.get("results", []),
        "memory": memory.get("results", []),
    }


@tool
def search_knowledge_base(query: str, top_k: int = 3):
    """混合搜索知识库"""
    return kb_search(query, top_k)
