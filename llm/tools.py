from store.db import get_session
from store.models import Server, Metric
from langchain_core.tools import tool
from llm.retriever import hybrid_search as kb_search


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
    查询指定服务器的最新状态指标（从 PostgreSQL 获取百分比值）
    """
    session = get_session()
    server = session.query(Server).filter_by(name=server_name).first()
    if not server:
        session.close()
        return {"error": f"{server_name} not found"}

    # 从 Metric 表取最新一条（已有百分比值）
    metric = session.query(Metric).filter_by(
        server_id=server.id
    ).order_by(Metric.id.desc()).first()
    session.close()

    return {
        "server_name": server.name,
        "server_ip": server.ip,
        "cpu": metric.cpu if metric else None,
        "memory": metric.memory if metric else None,
        "disk": metric.disk if metric else None,
    }


@tool
def search_knowledge_base(query: str, top_k: int = 3):
    """混合搜索知识库"""
    return kb_search(query, top_k)
