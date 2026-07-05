"""Loki MCP — 通过 HTTP API 查询日志

依赖环境变量 `CLOUD_LOKI_URL`（默认 http://localhost:3100）

Functions (均暴露为 langchain tool):
  - query_logs       按服务名查询日志
  - analyze_errors   分析错误日志，统计错误码
  - count_by_level   按日志级别统计数量
"""

import re
import time
from collections import Counter

import requests
from langchain_core.tools import tool

from llm.mcp import CLOUD_LOKI_URL

LOKI_API = f"{CLOUD_LOKI_URL}/loki/api/v1"


def _range_params(hours: int) -> dict:
    """生成 Loki query_range 公共时间参数（纳秒时间戳）"""
    now = time.time()
    return {
        "start": int((now - hours * 3600)) * 1_000_000_000,
        "end": int(now) * 1_000_000_000,
    }


def _query_loki(query: str, hours: int, limit: int = 100) -> list[str]:
    """通用 Loki LogQL 查询，返回日志行列表"""
    params = {"query": query, "limit": limit, **_range_params(hours)}
    try:
        resp = requests.get(f"{LOKI_API}/query_range", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Loki 查询失败: {e}") from e

    lines: list[str] = []
    for stream in data.get("data", {}).get("result", []):
        for _ts, log_line in stream.get("values", []):
            lines.append(log_line)
    return lines


def _parse_error_codes(lines: list[str]) -> dict:
    """从日志行中提取 HTTP 状态码、异常类等错误码并统计"""
    codes: Counter[str] = Counter()
    for line in lines:
        # HTTP 状态码
        for m in re.finditer(r"\b(\d{3})\b", line):
            code = m.group(1)
            if 400 <= int(code) < 600:
                codes[code] += 1
        # Python 异常类
        for m in re.finditer(r"(\w+(?:Error|Exception|Warning|Fault))", line):
            codes[m.group(1)] += 1
    return dict(codes.most_common(20))


@tool
def query_logs(server_name: str, hours: int = 1, level: str = "") -> str:
    """查询指定服务器在给定时间范围内的日志

    Args:
        server_name: 服务器名称（对应 Loki label `server`）
        hours:       回溯小时数，默认 1
        level:       按日志级别过滤（debug / info / warn / error），空字符串不过滤
    """
    query = f'{{server="{server_name}"}}'
    if level:
        query += f' |= "{level}"'

    lines = _query_loki(query, hours)
    if not lines:
        return f"服务器 {server_name} 过去 {hours} 小时内无日志"
    return "\n".join(lines)


@tool
def analyze_errors(server_name: str, hours: int = 1) -> dict:
    """分析指定服务器过去 N 小时的错误日志，返回错误码统计

    Args:
        server_name: 服务器名称
        hours:       回溯小时数，默认 1

    Returns:
        {server_name, hours, total_errors, error_codes: {code: count, ...}}
    """
    lines = _query_loki(f'{{server="{server_name}"}} |= "error"', hours, limit=500)
    codes = _parse_error_codes(lines)

    return {
        "server_name": server_name,
        "hours": hours,
        "total_errors": len(lines),
        "error_codes": codes,
    }


@tool
def count_by_level(server_name: str, hours: int = 1) -> dict:
    """按日志级别统计指定服务器过去 N 小时的日志数量

    Args:
        server_name: 服务器名称
        hours:       回溯小时数，默认 1

    Returns:
        {server_name, hours, total, levels: {level: count}}
    """
    levels = {}
    for level in ("debug", "info", "warn", "error"):
        lines = _query_loki(f'{{server="{server_name}"}} |= "{level}"', hours, limit=5000)
        levels[level] = len(lines)

    total = sum(levels.values())
    return {
        "server_name": server_name,
        "hours": hours,
        "total": total,
        "levels": levels,
    }


# langchain 可注册工具列表
tools = [query_logs, analyze_errors, count_by_level]
