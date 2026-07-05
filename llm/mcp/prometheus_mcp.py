"""Prometheus MCP — 通过 HTTP API 查询指标

依赖环境变量 `CLOUD_PROMETHEUS_URL`（默认 http://localhost:9090）

Functions (均暴露为 langchain tool):
  - query_metric    即时查询单个指标
  - range_query     范围查询指标趋势
  - check_alerts    获取当前告警列表
"""

from datetime import datetime, timezone, timedelta

import requests
from langchain_core.tools import tool

from llm.mcp import CLOUD_PROMETHEUS_URL

PROM_API = f"{CLOUD_PROMETHEUS_URL}/api/v1"


def _instance_filter(server_ip: str) -> str:
    """生成 instance 标签过滤"""
    if not server_ip:
        return ""
    # instance 在 Prometheus 中通常以 ip:port 形式存储
    return f'{{instance=~"{server_ip}(:\\d+)?"}}'


@tool
def query_metric(metric_name: str, server_ip: str = "") -> dict:
    """即时查询 Prometheus 指标当前值

    Args:
        metric_name: 指标名称，如 `node_cpu_seconds_total`
        server_ip:   服务器 IP（可选），传空则查所有实例

    Returns:
        {metric, server_ip, timestamp, results: [{instance, value, ...}]}
    """
    query = metric_name + _instance_filter(server_ip)
    try:
        resp = requests.get(
            f"{PROM_API}/query",
            params={"query": query},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Prometheus 查询失败: {e}") from e

    if data.get("status") != "success":
        return {"error": f"Prometheus 返回异常: {data.get('error', 'unknown')}"}

    results = []
    for result in data.get("data", {}).get("result", []):
        metric = result.get("metric", {})
        value = result.get("value", [None, None])
        results.append({
            "instance": metric.get("instance", ""),
            "job": metric.get("job", ""),
            "value": value[1],
        })

    return {
        "metric": metric_name,
        "server_ip": server_ip or "all",
        "timestamp": data.get("data", {}).get("resultType", ""),
        "results": results,
    }


@tool
def range_query(metric_name: str, server_ip: str = "", duration: str = "1h") -> dict:
    """范围查询 Prometheus 指标趋势

    Args:
        metric_name: 指标名称
        server_ip:   服务器 IP（可选）
        duration:    时间范围，如 1h / 30m / 6h / 1d / 7d

    Returns:
        {metric, server_ip, duration, step, results: [{instance, values: [[ts, val], ...]}]}
    """
    now = datetime.now(timezone.utc)
    unit = duration[-1]
    value = int(duration[:-1])
    if unit == "m":
        delta = timedelta(minutes=value)
    elif unit == "h":
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)
    else:
        delta = timedelta(hours=1)

    start = now - delta
    # 自动选择 step：1h → 30s, 6h → 5m, 1d → 15m, 7d → 1h
    total_seconds = delta.total_seconds()
    if total_seconds <= 3600:
        step = "30s"
    elif total_seconds <= 21600:
        step = "5m"
    elif total_seconds <= 86400:
        step = "15m"
    else:
        step = "1h"

    query = metric_name + _instance_filter(server_ip)
    try:
        resp = requests.get(
            f"{PROM_API}/query_range",
            params={
                "query": query,
                "start": start.isoformat(),
                "end": now.isoformat(),
                "step": step,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Prometheus 范围查询失败: {e}") from e

    if data.get("status") != "success":
        return {"error": f"Prometheus 返回异常: {data.get('error', 'unknown')}"}

    results = []
    for result in data.get("data", {}).get("result", []):
        metric = result.get("metric", {})
        values = [
            {"timestamp": ts, "value": val}
            for ts, val in result.get("values", [])
        ]
        results.append({
            "instance": metric.get("instance", ""),
            "job": metric.get("job", ""),
            "values": values,
        })

    return {
        "metric": metric_name,
        "server_ip": server_ip or "all",
        "duration": duration,
        "step": step,
        "results": results,
    }


@tool
def check_alerts() -> list[dict]:
    """获取 Prometheus 当前所有告警"""
    try:
        resp = requests.get(f"{PROM_API}/alerts", timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Prometheus 告警查询失败: {e}") from e

    if data.get("status") != "success":
        return [{"error": f"Prometheus 返回异常: {data.get('error', 'unknown')}"}]

    alerts = []
    for alert in data.get("data", {}).get("alerts", []):
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alerts.append({
            "name": labels.get("alertname", ""),
            "state": alert.get("state", ""),
            "severity": labels.get("severity", ""),
            "instance": labels.get("instance", ""),
            "summary": annotations.get("summary", ""),
            "description": annotations.get("description", ""),
            "active_at": alert.get("activeAt", ""),
        })

    return alerts


# langchain 可注册工具列表
tools = [query_metric, range_query, check_alerts]
