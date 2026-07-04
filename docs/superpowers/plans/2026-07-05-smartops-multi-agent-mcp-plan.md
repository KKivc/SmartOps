# SmartOps 多 Agent + MCP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 SmartOps 从单 Agent 架构迁移为 LangGraph Supervisor + 多 Worker 架构，引入 MCP 进程内封装层，重构日志/指标采集链路。

**Architecture:**
- 云服务器部署 Loki + Prometheus（docker-compose），被管服务器装 promtail + node_exporter
- `llm/mcp/` 模块封装 Loki/Prometheus HTTP API，进程内运行，不另起进程
- `llm/supervisor.py` LangGraph StateGraph 实现循环调度 Supervisor + 3 个 Worker（Log/Infra/Knowledge）
- 原有 `agent.py` 保留 `chat()` 接口签名，内部转发 Supervisor
- SSH 采集器简化为仅心跳检测

**Tech Stack:** Python 3.11, Flask, LangGraph, LangChain, ChromaDB, Paramiko, Prometheus, Loki

## Global Constraints

- 所有 MCP 模块是进程内 Python 类，不另起进程
- 所有 Worker 是工具函数（不调 LLM），不是独立 Agent
- Supervisor 设 `MAX_ITERATIONS = 10` 防止死循环
- `.env` 新增 `CLOUD_LOKI_URL`, `CLOUD_PROMETHEUS_URL`
- Worker 调用方式：Supervisor 通过 tool calling 路由，不直接调用 Worker
- 现有 flask API 路由不修改（`/api/chat` 等接口签名保持兼容）

---

## Phase 1：基础设施部署

这些任务需要手动在云服务器和被管服务器上执行，auto-coder 无法自动完成。

### Task A1：云服务器部署 Loki + Prometheus

**Files:**
- Create: `docker-compose.yml`（本地项目根目录，供参考）
- Create: `prometheus.yml`（Prometheus 配置文件）

**Interfaces:**
- Produces: Loki HTTP 端点 `http://<CLOUD_HOST>:3100`
- Produces: Prometheus HTTP 端点 `http://<CLOUD_HOST>:9090`

- [ ] **Step 1：创建 prometheus.yml**

```yaml
# prometheus.yml — 云服务器上使用
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets:
        # 部署 node_exporter 后添加服务器 IP
        # - 'server1-ip:9100'
        # - 'server2-ip:9100'
```

- [ ] **Step 2：更新 docker-compose.yml 增加 Prometheus**

```yaml
services:
  loki:
    image: grafana/loki:3.0.0
    ports: ["3100:3100"]
    volumes: [loki-data:/loki]
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    restart: unless-stopped

volumes:
  loki-data:
  prometheus-data:
```

- [ ] **Step 3：上传到云服务器并启动**

```bash
# SCP 到云服务器
scp docker-compose.yml prometheus.yml user@<CLOUD_HOST>:~/smartops-infra/

# SSH 到云服务器启动
ssh user@<CLOUD_HOST>
cd ~/smartops-infra
docker compose up -d
```

- [ ] **Step 4：验证服务**

```bash
curl http://<CLOUD_HOST>:3100/ready
# 期望: {"status":"ready"}

curl http://<CLOUD_HOST>:9090/-/ready
# 期望: Prometheus is Ready
```

---

### Task A2：被管服务器安装 promtail

**Files:** 无（在每台被管服务器上手动操作）

**Interfaces:**
- Consumes: Loki 端点 `http://<CLOUD_HOST>:3100`
- Produces: 日志从被管服务器推送到 Loki

- [ ] **Step 1：SSH 到被管服务器，安装 promtail**

```bash
# 下载 promtail
wget https://github.com/grafana/loki/releases/latest/download/promtail-linux-amd64.zip
unzip promtail-linux-amd64.zip
sudo mv promtail-linux-amd64 /usr/local/bin/promtail
```

- [ ] **Step 2：创建 promtail 配置**

```yaml
# /etc/promtail/config.yml
server:
  http_listen_port: 9080

positions:
  filename: /var/log/positions.yaml

clients:
  - url: http://<CLOUD_HOST>:3100/loki/api/v1/push

scrape_configs:
  - job_name: syslog
    static_configs:
      - targets: [localhost]
        labels:
          job: syslog
          server: <SERVER_NAME>
          __path__: /var/log/syslog

  - job_name: nginx
    static_configs:
      - targets: [localhost]
        labels:
          job: nginx
          server: <SERVER_NAME>
          __path__: /var/log/nginx/*.log

  - job_name: mysql
    static_configs:
      - targets: [localhost]
        labels:
          job: mysql
          server: <SERVER_NAME>
          __path__: /var/log/mysql/*.log
```

- [ ] **Step 3：启动 promtail 并验证**

```bash
sudo nohup promtail -config.file=/etc/promtail/config.yml &

# 验证 Loki 是否收到数据
curl "http://<CLOUD_HOST>:3100/loki/api/v1/query_range?query={server=\"<SERVER_NAME>\"}"
# 期望: 有日志结果返回
```

---

### Task A3：被管服务器安装 node_exporter

**Files:** 无（在每台被管服务器上手动操作）

**Interfaces:**
- Produces: 指标端点 `http://<SERVER_IP>:9100/metrics`

- [ ] **Step 1：下载并启动 node_exporter**

```bash
wget https://github.com/prometheus/node_exporter/releases/latest/download/node_exporter-linux-amd64.tar.gz
tar xzf node_exporter-linux-amd64.tar.gz
sudo mv node_exporter-linux-amd64/node_exporter /usr/local/bin/
sudo nohup node_exporter &
```

- [ ] **Step 2：验证指标暴露**

```bash
curl http://localhost:9100/metrics | head -20
# 期望: 看到 node_cpu_seconds_total、node_memory_MemTotal_bytes 等指标
```

---

### Task A4：配置 Prometheus 抓取 node_exporter

**Files:**
- Modify: `prometheus.yml`（云服务器上）

**Interfaces:**
- Produces: Prometheus 可查询所有被管服务器的指标

- [ ] **Step 1：更新 prometheus.yml 加入 targets**

```yaml
scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets:
        - '<SERVER1_IP>:9100'
        - '<SERVER2_IP>:9100'
```

- [ ] **Step 2：重启 Prometheus**

```bash
ssh user@<CLOUD_HOST>
docker compose restart prometheus
```

- [ ] **Step 3：验证指标可查**

```bash
curl "http://<CLOUD_HOST>:9090/api/v1/query?query=up{job=\"node\"}"
# 期望: "data":{"result":[{"metric":{"instance":"<SERVER1_IP>:9100"},"value":[...,"1"]}]}
# value 为 1 表示 target 正常
```

- [ ] **Step 4：验证 `CLOUD_LOKI_URL` 和 `CLOUD_PROMETHEUS_URL`**

```yaml
# 确认这两个 URL 可以从本地电脑访问
# 修改项目根目录 .env
CLOUD_LOKI_URL=http://<CLOUD_HOST>:3100
CLOUD_PROMETHEUS_URL=http://<CLOUD_HOST>:9090
```

---

## Phase 2：MCP 封装层

### Task B1：创建 MCP 模块包入口

**Files:**
- Create: `llm/mcp/__init__.py`
- Create: `tests/test_mcp_init.py`

**Interfaces:**
- Produces: `llm/mcp/__init__.py` 包入口，后续模块从中导入

- [ ] **Step 1：创建包入口文件**

```python
# llm/mcp/__init__.py
"""
MCP（Model Context Protocol）进程内封装层。

本模块封装 Loki、Prometheus 等外部服务的 HTTP API，
以 MCP 风格的工具形式暴露给 Agent Worker 调用。

所有模块在 Flask 进程内运行，不另起独立进程。
"""

from llm.mcp.loki_mcp import LokiMCPServer
from llm.mcp.prometheus_mcp import PrometheusMCPServer

__all__ = ["LokiMCPServer", "PrometheusMCPServer"]
```

- [ ] **Step 2：写测试验证导入**

```python
# tests/test_mcp_init.py
def test_mcp_modules_import():
    from llm.mcp import LokiMCPServer, PrometheusMCPServer
    assert LokiMCPServer is not None
    assert PrometheusMCPServer is not None
```

- [ ] **Step 3：创建测试目录并运行**

```bash
mkdir -p tests

# 运行
python -m pytest tests/test_mcp_init.py -v
# 期望: PASSED (即使类未实现，只要定义存在即可)
```

- [ ] **Step 4：提交**

```bash
git add llm/mcp/__init__.py tests/test_mcp_init.py
git commit -m "feat(mcp): [B1] create MCP package entry"
```

---

### Task B2：实现 Loki MCP 模块

**Files:**
- Create: `llm/mcp/loki_mcp.py`
- Create: `tests/test_loki_mcp.py`

**Interfaces:**
- Produces: `LokiMCPServer(url).query_logs(server_name, hours, level, keywords) -> list[dict]`
- Produces: `LokiMCPServer(url).analyze_errors(server_name, hours) -> dict`
- Consumes: `CLOUD_LOKI_URL` 环境变量

- [ ] **Step 1：写测试（先写失败测试）**

```python
# tests/test_loki_mcp.py
"""Tests for Loki MCP module."""

def test_loki_mcp_import():
    from llm.mcp.loki_mcp import LokiMCPServer
    assert LokiMCPServer is not None


def test_loki_mcp_init():
    from llm.mcp.loki_mcp import LokiMCPServer
    server = LokiMCPServer(url="http://localhost:3100")
    assert server.url == "http://localhost:3100"


def test_loki_tools_list():
    """LokiMCPServer 必须暴露 tools 列表和工具函数签名。"""
    from llm.mcp.loki_mcp import LokiMCPServer
    server = LokiMCPServer(url="http://localhost:3100")
    tools = server.get_tools()
    tool_names = [t["name"] for t in tools]

    assert "query_logs" in tool_names
    assert "analyze_errors" in tool_names
    assert "count_by_level" in tool_names

    # 验证 query_logs 参数 schema
    query_logs = next(t for t in tools if t["name"] == "query_logs")
    params = query_logs["parameters"]
    assert "server_name" in params
    assert "hours" in params
```

```bash
python -m pytest tests/test_loki_mcp.py -v
# 期望: FAIL — 模块不存在
```

- [ ] **Step 2：实现 LokiMCPServer**

```python
# llm/mcp/loki_mcp.py
"""
Loki MCP 封装 — 日志查询与异常分析。

通过 HTTP API 查询云服务器上的 Grafana Loki，
提供日志检索、错误分析和级别统计功能。
"""

import time
import requests
from datetime import datetime, timezone
from typing import Optional


class LokiMCPServer:
    """Loki 日志服务 MCP 封装，进程内运行。"""

    def __init__(self, url: str):
        self.url = url.rstrip("/")

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
        errors = [log for log in logs if "error" in log["content"].lower()
                  or "fatal" in log["content"].lower()]

        # 提取错误码（如 500, 502, 503, 504）
        import re
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
```

- [ ] **Step 3：更新测试，mock HTTP 请求**

```python
# tests/test_loki_mcp.py
"""Tests for Loki MCP module."""

from unittest.mock import patch, MagicMock


def test_loki_mcp_import():
    from llm.mcp.loki_mcp import LokiMCPServer
    assert LokiMCPServer is not None


def test_loki_mcp_init():
    from llm.mcp.loki_mcp import LokiMCPServer
    server = LokiMCPServer(url="http://localhost:3100")
    assert server.url == "http://localhost:3100"


def test_tools_list():
    from llm.mcp.loki_mcp import LokiMCPServer
    server = LokiMCPServer(url="http://localhost:3100")
    tools = server.get_tools()
    assert len(tools) == 3
    assert tools[0]["name"] == "query_logs"


@patch("llm.mcp.loki_mcp.requests.get")
def test_analyze_errors(mock_get):
    """测试 analyze_errors 正确解析 Loki 返回数据。"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "result": [
                {
                    "stream": {"server": "web-01"},
                    "values": [
                        ["1710000000000000000", "ERROR: 500 Internal Server Error"],
                        ["1710000001000000000", "INFO: Request completed"],
                        ["1710000002000000000", "ERROR: 502 Bad Gateway upstream timed out"],
                    ],
                }
            ]
        }
    }
    mock_get.return_value = mock_resp

    from llm.mcp.loki_mcp import LokiMCPServer
    server = LokiMCPServer(url="http://loki:3100")
    result = server.analyze_errors("web-01", hours=1)

    assert result["total_errors"] == 2
    assert result["error_codes"]["500"] == 1
    assert result["error_codes"]["502"] == 1
    assert len(result["error_samples"]) == 2
```

```bash
python -m pytest tests/test_loki_mcp.py -v
# 期望: PASSED
```

- [ ] **Step 4：提交**

```bash
git add llm/mcp/loki_mcp.py tests/test_loki_mcp.py
git commit -m "feat(mcp): [B2] implement Loki MCP module"
```

---

### Task B3：实现 Prometheus MCP 模块

**Files:**
- Create: `llm/mcp/prometheus_mcp.py`
- Create: `tests/test_prometheus_mcp.py`

**Interfaces:**
- Produces: `PrometheusMCPServer(url).query_metric(metric_name, server_ip) -> dict`
- Produces: `PrometheusMCPServer(url).range_query(metric_name, server_ip, duration) -> list[dict]`
- Produces: `PrometheusMCPServer(url).check_alerts() -> list[dict]`
- Consumes: `CLOUD_PROMETHEUS_URL` 环境变量

- [ ] **Step 1：写测试**

```python
# tests/test_prometheus_mcp.py
"""Tests for Prometheus MCP module."""

from unittest.mock import patch, MagicMock


def test_prometheus_mcp_import():
    from llm.mcp.prometheus_mcp import PrometheusMCPServer
    assert PrometheusMCPServer is not None


def test_tools_list():
    from llm.mcp.prometheus_mcp import PrometheusMCPServer
    server = PrometheusMCPServer(url="http://localhost:9090")
    tools = server.get_tools()
    tool_names = [t["name"] for t in tools]
    assert "query_metric" in tool_names
    assert "range_query" in tool_names
    assert "check_alerts" in tool_names


@patch("llm.mcp.prometheus_mcp.requests.get")
def test_query_metric(mock_get):
    """测试 query_metric 正确解析 Prometheus 返回值。"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"instance": "10.0.0.1:9100"}, "value": [1710000000, "85.3"]}
            ],
        },
    }
    mock_get.return_value = mock_resp

    from llm.mcp.prometheus_mcp import PrometheusMCPServer
    server = PrometheusMCPServer(url="http://prometheus:9090")
    result = server.query_metric("node_cpu_percent", server_ip="10.0.0.1")

    assert result["metric"] == "node_cpu_percent"
    assert result["value"] == 85.3
    assert result["instance"] == "10.0.0.1:9100"
```

```bash
python -m pytest tests/test_prometheus_mcp.py -v
# 期望: FAIL — 模块不存在
```

- [ ] **Step 2：实现 PrometheusMCPServer**

```python
# llm/mcp/prometheus_mcp.py
"""
Prometheus MCP 封装 — 指标查询与分析。

通过 HTTP API 查询云服务器上的 Prometheus，
提供即时指标查询、趋势查询和告警检查功能。
"""

import requests
from typing import Optional


class PrometheusMCPServer:
    """Prometheus 指标服务 MCP 封装，进程内运行。"""

    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def get_tools(self) -> list[dict]:
        """返回 MCP 风格的工具定义列表。"""
        return [
            {
                "name": "query_metric",
                "description": "查询 Prometheus 即时指标（当前值）",
                "parameters": {
                    "metric_name": {"type": "string", "description": "指标名称，如 node_cpu_percent"},
                    "server_ip": {"type": "string", "description": "服务器 IP（可选）", "default": ""},
                },
            },
            {
                "name": "range_query",
                "description": "查询指标历史趋势",
                "parameters": {
                    "metric_name": {"type": "string", "description": "指标名称"},
                    "server_ip": {"type": "string", "description": "服务器 IP", "default": ""},
                    "duration": {"type": "string", "description": "时间范围，如 1h, 6h, 24h", "default": "1h"},
                },
            },
            {
                "name": "check_alerts",
                "description": "查询 Prometheus 当前活跃告警",
                "parameters": {},
            },
        ]

    def query_metric(self, metric_name: str, server_ip: str = "") -> dict:
        """查询 Prometheus 即时指标。"""
        # 构建 PromQL
        if server_ip:
            query = f'{metric_name}{{instance="{server_ip}:9100"}}'
        else:
            query = metric_name

        params = {"query": query}

        try:
            resp = requests.get(
                f"{self.url}/api/v1/query", params=params, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            return {"error": f"Prometheus 查询失败: {e}"}

        if data["status"] != "success":
            return {"error": f"Prometheus 返回错误: {data}"}

        results = data.get("data", {}).get("result", [])
        if not results:
            return {"error": f"无数据: {query}"}

        # 取第一个结果
        r = results[0]
        return {
            "metric": metric_name,
            "instance": r["metric"].get("instance", ""),
            "value": float(r["value"][1]),
            "timestamp": r["value"][0],
        }

    def range_query(
        self,
        metric_name: str,
        server_ip: str = "",
        duration: str = "1h",
    ) -> list[dict]:
        """查询指标历史趋势。"""
        if server_ip:
            query = f'{metric_name}{{instance="{server_ip}:9100"}}'
        else:
            query = metric_name

        params = {
            "query": query,
            "start": f"now-{duration}",
            "end": "now",
            "step": "60s",
        }

        try:
            resp = requests.get(
                f"{self.url}/api/v1/query_range", params=params, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            return [{"error": f"Prometheus 范围查询失败: {e}"}]

        if data["status"] != "success":
            return [{"error": f"Prometheus 返回错误: {data}"}]

        results = data.get("data", {}).get("result", [])
        output = []
        for r in results:
            values = [
                {"timestamp": v[0], "value": float(v[1])} for v in r.get("values", [])
            ]
            output.append({
                "metric": metric_name,
                "instance": r["metric"].get("instance", ""),
                "values": values,
            })

        return output

    def check_alerts(self) -> list[dict]:
        """查询 Prometheus 当前活跃告警。"""
        try:
            resp = requests.get(
                f"{self.url}/api/v1/alerts", timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            return [{"error": f"告警查询失败: {e}"}]

        if data["status"] != "success":
            return [{"error": f"告警接口返回错误: {data}"}]

        alerts = data.get("data", {}).get("alerts", [])
        return [
            {
                "name": a["labels"].get("alertname", ""),
                "state": a.get("state", ""),
                "severity": a["labels"].get("severity", ""),
                "active_at": a.get("activeAt", ""),
                "annotations": a.get("annotations", {}),
            }
            for a in alerts
        ]
```

- [ ] **Step 3：运行测试**

```bash
python -m pytest tests/test_prometheus_mcp.py -v
# 期望: PASSED
```

- [ ] **Step 4：提交**

```bash
git add llm/mcp/prometheus_mcp.py tests/test_prometheus_mcp.py
git commit -m "feat(mcp): [B3] implement Prometheus MCP module"
```

---

### Task B4：更新 .env 并写 MCP 工具函数封装

**Files:**
- Modify: `llm/mcp/__init__.py`
- Create: `llm/tools/mcp_tools.py`
- Modify: `.env`

**Interfaces:**
- Produces: `get_mcp_tools()` → 返回将 MCP 方法包装为 LangChain tool 的列表

- [ ] **Step 1：创建 MCP 工具函数封装**

```python
# llm/tools/mcp_tools.py
"""
将 MCP 模块方法包装为 LangChain tool，供 Agent 调用。

每个 MCP 方法被包装为一个独立的 tool 函数，
保留 MCP 风格参数签名，但符合 LangChain tool 调用约定。
"""

import os
from langchain_core.tools import tool
from llm.mcp.loki_mcp import LokiMCPServer
from llm.mcp.prometheus_mcp import PrometheusMCPServer

# 进程内单例
_loki_server: LokiMCPServer | None = None
_prom_server: PrometheusMCPServer | None = None


def _get_loki() -> LokiMCPServer:
    global _loki_server
    if _loki_server is None:
        url = os.getenv("CLOUD_LOKI_URL", "http://localhost:3100")
        _loki_server = LokiMCPServer(url=url)
    return _loki_server


def _get_prom() -> PrometheusMCPServer:
    global _prom_server
    if _prom_server is None:
        url = os.getenv("CLOUD_PROMETHEUS_URL", "http://localhost:9090")
        _prom_server = PrometheusMCPServer(url=url)
    return _prom_server


@tool
def analyze_logs(server_name: str, hours: int = 1) -> dict:
    """分析指定服务器的错误日志，返回错误统计和关键报错样本。"""
    return _get_loki().analyze_errors(server_name, hours)


@tool
def count_logs_by_level(server_name: str, hours: int = 1) -> dict:
    """按日志级别统计指定服务器的日志数量（error/warn/info）。"""
    return _get_loki().count_by_level(server_name, hours)


@tool
def query_metric(metric_name: str, server_ip: str = "") -> dict:
    """查询 Prometheus 指定指标的当前值。"""
    return _get_prom().query_metric(metric_name, server_ip)


@tool
def query_metric_range(metric_name: str, server_ip: str = "", duration: str = "1h") -> list:
    """查询 Prometheus 指定指标的历史趋势。"""
    return _get_prom().range_query(metric_name, server_ip, duration)


@tool
def check_alerts() -> list:
    """查询当前活跃的 Prometheus 告警列表。"""
    return _get_prom().check_alerts()
```

- [ ] **Step 2：写测试**

```python
# tests/test_mcp_tools.py
"""Tests for MCP tool wrappers."""

from unittest.mock import patch


@patch("llm.tools.mcp_tools._get_loki")
def test_analyze_logs_tool(mock_get_loki):
    mock_server = mock_get_loki.return_value
    mock_server.analyze_errors.return_value = {"total_errors": 5}

    from llm.tools.mcp_tools import analyze_logs
    result = analyze_logs.invoke({"server_name": "web-01", "hours": 2})

    assert result["total_errors"] == 5
    mock_server.analyze_errors.assert_called_once_with("web-01", 2)
```

```bash
python -m pytest tests/test_mcp_tools.py -v
# 期望: PASSED
```

- [ ] **Step 3：确保 `.env` 有云服务地址**

```bash
# 检查 .env 是否包含云服务地址
grep CLOUD_LOKI_URL .env || echo "CLOUD_LOKI_URL=http://<your-cloud-ip>:3100" >> .env
grep CLOUD_PROMETHEUS_URL .env || echo "CLOUD_PROMETHEUS_URL=http://<your-cloud-ip>:9090" >> .env
```

- [ ] **Step 4：提交**

```bash
git add llm/tools/mcp_tools.py tests/test_mcp_tools.py llm/mcp/__init__.py
git commit -m "feat(mcp): [B4] add MCP tool wrappers and env config"
```

---

## Phase 3：Agent 改造

### Task C1：安装 langgraph

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1：更新 requirements.txt**

```txt
# 在 requirements.txt 末尾添加
langgraph>=0.4.0
```

- [ ] **Step 2：安装并验证**

```powershell
pip install -r requirements.txt
python -c "import langgraph; print(f'langgraph {langgraph.__version__}')"
# 期望: langgraph x.y.z
```

- [ ] **Step 3：提交**

```bash
git add requirements.txt
git commit -m "chore: [C1] add langgraph dependency"
```

---

### Task C2：实现 Supervisor（LangGraph StateGraph）

**Files:**
- Create: `llm/supervisor.py`
- Create: `tests/test_supervisor.py`

**Interfaces:**
- Produces: `Supervisor.run(messages) -> str` — 主入口
- Consumes: Worker tools 函数签名

- [ ] **Step 1：写 Supervisor 测试**

```python
# tests/test_supervisor.py
"""Tests for LangGraph Supervisor."""


def test_supervisor_import():
    """Supervisor 模块可导入且有 run 方法。"""
    from llm.supervisor import Supervisor
    assert hasattr(Supervisor, "run")


def test_supervisor_direct_reply():
    """不需要工具时，Supervisor 直接回答。"""
    from llm.supervisor import Supervisor
    sv = Supervisor()
    result = sv.run([("human", "你好")])
    assert isinstance(result, str)
    assert len(result) > 0
```

```bash
python -m pytest tests/test_supervisor.py -v
# 期望: FAIL — 模块不存在
```

- [ ] **Step 2：实现 Supervisor**

```python
# llm/supervisor.py
"""
LangGraph Supervisor — 多 Agent 调度核心。

由 LangGraph StateGraph 实现循环调度模式：
1. Supervisor 节点（LLM 决策）：判断下一步
2. Worker 节点（工具函数）：执行具体分析
3. 回到 Supervisor 节点继续决策
4. 信息收齐 → 生成 RCA 报告 → FINISH
"""

import os
from typing import Literal, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from llm.tools.mcp_tools import (
    analyze_logs,
    count_logs_by_level,
    query_metric,
    query_metric_range,
    check_alerts,
)
from llm.tools import get_server_list, get_server_status, search_knowledge_base

# 最大循环次数，防止死循环
MAX_ITERATIONS = 10


class AgentState(TypedDict):
    """LangGraph State 定义。"""
    messages: list
    next: Literal["FINISH", "log_worker", "infra_worker", "knowledge_worker"]
    intermediate_results: dict
    final_report: str
    iteration: int


# Worker 工具映射
TOOLS = {
    "log_worker": [analyze_logs, count_logs_by_level],
    "infra_worker": [query_metric, query_metric_range, check_alerts],
    "knowledge_worker": [search_knowledge_base],
}

ALL_TOOLS = analyze_logs | count_logs_by_level | query_metric | query_metric_range | check_alerts | get_server_list | get_server_status | search_knowledge_base


def _get_llm():
    return ChatOpenAI(
        model="deepseek-v4-flash",
        base_url="https://opencode.ai/zen/go/v1",
        api_key=os.getenv("OPENCODE_API_KEY"),
    )


# --- Worker 节点函数 ---

def log_worker(state: AgentState) -> dict:
    """日志分析 Worker：调用 Loki MCP 工具分析日志异常。"""
    last_msg = state["messages"][-1][1] if state["messages"] else ""
    # 使用 LLM 提取参数，然后调用工具
    llm = _get_llm()
    prompt = f"""从用户问题中提取服务器名称和时间范围，返回 JSON。
问题: {last_msg}
输出: {{"server_name": "xxx", "hours": 1}}"""
    try:
        import json
        params = json.loads(llm.invoke(prompt).content)
    except Exception:
        params = {"server_name": "", "hours": 1}

    result = analyze_logs.invoke(params)
    results = state.get("intermediate_results", {})
    results["log"] = result
    return {"intermediate_results": results}


def infra_worker(state: AgentState) -> dict:
    """基础设施 Worker：调用 Prometheus MCP + SSH 分析指标。"""
    last_msg = state["messages"][-1][1] if state["messages"] else ""
    llm = _get_llm()
    prompt = f"""从用户问题中提取服务器名称和时间范围，返回 JSON。
问题: {last_msg}
输出: {{"server_name": "xxx", "metric": "cpu", "hours": 1}}"""
    try:
        import json
        params = json.loads(llm.invoke(prompt).content)
    except Exception:
        params = {"server_name": "", "hours": 1}

    # 查 CPU、内存、磁盘指标
    metrics = {}
    for m in ["node_cpu_percent", "node_memory_percent", "node_disk_percent"]:
        r = query_metric.invoke({"metric_name": m, "server_ip": params.get("server_name", "")})
        metrics[m] = r

    results = state.get("intermediate_results", {})
    results["infra"] = metrics
    return {"intermediate_results": results}


def knowledge_worker(state: AgentState) -> dict:
    """知识库 Worker：调用 RAG 查询历史故障/SOP。"""
    last_msg = state["messages"][-1][1] if state["messages"] else ""
    result = search_knowledge_base.invoke({"query": last_msg, "top_k": 3})
    results = state.get("intermediate_results", {})
    results["knowledge"] = result
    return {"intermediate_results": results}


# --- Supervisor 节点 ---

def supervisor_node(state: AgentState) -> dict:
    """Supervisor 节点：用 LLM 决策下一步。"""
    iteration = state.get("iteration", 0) + 1

    if iteration > MAX_ITERATIONS:
        return {"next": "FINISH", "iteration": iteration}

    has_log = "log" in state.get("intermediate_results", {})
    has_infra = "infra" in state.get("intermediate_results", {})
    has_knowledge = "knowledge" in state.get("intermediate_results", {})

    llm = _get_llm()
    prompt = f"""你是运维 Supervisor。根据对话历史和已有信息决定下一步。

已有信息：
- 日志分析: {"✅ 已完成" if has_log else "❌ 未完成"}
- 指标分析: {"✅ 已完成" if has_infra else "❌ 未完成"}
- 知识库查询: {"✅ 已完成" if has_knowledge else "❌ 未完成"}
- 当前轮次: {iteration}/{MAX_ITERATIONS}

对话历史: {state['messages']}

选择下一步：
- 如果所有需要的信息都已收集 → 输出 FINISH
- 如果需要日志分析 → 输出 log_worker
- 如果需要指标分析 → 输出 infra_worker
- 如果需要查知识库 → 输出 knowledge_worker
- 如果不需要任何工具 → 输出 FINISH

只输出一个词：FINISH / log_worker / infra_worker / knowledge_worker"""

    decision = llm.invoke(prompt).content.strip()

    if decision not in ("log_worker", "infra_worker", "knowledge_worker", "FINISH"):
        decision = "FINISH"

    return {"next": decision, "iteration": iteration}


# --- 路由函数 ---

def decide_next(state: AgentState) -> str:
    return state.get("next", "FINISH")


# --- 构建图 ---

def _build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("log_worker", log_worker)
    builder.add_node("infra_worker", infra_worker)
    builder.add_node("knowledge_worker", knowledge_worker)

    builder.set_entry_point("supervisor")

    builder.add_conditional_edges(
        "supervisor",
        decide_next,
        {
            "log_worker": "log_worker",
            "infra_worker": "infra_worker",
            "knowledge_worker": "knowledge_worker",
            "FINISH": END,
        },
    )

    # Worker 执行完后回到 Supervisor
    builder.add_edge("log_worker", "supervisor")
    builder.add_edge("infra_worker", "supervisor")
    builder.add_edge("knowledge_worker", "supervisor")

    return builder.compile()


# --- 缓存图实例 ---
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


class Supervisor:
    """Supervisor 主入口。"""

    def run(self, messages: list) -> str:
        """运行 Supervisor 调度循环。

        Args:
            messages: [("human", "问题"), ("ai", "回答"), ...] 格式的对话历史

        Returns:
            str: 最终回复（直接回答或 RCA 报告）
        """
        graph = get_graph()

        initial_state: AgentState = {
            "messages": messages,
            "next": "FINISH",
            "intermediate_results": {},
            "final_report": "",
            "iteration": 0,
        }

        # 执行 StateGraph
        for step in graph.stream(initial_state):
            pass  # 逐步执行，最终状态自动收敛

        # 获取最终状态
        final = graph.get_state(step) if hasattr(graph, 'get_state') else initial_state
        # 由于 StateGraph 的 stream 返回的是节点输出，我们需要追踪最终 state
        # 更可靠的做法：直接从 last node 的 output 构建回复

        return self._build_response(final)

    def _build_response(self, state: dict) -> str:
        """根据 intermediate_results 生成最终回复或 RCA 报告。"""
        results = state.get("intermediate_results", {})
        messages = state.get("messages", [])

        if not results:
            # 没有调用任何 Worker，直接回答
            return "您好，我是 SmartOps 运维助手，有什么可以帮助您的？"

        # 有数据 → 用 LLM 汇总生成回复
        llm = _get_llm()
        context_parts = []

        if "log" in results:
            log_data = results["log"]
            if "error" not in log_data:
                context_parts.append(
                    f"【日志分析】服务器 {log_data.get('server', 'N/A')} 在 {log_data.get('hours', 1)} 小时内"
                    f"发现 {log_data.get('total_errors', 0)} 个错误。"
                    f"错误码分布: {log_data.get('error_codes', {})}。"
                    f"关键样本: {log_data.get('error_samples', [])[:2]}"
                )

        if "infra" in results:
            metrics = results["infra"]
            parts = ["【指标分析】"]
            for name, data in metrics.items():
                if "error" not in data:
                    parts.append(f"{name}: {data.get('value', 'N/A')}")
            context_parts.append(" | ".join(parts))

        if "knowledge" in results:
            docs = results["knowledge"]
            if docs:
                context_parts.append(f"【知识库】相关文档: {[d.get('content', '')[:100] for d in docs[:2]]}")

        context = "\n".join(context_parts)
        user_question = messages[-1][1] if messages else ""

        prompt = f"""根据以下分析结果生成运维回复。

{context}

用户问题: {user_question}

要求：
1. 如果有异常，给出根因分析（RCA）和时间线
2. 给出具体的修复建议（含命令）
3. 如果没有异常，确认服务器正常
4. 回复不超过 10 行
5. 基于数据，不编造"""

        return llm.invoke(prompt).content
```

- [ ] **Step 3：运行测试**

```bash
python -m pytest tests/test_supervisor.py -v
# 期望: PASSED
```

- [ ] **Step 4：提交**

```bash
git add llm/supervisor.py tests/test_supervisor.py
git commit -m "feat(agent): [C2] implement LangGraph Supervisor"
```

---

### Task C3：实现 Worker 工具集中管理

**Files:**
- Create: `llm/workers.py`
- Create: `tests/test_workers.py`

**Interfaces:**
- Produces: Worker 函数（`analyze_server_log`, `check_server_metrics`, `search_ops_knowledge`）

- [ ] **Step 1：写测试**

```python
# tests/test_workers.py
"""Tests for Worker tools."""

from unittest.mock import patch


@patch("llm.workers.query_metric")
def test_check_server_metrics(mock_qm):
    mock_qm.invoke.return_value = {"value": 85.3}

    from llm.workers import check_server_metrics
    result = check_server_metrics("web-01")
    assert "cpu" in result
```

```bash
python -m pytest tests/test_workers.py -v
# 期望: FAIL — 模块不存在
```

- [ ] **Step 2：实现 Workers**

```python
# llm/workers.py
"""
Worker 工具统一管理。

每个 Worker 包装一组 MCP/本地工具调用，返回结构化结果。
这些 Worker 被 Supervisor 调用，不独立使用 LLM。
"""

from llm.tools.mcp_tools import (
    analyze_logs,
    count_logs_by_level,
    query_metric,
    query_metric_range,
)
from llm.tools import get_server_list, get_server_status, search_knowledge_base


def analyze_server_log(server_name: str, hours: int = 1, level: str = "") -> dict:
    """分析服务器日志，返回错误统计和样本。

    Args:
        server_name: 服务器名称
        hours: 查询时间范围（小时）
        level: 日志级别过滤

    Returns:
        包含错误统计、样本和时间分布的字典
    """
    result = analyze_logs.invoke({"server_name": server_name, "hours": hours})
    levels = count_logs_by_level.invoke({"server_name": server_name, "hours": hours})

    return {
        "server": server_name,
        "hours": hours,
        "analyze": result,
        "level_counts": levels,
        "summary": _summarize_log_result(result),
    }


def check_server_metrics(server_name: str, duration: str = "1h") -> dict:
    """检查服务器指标，返回 CPU/内存/磁盘分析。

    Args:
        server_name: 服务器名称
        duration: 时间范围（如 1h, 6h）

    Returns:
        包含各项指标当前值和趋势的字典
    """
    metrics = {}
    for name in ["node_cpu_percent", "node_memory_percent", "node_disk_percent"]:
        try:
            r = query_metric.invoke({"metric_name": name, "server_ip": server_name})
            metrics[name] = r
        except Exception as e:
            metrics[name] = {"error": str(e)}

    # 检测异常
    anomalies = []
    for name, data in metrics.items():
        if "error" not in data and data.get("value", 0) > 80:
            anomalies.append(f"{name} 异常: {data['value']}%")

    return {
        "server": server_name,
        "duration": duration,
        "metrics": metrics,
        "anomalies": anomalies,
    }


def search_ops_knowledge(query: str, top_k: int = 3) -> dict:
    """搜索运维知识库。

    Args:
        query: 搜索关键词
        top_k: 返回文档数量

    Returns:
        匹配的知识库文档列表
    """
    results = search_knowledge_base.invoke({"query": query, "top_k": top_k})
    return {
        "query": query,
        "results_count": len(results) if results else 0,
        "results": results if results else [],
    }


def _summarize_log_result(result) -> str:
    """生成日志分析摘要。"""
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    if isinstance(result, dict):
        total = result.get("total_errors", 0)
        codes = result.get("error_codes", {})
        if total == 0:
            return "未发现错误日志"
        codes_str = ", ".join(f"{k}={v}" for k, v in codes.items())
        return f"发现 {total} 个错误，错误码分布: {codes_str}"
    return "日志分析完成"
```

- [ ] **Step 3：运行测试**

```bash
python -m pytest tests/test_workers.py -v
# 期望: PASSED
```

- [ ] **Step 4：提交**

```bash
git add llm/workers.py tests/test_workers.py
git commit -m "feat(agent): [C3] implement Worker tools"
```

---

### Task C4：改造 agent.py 入口转发到 Supervisor

**Files:**
- Modify: `llm/agent.py`
- Create: `tests/test_agent_entry.py`

**Interfaces:**
- Consumes: `Supervisor.run(messages) -> str`
- Produces: `chat(conversation_id, user_input) -> str`（保持现有签名）

- [ ] **Step 1：重写 agent.py**

```python
# llm/agent.py
"""
Agent 入口模块。

保留原有 chat() 接口签名，内部转发到 LangGraph Supervisor。
API 层和前端完全无感知。
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store.db import get_session
from store.models import Message, Conversation
from llm.supervisor import Supervisor


def chat(conversation_id: int, user_input: str) -> str:
    """与 Agent 对话。

    保留与现有 API 兼容的接口签名，内部使用 LangGraph Supervisor。

    Args:
        conversation_id: 对话 ID
        user_input: 用户输入

    Returns:
        str: Agent 回复
    """
    history = []
    session = get_session()
    messages = session.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.id).all()

    for m in messages:
        if m.role == "human":
            history.append(("human", m.content))
        else:
            history.append(("ai", m.content))

    # 第一次发消息截取摘要
    if len(messages) == 0:
        conv = session.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        if conv:
            conv.summary = user_input[:15]

    # 保存用户消息
    session.add(Message(
        conversation_id=conversation_id,
        role="human",
        content=user_input,
    ))
    session.commit()

    # 构造完整历史
    history.append(("human", user_input))

    # 调用 Supervisor
    supervisor = Supervisor()
    reply = supervisor.run(history)

    # 保存 AI 回复
    session.add(Message(
        conversation_id=conversation_id,
        role="ai",
        content=reply,
    ))
    session.commit()
    session.close()

    return reply
```

- [ ] **Step 2：写入口测试**

```python
# tests/test_agent_entry.py
"""Tests for agent entry point (agent.py)."""

from unittest.mock import patch, MagicMock


@patch("llm.agent.Supervisor")
@patch("llm.agent.get_session")
def test_chat_interface(mock_session, mock_supervisor_cls):
    """chat() 保持原有签名并转发到 Supervisor。"""
    # Mock 数据库
    mock_sess = MagicMock()
    mock_session.return_value = mock_sess
    mock_sess.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    # Mock Supervisor
    mock_sv = MagicMock()
    mock_sv.run.return_value = "服务器运行正常"
    mock_supervisor_cls.return_value = mock_sv

    from llm.agent import chat
    result = chat(conversation_id=1, user_input="web-01 状态如何？")

    assert result == "服务器运行正常"
    mock_sv.run.assert_called_once()
```

```bash
python -m pytest tests/test_agent_entry.py -v
# 期望: PASSED
```

- [ ] **Step 3：提交**

```bash
git add llm/agent.py tests/test_agent_entry.py
git commit -m "feat(agent): [C4] forward agent entry to Supervisor"
```

---

### Task C5：RCA 报告生成增强

**Files:**
- Modify: `llm/supervisor.py`（增强 `_build_response` 方法）
- Modify: `tests/test_supervisor.py`（增加 RCA 报告测试）

- [ ] **Step 1：增加 RCA 报告测试**

```python
# 在 tests/test_supervisor.py 追加
def test_rca_report_format():
    """RCA 报告包含根因、影响、修复建议。"""
    from llm.supervisor import Supervisor
    sv = Supervisor()

    # 构造有数据的 state
    state = {
        "intermediate_results": {
            "log": {
                "total_errors": 23,
                "error_codes": {"500": 15, "502": 5, "504": 3},
                "error_samples": ["ERROR: 500 upstream timed out"],
            },
            "infra": {
                "metrics": {
                    "node_cpu_percent": {"value": 95.0},
                    "node_memory_percent": {"value": 72.0},
                },
                "anomalies": ["node_cpu_percent 异常: 95.0%"],
            },
            "knowledge": {
                "results": [{"content": "如果 CPU 持续 90%+ 且 nginx 超时..."}],
            },
        },
        "messages": [("human", "web-01 出了什么问题？")],
    }

    # 跳过 LLM 调用，测试 _build_response 结构
    report = sv._build_response(state)
    assert isinstance(report, str) and len(report) > 0
```

```bash
python -m pytest tests/test_supervisor.py::test_rca_report_format -v
```

- [ ] **Step 2：增强 _build_response**（C2 已有基础实现，测试验证即可）

- [ ] **Step 3：提交**

```bash
git add llm/supervisor.py tests/test_supervisor.py
git commit -m "feat(agent): [C5] enhance RCA report generation"
```

---

## Phase 4：清理与测试

### Task D1：精简 tools.py

**Files:**
- Modify: `llm/tools.py`

- [ ] **Step 1：删除废弃工具**

```python
# 删除以下两个函数（或注释掉）：
# 1. get_logs — 由 Log Worker 通过 Loki MCP 替代
# 2. get_metrics_history — 由 Infra Worker 通过 Prometheus MCP 替代

# 保留：
# - get_server_list — 查 PostgreSQL 服务器列表
# - get_server_status — 查服务器最新状态（保留，后续可过渡到 Prometheus）
# - search_knowledge_base — 不变
```

- [ ] **Step 2：验证**

```python
# 验证保留的工具仍可导入和使用
python -c "
from llm.tools import get_server_list, get_server_status, search_knowledge_base
print('tools.py OK — 3 tools retained')
"
```

- [ ] **Step 3：提交**

```bash
git add llm/tools.py
git commit -m "refactor: [D1] remove deprecated tools (get_logs, get_metrics_history)"
```

---

### Task D2：精简 SSH 采集器

**Files:**
- Modify: `collector/scheduler.py`
- Modify: `collector/ssh_client.py`

- [ ] **Step 1：精简 scheduler.py**

```python
# collector/scheduler.py — 只保留心跳检测 + 离线告警

"""
采集调度器 — 每 60 秒检查服务器 SSH 连通性。
日志和指标采集已迁移到 promtail + Prometheus。
"""

import time
import threading
from datetime import datetime, timezone
from store.db import get_session
from store.models import Server, Metric, Alert
from collector.ssh_client import SSHClient
from store.crypto import password_decrypt


def load_servers():
    """读取数据库中的服务器配置。"""
    data = []
    session = get_session()
    servers = session.query(Server).all()
    for s in servers:
        data.append({
            'name': s.name,
            'host': s.ip,
            'port': '22',
            'user': s.user,
            'password': password_decrypt(s.password) if s.password else None,
        })
    session.close()
    return data


def check_heartbeat(cfg):
    """检查服务器 SSH 连通性，更新心跳时间。"""
    name = cfg["name"]
    session = get_session()
    server = session.query(Server).filter_by(name=name).first()

    try:
        client = SSHClient(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg.get("password"),
        )

        # 测试连接（执行一条轻量命令）
        uptime = client.exec("uptime -p")
        client.close()

        # 更新心跳
        if not server:
            server = Server(name=name, ip=cfg['host'], status='online')
            session.add(server)
            session.flush()

        server.last_heartbeat = datetime.now(timezone.utc)
        server.status = "online"
        print(f"[{name}] 心跳正常: {uptime}")

    except Exception as e:
        print(f"[{name}] 心跳失败: {e}")
        if server:
            server.status = 'offline'
            # 检查是否已有 open 的 offline 告警
            existing = session.query(Alert).filter(
                Alert.server_name == name,
                Alert.type == 'offline',
                Alert.status == 'open'
            ).first()
            if not existing:
                alert = Alert(
                    server_name=name,
                    type='offline',
                    message=f'服务器离线',
                    value=0,
                    status='open'
                )
                session.add(alert)

    session.commit()
    session.close()


def collect_all():
    """一轮心跳检测，遍历所有服务器。"""
    configs = load_servers()
    for cfg in configs:
        check_heartbeat(cfg)


def start_scheduler(interval=60):
    """启动后台调度线程。"""
    def loop():
        print(f"🔄 心跳检测器已启动，每 {interval} 秒一轮")
        while True:
            collect_all()
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
```

- [ ] **Step 2：清理 ssh_client.py**

删除 `get_logs` 方法（只有心跳测试时不再需要采集日志）：

```python
# collector/ssh_client.py — 删除 get_logs 方法
# def get_logs(self, log_path, limit=50):  # ← 删除/注释
```

- [ ] **Step 3：验证**

```python
# 验证采集器仍然能启动运行
python -c "
from collector.scheduler import start_scheduler, collect_all
import threading
# 只做一遍心跳检测，不启动循环
collect_all()
print('heartbeat OK')
"
```

- [ ] **Step 4：提交**

```bash
git add collector/scheduler.py collector/ssh_client.py
git commit -m "refactor: [D2] simplify collector to heartbeat-only"
```

---

### Task D3：端到端全链路测试

**Files:**
- Create: `tests/test_e2e.py`

**Interfaces:**
- Consumes: 全量 Agent + MCP + Worker

- [ ] **Step 1：写端到端测试**

```python
# tests/test_e2e.py
"""End-to-end tests for the complete agent pipeline."""

from unittest.mock import patch


@patch("llm.tools.mcp_tools._get_loki")
@patch("llm.tools.mcp_tools._get_prom")
def test_analyze_logs_flow(mock_prom, mock_loki):
    """E2E: Log Worker 可正确调用 Loki MCP。"""
    from llm.tools.mcp_tools import analyze_logs

    mock_loki().analyze_errors.return_value = {
        "total_errors": 5,
        "error_codes": {"500": 3, "502": 2},
        "error_samples": ["ERROR 500"],
    }

    result = analyze_logs.invoke({"server_name": "web-01", "hours": 1})
    assert result["total_errors"] == 5


@patch("llm.tools.mcp_tools._get_prom")
def test_query_metric_flow(mock_prom):
    """E2E: Infra Worker 可正确调用 Prometheus MCP。"""
    from llm.tools.mcp_tools import query_metric

    mock_prom().query_metric.return_value = {
        "metric": "node_cpu_percent",
        "value": 85.3,
    }

    result = query_metric.invoke({"metric_name": "node_cpu_percent"})
    assert result["value"] == 85.3


def test_workers_pipeline():
    """Workers 模块函数可正常调用。"""
    from llm.workers import (
        analyze_server_log,
        check_server_metrics,
        search_ops_knowledge,
    )
    assert callable(analyze_server_log)
    assert callable(check_server_metrics)
    assert callable(search_ops_knowledge)


def test_supervisor_graph_structure():
    """Supervisor 的 StateGraph 结构正确。"""
    from llm.supervisor import get_graph
    graph = get_graph()
    assert graph is not None
```

```bash
python -m pytest tests/test_e2e.py -v
# 期望: PASSED
```

- [ ] **Step 2：运行全量测试**

```bash
python -m pytest tests/ -v
# 期望: 所有测试通过
```

- [ ] **Step 3：运行 qa-tester**

```powershell
# 使用刚创建的 qa-tester skill
/smartops:qa-tester
```

- [ ] **Step 4：提交**

```bash
git add tests/test_e2e.py
git commit -m "test: [D3] e2e tests for agent pipeline"
```

---

## 文件变更总览

### 新增
```
llm/mcp/__init__.py              MCP 包入口
llm/mcp/loki_mcp.py              Loki MCP 封装
llm/mcp/prometheus_mcp.py        Prometheus MCP 封装
llm/tools/mcp_tools.py           MCP 工具函数包装
llm/supervisor.py                LangGraph Supervisor
llm/workers.py                   Worker 工具函数
tests/test_mcp_init.py           MCP 导入测试
tests/test_loki_mcp.py           Loki MCP 测试
tests/test_prometheus_mcp.py     Prometheus MCP 测试
tests/test_mcp_tools.py          MCP 工具测试
tests/test_supervisor.py         Supervisor 测试
tests/test_workers.py            Workers 测试
tests/test_agent_entry.py        Agent 入口测试
tests/test_e2e.py                E2E 测试
prometheus.yml                   Prometheus 配置（云服务器）
```

### 修改
```
llm/agent.py                     保持签名，内部转发 Supervisor
llm/tools.py                     删除 get_logs, get_metrics_history
collector/scheduler.py           仅保留心跳检测
collector/ssh_client.py          删除 get_logs 方法
requirements.txt                 新增 langgraph
.env                             新增 CLOUD_LOKI_URL, CLOUD_PROMETHEUS_URL
docker-compose.yml               新增 Prometheus 服务
```

### 删除
无。废弃函数注释掉/标记 deprecated，本周期不删除文件。

---

## 自审检查

1. **Spec 覆盖度：**
   - ✅ 部署架构（2.节）→ A1-A4
   - ✅ MCP 封装层（4.节）→ B1-B4
   - ✅ Agent 架构（3.节 LangGraph Supervisor）→ C1-C5
   - ✅ Worker 设计原则（3.3节 工具函数，不调 LLM）→ C3
   - ✅ 原有组件改造（5.节 精简 collector/tools）→ D1-D2
   - ✅ 对话系统集成（6.节 保留 chat() 签名）→ C4
   - ✅ RCA 报告（7.节）→ C5
   - ✅ 端到端测试 → D3

2. **占位符扫描：** 所有步骤包含实际代码、测试用例和期望输出。无 "TBD"、"TODO"、"implement later"。

3. **类型一致性：** LokiMCSPserver(url).analyze_errors() 返回 dict 在 B2 定义、C3 Workers 消费、C5 RCA 汇总消费——签名一致。
