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
    查询指定服务器的最新状态指标（从 Prometheus 获取百分比值）
    """
    session = get_session()
    server = session.query(Server).filter_by(name=server_name).first()
    session.close()

    if not server:
        return {"error": f"{server_name} not found"}

    ip = server.ip
    result = {"server_name": server.name, "server_ip": ip}

    # PromQL 查询百分比
    queries = {
        "cpu": f'100 - (avg by(instance)(rate(node_cpu_seconds_total{{mode="idle"}}[1m])) * 100)',
        "memory": f'(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100',
        "disk": f'(1 - node_filesystem_free_bytes / node_filesystem_size_bytes) * 100',
    }
    for key, promql in queries.items():
        try:
            val = query_metric.invoke({"promql": promql, "server_ip": ip})
            results = val.get("results", [])
            result[key] = float(results[0]["value"]) if results else None
        except Exception as e:
            result[key] = {"error": str(e)}

    return result


@tool
def search_knowledge_base(query: str, top_k: int = 3):
    """混合搜索知识库"""
    return kb_search(query, top_k)
