from store.db import get_session
from store.models import Server, Metric
from langchain_core.tools import tool
from datetime import datetime, timedelta, timezone
import requests
import time
from llm.rag import search_knowledge_base as kb_search

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
    查询指定服务器的最新状态指标
    """
    session = get_session()
    server = session.query(Server).filter_by(name=server_name).first()
    if not server:
        session.close()
        return {"error": f"{server_name} not found"}

    metric = session.query(Metric).filter_by(server_id=server.id).order_by(Metric.created_at.desc()).first()
    # 当metric为none
    if not metric:
        session.close()
        return  {"server_name": server.name, "status": "no data yet"}
    
    result = {          # 一条数据，用字典
        "server_id": server.id,
        "server_name": server.name,
        "cpu": metric.cpu,
        "memory": metric.memory,
        "disk": metric.disk,
        "net_recv": metric.net_recv,
        "net_sent": metric.net_sent
    }
    session.close()
    return result

@tool
def get_metrics_history(server_name: str, hours: int=24):
    """查某个服务器过去的历史指标趋势"""
    result = []
    session =get_session()
    server = session.query(Server).filter_by(name=server_name).first()
    if not server:
        session.close()
        return {"error": f"{server_name} not found"}
    
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    metrics = session.query(Metric).filter(
        Metric.server_id == server.id,
        Metric.created_at >= since
    ).order_by(Metric.created_at.asc()).all()   # all()是多条数据不止一条用列表，filter():可用于比较

    # 当metric为none
    if not metrics:
        session.close()
        return {"server_name": server.name, "status": "no data yet"}
    
    for r in metrics:
        result.append({
            "server_id": server.id,
            "server_name": server.name,
            "cpu": r.cpu,
            "memory": r.memory,
            "disk": r.disk,
            "net_recv": r.net_recv,
            "net_sent": r.net_sent,
            "created_at": r.created_at.isoformat()
        })

    session.close()
    return result

@tool
def get_logs(server_name: str, hours: int=1, level: str=''):
    """从loki获取日志信息"""
    logs=[]
    session = get_session()
    server = session.query(Server).filter_by(name=server_name).first()
    if not server:
        session.close()
        return {"error": f"{server_name} not found"}
    
    LOKI_URL = "http://localhost:3100/loki/api/v1/query_range"

    query = f'{{server="{server_name}"}}'
    if level:
        query += f' |= "{level}"'

    params = {
        "query": query,
        
        "start": int(time.time() - hours * 3600) * 1_000_000_000,
        "end": int(time.time()) * 1_000_000_000,
        "limit": 100
    }
    try:
        resp = requests.get(LOKI_URL, params=params)
        resp.raise_for_status()     # 检查HTTP状态码,有错误码就直接报异常
        data = resp.json()
    except Exception as e:
        return {"error": f"Loki 查询失败: {str(e)}"}
    for stream_result in data["data"]["result"]:
        for ts, log_line in stream_result["values"]:  # values = 时间戳+日志
            logs.append(log_line)

    session.close()
    return '\n'.join(logs)
        
@tool
def search_knowledge_base(query: str, limit: int=5):
    """语义搜索知识库"""
    return kb_search(query, limit)