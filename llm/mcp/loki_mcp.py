"""
Loki MCP 封装 — 日志查询与异常分析。

通过 HTTP API 查询云服务器上的 Grafana Loki，
提供日志检索、错误分析和级别统计功能。
"""

import re
import time
import requests
from datetime import datetime, timezone
from typing import Optional


class LokiMCPServer:
    """Loki 日志服务 MCP 封装，进程内运行。"""

    def __init__(self, url: str):
        self.url = url.rstrip("/")

    # ------------------------------------------------------------------
    # MCP 工具定义
    # ------------------------------------------------------------------

    def get_tools(self) -> list[dict]:
        """返回 MCP 风格的工具定义列表。"""
        return [
            {
                "name": "query_logs",
                "description": "查询 Loki 原始日志，支持按服务名、时间范围和级别过滤",
                "parameters": {
                    "server_name": {"type": "string", "description": "服务器名称"},
                    "hours": {"type": "integer", "description": "查询范围（小时）", "default": 1},
                    "level": {"type": "string", "description": "日志级别过滤", "default": ""},
                    "keywords": {"type": "array", "description": "关键词过滤", "default": []},
                },
            },
            {
                "name": "analyze_errors",
                "description": "分析错误日志：统计错误码分布、提取关键报错样本、时间分布",
                "parameters": {
                    "server_name": {"type": "string", "description": "服务器名称"},
                    "hours": {"type": "integer", "description": "分析范围（小时）", "default": 1},
                },
            },
            {
                "name": "count_by_level",
                "description": "按日志级别统计数量（error / warn / info）",
                "parameters": {
                    "server_name": {"type": "string", "description": "服务器名称"},
                    "hours": {"type": "integer", "description": "统计范围（小时）", "default": 1},
                },
            },
        ]

    # ------------------------------------------------------------------
    # 工具实现
    # ------------------------------------------------------------------

    def query_logs(
        self,
        server_name: str,
        hours: int = 1,
        level: str = "",
        keywords: Optional[list[str]] = None,
    ) -> list[dict]:
        """查询 Loki 原始日志。"""
        query = f'{{server="{server_name}"}}'
        if level:
            query += f' |= "{level}"'

        params = {
            "query": query,
            "start": int((time.time() - hours * 3600)) * 1_000_000_000,
            "end": int(time.time()) * 1_000_000_000,
            "limit": 200,
        }

        try:
            resp = requests.get(f"{self.url}/loki/api/v1/query_range", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            return [{"error": f"Loki 查询失败: {e}"}]

        logs = []
        for stream in data.get("data", {}).get("result", []):
            for ts, line in stream.get("values", []):
                logs.append({
                    "timestamp": datetime.fromtimestamp(int(ts) / 1e9, tz=timezone.utc).isoformat(),
                    "content": line,
                    "labels": stream.get("stream", {}),
                })

        # 关键词过滤
        if keywords:
            filtered = []
            for log in logs:
                if any(kw.lower() in log["content"].lower() for kw in keywords):
                    filtered.append(log)
            return filtered

        return logs

    def analyze_errors(self, server_name: str, hours: int = 1) -> dict:
        """分析错误日志：统计、采样、时间分布。"""
        logs = self.query_logs(server_name, hours=hours)
        if not logs or "error" in logs[0]:
            return {"error": "无日志数据", "server": server_name}

        # 筛选 error 级别
        errors = [
            log for log in logs
            if "error" in log["content"].lower() or "fatal" in log["content"].lower()
        ]

        # 提取错误码（如 500, 502, 503, 504）
        error_codes = {}
        for log in errors:
            codes = re.findall(r"\b(50[0-9]|40[0-9]|30[0-2])\b", log["content"])
            for code in codes:
                error_codes[code] = error_codes.get(code, 0) + 1

        # 提取关键样本（最多 5 条）
        samples = [e["content"] for e in errors[:5]]

        # 时间分布（按分钟聚合）
        time_dist = {}
        for e in errors:
            minute = e["timestamp"][:16]
            time_dist[minute] = time_dist.get(minute, 0) + 1

        return {
            "server": server_name,
            "hours": hours,
            "total_errors": len(errors),
            "error_codes": error_codes,
            "error_samples": samples,
            "time_distribution": time_dist,
        }

    def count_by_level(self, server_name: str, hours: int = 1) -> dict:
        """按日志级别统计数量。"""
        logs = self.query_logs(server_name, hours=hours)
        if not logs or "error" in logs[0]:
            return {"error": "无日志数据", "server": server_name}

        counts = {"error": 0, "warn": 0, "info": 0, "unknown": 0}
        for log in logs:
            content = log["content"].upper()
            if "ERROR" in content or "FATAL" in content:
                counts["error"] += 1
            elif "WARN" in content or "WARNING" in content:
                counts["warn"] += 1
            elif "INFO" in content:
                counts["info"] += 1
            else:
                counts["unknown"] += 1

        return {
            "server": server_name,
            "hours": hours,
            "counts": counts,
            "total": sum(counts.values()),
        }
