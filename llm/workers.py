"""Worker 工具函数 — 供 Supervisor StateGraph 调用

每个 Worker 是纯工具函数，不调 LLM，只负责查数据并返回结果。
"""

from llm.mcp.loki_mcp import query_logs, analyze_errors, count_by_level
from llm.mcp.prometheus_mcp import query_metric, range_query, check_alerts
from llm.retriever import hybrid_search as kb_search


def log_worker(server_name: str, hours: int = 1) -> dict:
    """日志分析 Worker — 查 Loki 并汇总关键信息

    Returns:
        {server_name, hours, log_snippet, error_stats, level_distribution}
    """
    snippet = query_logs.invoke({"server_name": server_name, "hours": hours})
    err_stats = analyze_errors.invoke({"server_name": server_name, "hours": hours})
    levels = count_by_level.invoke({"server_name": server_name, "hours": hours})

    return {
        "server_name": server_name,
        "hours": hours,
        "log_snippet": snippet[:2000] if isinstance(snippet, str) else str(snippet),
        "error_stats": err_stats,
        "level_distribution": levels,
    }


def infra_worker(server_name: str, server_ip: str = "") -> dict:
    """基础设施 Worker — 查 Prometheus 指标 + 告警

    Returns:
        {server_name, cpu_percent, memory_percent, disk_percent, alerts}
    """
    result = {
        "server_name": server_name,
        "server_ip": server_ip or "all",
        "data_available": False,
    }

    # 用 PromQL 查百分比值
    promql_queries = {
        "cpu_percent": f'100 - (avg by(instance)(rate(node_cpu_seconds_total{{mode="idle"}}[1m])) * 100)',
        "memory_percent": f'(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100',
        "disk_percent": f'(1 - node_filesystem_free_bytes / node_filesystem_size_bytes) * 100',
    }

    for key, promql in promql_queries.items():
        try:
            val = query_metric.invoke({"promql": promql, "server_ip": server_ip})
            results = val.get("results", [])
            if results:
                result[key] = round(float(results[0].get("value", 0)), 1)
                result["data_available"] = True
            else:
                result[key] = None
        except Exception as e:
            result[key] = {"error": str(e)}

    # 查告警
    try:
        result["alerts"] = check_alerts.invoke({})
    except Exception as e:
        result["alerts"] = {"error": str(e)}

    return result


def knowledge_worker(query: str, top_k: int = 3) -> dict:
    """知识库 Worker — 检索 ChromaDB / BM25

    Returns:
        {query, results: [{content, score, source}]}
    """
    try:
        docs = kb_search(query, top_k)
    except Exception as e:
        return {"query": query, "error": str(e)}

    results = []
    for doc in docs:
        results.append({
            "content": doc.page_content[:500] if hasattr(doc, "page_content") else str(doc)[:500],
            "score": getattr(doc, "metadata", {}).get("score", 0),
            "source": getattr(doc, "metadata", {}).get("source", ""),
        })

    return {"query": query, "results": results}
