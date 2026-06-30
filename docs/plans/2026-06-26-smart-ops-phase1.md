# SmartOps Phase 1 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 PostgreSQL 数据库 + Collector 数据采集 + API 接收层，实现服务器监控数据从采集到入库的完整链路。

**Architecture:** Collector 在目标服务器上跑 psutil 采集系统指标，通过 HTTP POST 推送到中央 Flask API，API 写入 PostgreSQL。数据流单向：Collector → API → DB。不包含面板展示（Phase 2）和 LLM 排错（Phase 3）。

**Tech Stack:** Python 3.13, Flask, SQLAlchemy, psycopg2-binary, PostgreSQL 15+, psutil, pyyaml

## 全局约束

- 所有新文件建在 `E:\service-healthcheck\` 下
- 不要修改已有的 `healthcheck.py`、`web.py`、`config.json`、`templates/`、`Dockerfile`、`docker-compose.yml`
- Python 依赖装在 `E:\service-healthcheck\.venv\`（已有的虚拟环境）
- API 服务在本地开发时监听 `127.0.0.1:5001`
- Config 通过环境变量 + `.env` 文件加载，不硬编码
- 错误处理和日志统一：失败重试 3 次，全部失败则 log 并跳过
- Windows 开发环境：PostgreSQL 通过官方 Windows 安装程序安装

```
Phase 1 数据流：
Collector (psutil) ──HTTP POST──→ Flask API (api.py) ──SQL──→ PostgreSQL
                                    ↑
                              .env (DB连接串)
```

---

## 项目文件清单（新增）

```
E:\service-healthcheck\
├── .env                       # 数据库连接串 (NEW)
├── store/                     # 数据库层 (NEW)
│   ├── __init__.py
│   ├── db.py                  # SQLAlchemy engine + session
│   └── models.py              # 数据模型定义
├── api.py                     # Flask API 接收层 (NEW)
├── collector/                 # 采集器 (NEW)
│   ├── collector.py           # 主脚本
│   ├── collector.yml          # 配置模板
│   └── requirements.txt       # psutil requests pyyaml
└── tests/                     # 测试 (NEW)
    └── test_api.py            # API 路由测试
```

---

## 任务依赖

```
Task 1: 环境准备
  └→ Task 2: 数据库连接 + 模型
       └→ Task 3: Flask API
       └→ Task 4: Collector
            └→ Task 5: 集成验证
```

---

## 任务一：环境准备

**Files:**
- Create: `E:\service-healthcheck\\.env`
- Modify: `E:\service-healthcheck\\requirements.txt`

**Interfaces:**
- Consumes: 无
- Produces: `.env` 中的 `DATABASE_URL` 变量，后续所有任务读取此变量

### Step 1: 安装 PostgreSQL 15+

从 https://www.postgresql.org/download/windows/ 下载安装，安装时：
- 端口保持 `5432`
- 设置 postgres 密码（记下来，下一步要写进 .env）

安装完成后测试：
```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -c "SELECT version();"
```
Expected: 显示 PostgreSQL 版本号。

### Step 2: 创建数据库

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -c "CREATE DATABASE smartops;"
```

### Step 3: 启用 pgvector

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "CREATE EXTENSION vector;"
```

### Step 4: 安装 Python 依赖

```powershell
cd E:\service-healthcheck
.venv\Scripts\python -m pip install psycopg2-binary sqlalchemy psutil pyyaml python-dotenv
```

更新 `requirements.txt`，追加：
```
psycopg2-binary
sqlalchemy
psutil
pyyaml
python-dotenv
```

### Step 5: 创建 .env

创建 `E:\service-healthcheck\\.env`：
```ini
DATABASE_URL=postgresql://postgres:你的密码@localhost:5432/smartops
```

### Step 6: 验证连接

```powershell
cd E:\service-healthcheck
.venv\Scripts\python -c "import psycopg2; conn = psycopg2.connect('postgresql://postgres:你的密码@localhost:5432/smartops'); print(conn.closed)"
```
Expected: `0`（表示连接成功）

### Step 7: 创建目录

```powershell
New-Item -ItemType Directory -Path E:\service-healthcheck\store -Force
New-Item -ItemType Directory -Path E:\service-healthcheck\collector -Force
New-Item -ItemType Directory -Path E:\service-healthcheck\tests -Force
```

### Step 8: Commit

```bash
cd E:/service-healthcheck
git add requirements.txt docs/plans/2026-06-26-smart-ops-phase1.md
git commit -m "chore: setup PostgreSQL dev environment and deps"
```

---

## 任务二：数据库连接与模型

**Files:**
- Create: `E:\service-healthcheck\store\__init__.py`
- Create: `E:\service-healthcheck\store\db.py`
- Create: `E:\service-healthcheck\store\models.py`

**Interfaces:**
- Produces `store.db.get_engine()` → SQLAlchemy Engine
- Produces `store.db.init_db()` → 创建所有表
- Produces `store.models` → Base + 所有模型类

### Step 1: store/__init__.py

```python
"""
SmartOps 数据存储层
"""
```

### Step 2: store/db.py

```python
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

load_dotenv()  # 从 .env 加载 DATABASE_URL，多次调用安全

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/smartops")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine))


def get_session():
    return SessionLocal()


def init_db():
    from store.models import Base
    Base.metadata.create_all(bind=engine)
```

### Step 3: store/models.py

```python
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Date
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    ip = Column(String(45))
    os = Column(String(100))
    last_heartbeat = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), default="offline")


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    cpu = Column(Float)
    memory = Column(Float)
    disk = Column(Float)
    net_recv = Column(Integer)
    net_sent = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Probe(Base):
    __tablename__ = "probes"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    name = Column(String(100))
    url = Column(Text)
    status = Column(Boolean)
    latency = Column(Integer)
    diagnosis = Column(Text)
    ssl_expiry = Column(Date)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    log_name = Column(String(100))
    content = Column(Text)
    level = Column(String(20))
    embedding = Column(String)  # Phase 3 改为 pgvector 类型
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    summary = Column(Text)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20))
    content = Column(Text)
    tokens = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

### Step 4: 验证建表

```powershell
cd E:\service-healthcheck
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python -c "from store.db import init_db; init_db(); print('Tables created')"
```

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "\dt"
```
Expected: 显示 agents, metrics, probes, logs, conversations, messages 六张表。

### Step 5: Commit

```bash
cd E:/service-healthcheck
git add store/
git commit -m "feat: add SQLAlchemy models and DB connection"
```

---

## 任务三：Flask API（数据接收层）

**Files:**
- Create: `E:\service-healthcheck\api.py`
- Create: `E:\service-healthcheck\tests\__init__.py`
- Create: `E:\service-healthcheck\tests\test_api.py`

**Interfaces:**
- Consumes: `store.db.init_db()`、`store.db.get_session()`、各模型类
- Produces: HTTP REST API 端点
- Consumed by: Collector（任务四）

### Step 1: api.py

```python
import os
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from store.db import init_db, get_session
from store.models import Agent, Metric, Probe, Log

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ── 启动时初始化数据库 ──

with app.app_context():
    init_db()
    logger.info("Database initialized")


# ── Agent 注册/心跳 ──

@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json()
    name = data.get("server_name")
    if not name:
        return jsonify({"error": "server_name required"}), 400

    session = get_session()
    agent = session.query(Agent).filter_by(name=name).first()
    if not agent:
        agent = Agent(name=name, ip=request.remote_addr or "",
                      os=data.get("os", ""), status="online")
        session.add(agent)
    else:
        agent.ip = request.remote_addr or agent.ip
        agent.os = data.get("os", agent.os)
        agent.status = "online"

    agent.last_heartbeat = datetime.now(timezone.utc)
    session.commit()
    session.close()
    return jsonify({"status": "ok"})


# ── 系统指标上报 ──

@app.route("/api/metrics", methods=["POST"])
def receive_metrics():
    data = request.get_json()
    name = data.get("server_name")
    if not name:
        return jsonify({"error": "server_name required"}), 400

    session = get_session()
    agent = session.query(Agent).filter_by(name=name).first()
    if not agent:
        return jsonify({"error": "unknown agent"}), 404

    metric = Metric(
        agent_id=agent.id,
        cpu=data.get("cpu"),
        memory=data.get("memory"),
        disk=data.get("disk"),
        net_recv=data.get("net_recv"),
        net_sent=data.get("net_sent"),
    )
    session.add(metric)
    session.commit()
    session.close()
    return jsonify({"status": "ok"})


# ── 服务探活上报 ──

@app.route("/api/probes", methods=["POST"])
def receive_probes():
    data = request.get_json()
    name = data.get("server_name")
    if not name:
        return jsonify({"error": "server_name required"}), 400

    session = get_session()
    agent = session.query(Agent).filter_by(name=name).first()
    if not agent:
        return jsonify({"error": "unknown agent"}), 404

    results = data.get("results", [])
    for r in results:
        probe = Probe(
            agent_id=agent.id,
            name=r.get("name"),
            url=r.get("url"),
            status=r.get("status"),
            latency=r.get("latency"),
            diagnosis=r.get("diagnosis", ""),
        )
        session.add(probe)
    session.commit()
    session.close()
    return jsonify({"status": "ok", "count": len(results)})


# ── 日志上报 ──

@app.route("/api/logs", methods=["POST"])
def receive_logs():
    data = request.get_json()
    name = data.get("server_name")
    if not name:
        return jsonify({"error": "server_name required"}), 400

    session = get_session()
    agent = session.query(Agent).filter_by(name=name).first()
    if not agent:
        return jsonify({"error": "unknown agent"}), 404

    entries = data.get("logs", [])
    for entry in entries:
        log = Log(
            agent_id=agent.id,
            log_name=entry.get("log_name"),
            content=entry.get("content"),
            level=entry.get("level", "info"),
        )
        session.add(log)
    session.commit()
    session.close()
    return jsonify({"status": "ok", "count": len(entries)})


# ── 健康检查 ──

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
```

### Step 2: 测试 API

```powershell
cd E:\service-healthcheck
# 终端1：启动 API
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python api.py
```

新开一个终端测试：
```powershell
# 测试心跳
.venv\Scripts\python -c "
import requests
r = requests.post('http://127.0.0.1:5001/api/heartbeat',
    json={'server_name': 'test-server', 'os': 'Windows 11'})
print(r.json())
"

# Expected: {'status': 'ok'}

# 测试指标上报
.venv\Scripts\python -c "
import requests
r = requests.post('http://127.0.0.1:5001/api/metrics',
    json={'server_name': 'test-server', 'cpu': 45.2, 'memory': 62.1, 'disk': 55.0})
print(r.json())
"

# Expected: {'status': 'ok'}

# 验证数据入库
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "SELECT * FROM agents;"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "SELECT cpu, memory, disk FROM metrics;"
```

Expected: 能看到刚插入的数据。

### Step 3: 测试文件 tests/test_api.py

```python
import pytest
import json
import os
os.environ["DATABASE_URL"] = "postgresql://postgres:你的密码@localhost:5432/smartops"

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_heartbeat_missing_name(client):
    resp = client.post("/api/heartbeat", json={})
    assert resp.status_code == 400


def test_heartbeat_creates_agent(client):
    resp = client.post("/api/heartbeat", json={
        "server_name": "test-agent",
        "os": "Linux"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_metrics_unknown_agent(client):
    resp = client.post("/api/metrics", json={
        "server_name": "nonexistent",
        "cpu": 50.0
    })
    assert resp.status_code == 404


def test_metrics_valid(client):
    # 先注册 agent
    client.post("/api/heartbeat", json={"server_name": "metrics-test"})
    # 再上报指标
    resp = client.post("/api/metrics", json={
        "server_name": "metrics-test",
        "cpu": 75.3,
        "memory": 50.0,
        "disk": 30.0
    })
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
```

### Step 4: 跑测试

```powershell
cd E:\service-healthcheck
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python -m pytest tests/test_api.py -v
```

Expected: 5 个 test 全部 PASS。

### Step 5: Commit

```bash
cd E:/service-healthcheck
git add api.py tests/
git commit -m "feat: add Flask API for collector data ingestion"
```

---

## 任务四：Collector（服务器端采集器）

**Files:**
- Create: `E:\service-healthcheck\collector\collector.py`
- Create: `E:\service-healthcheck\collector\collector.yml`
- Create: `E:\service-healthcheck\collector\requirements.txt`

**Interfaces:**
- Consumes: HTTP API（任务三部署的端点）
- Produces: 通过 HTTP POST 向 API 发送采集数据

### Step 1: collector/requirements.txt

```
psutil>=6.0
requests>=2.31
pyyaml>=6.0
```

### Step 2: collector/collector.yml

```yaml
server_name: kkivc-vps
api_url: http://127.0.0.1:5001
api_key: ""              # 预留，后续加认证
interval: 60             # 采集间隔（秒）

# 日志采集（可选）
logs:
  # - name: nginx-error
  #   path: /var/log/nginx/error.log
```

### Step 3: collector/collector.py

```python
#!/usr/bin/env python3
"""
SmartOps Collector — 服务器端系统指标采集器。
采集 CPU/内存/磁盘/网络并推送到中央 API。

用法:
    python collector.py [--config collector.yml]
"""

import os
import sys
import time
import json
import yaml
import logging
import argparse
from pathlib import Path

import psutil
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("collector")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_metrics() -> dict:
    """采集系统指标，返回 dict"""
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()

    return {
        "cpu": round(cpu, 1),
        "memory": round(mem.percent, 1),
        "disk": round(disk.percent, 1),
        "net_recv": net.bytes_recv,
        "net_sent": net.bytes_sent,
    }


def send_heartbeat(config: dict):
    """发送心跳"""
    url = f"{config['api_url']}/api/heartbeat"
    try:
        resp = requests.post(url, json={
            "server_name": config["server_name"],
            "os": f"{sys.platform}",
        }, timeout=10)
        resp.raise_for_status()
        logger.debug("Heartbeat sent")
    except requests.RequestException as e:
        logger.warning(f"Heartbeat failed: {e}")


def send_metrics(config: dict):
    """采集并上报系统指标"""
    metrics = collect_metrics()
    metrics["server_name"] = config["server_name"]
    url = f"{config['api_url']}/api/metrics"

    for attempt in range(3):
        try:
            resp = requests.post(url, json=metrics, timeout=10)
            resp.raise_for_status()
            logger.info(f"Metrics sent: CPU={metrics['cpu']}% MEM={metrics['memory']}%")
            return
        except requests.RequestException as e:
            logger.warning(f"Metrics push failed (attempt {attempt+1}/3): {e}")
            time.sleep(2)

    logger.error(f"Metrics push failed after 3 attempts")


def tail_logs(config: dict, cursors: dict) -> list:
    """读取日志新增行，返回日志条目列表"""
    entries = []
    for log_cfg in config.get("logs", []):
        path = log_cfg["path"]
        name = log_cfg["name"]

        try:
            p = Path(path)
            if not p.exists():
                continue

            stat = p.stat()
            cursor = cursors.get(name, {})

            # 文件被轮转或第一次读取 → 读末尾 100 行
            if cursor.get("inode") != stat.st_ino:
                cursors[name] = {"inode": stat.st_ino, "offset": 0}
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                lines = lines[-100:]
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(cursor["offset"])
                    lines = f.readlines()
                cursors[name]["offset"] = p.stat().st_size

            for line in lines:
                line = line.strip()
                if line:
                    entries.append({
                        "log_name": name,
                        "content": line,
                        "level": infer_level(line),
                    })
        except OSError as e:
            logger.warning(f"Log read error ({path}): {e}")

    return entries


def infer_level(line: str) -> str:
    """根据日志内容推断级别"""
    line_lower = line.lower()
    if "error" in line_lower or "critical" in line_lower or "panic" in line_lower:
        return "error"
    if "warn" in line_lower:
        return "warn"
    return "info"


def send_logs(config: dict, cursors: dict):
    """采集并上报日志"""
    entries = tail_logs(config, cursors)
    if not entries:
        return

    url = f"{config['api_url']}/api/logs"
    try:
        resp = requests.post(url, json={
            "server_name": config["server_name"],
            "logs": entries,
        }, timeout=10)
        resp.raise_for_status()
        logger.info(f"Logs sent: {len(entries)} entries")
    except requests.RequestException as e:
        logger.warning(f"Log push failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="SmartOps Collector")
    parser.add_argument("--config", default="collector.yml", help="配置文件路径")
    args = parser.parse_args()

    config = load_config(args.config)
    logger.info(f"Collector started for server: {config['server_name']}")
    logger.info(f"API: {config['api_url']}, interval: {config['interval']}s")

    cursors = {}
    send_heartbeat(config)

    while True:
        send_metrics(config)
        send_logs(config, cursors)
        time.sleep(config["interval"])


if __name__ == "__main__":
    main()
```

### Step 4: 本地测试 Collector

确认 API 正在运行（任务三已启动），然后：

```powershell
cd E:\service-healthcheck\collector
..\.venv\Scripts\python collector.py --interval 10
```

Expected: 每 10s 打印一条 "Metrics sent: CPU=xx%"。

等几轮后验证 PostgreSQL：
```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "SELECT cpu, memory, disk, created_at FROM metrics ORDER BY id DESC LIMIT 5;"
```
Expected: 显示最近 5 条采集数据。

### Step 5: Commit

```bash
cd E:/service-healthcheck
git add collector/
git commit -m "feat: add system metrics collector"
```

---

## 任务五：集成验证

确保整个链路跑通。

### Step 1: 启动 API

```powershell
cd E:\service-healthcheck
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python api.py
```
API 监听 `127.0.0.1:5001`。

### Step 2: 在另一个终端启动 Collector

```powershell
cd E:\service-healthcheck\collector
..\.venv\Scripts\python collector.py --interval 15
```

### Step 3: 验证端到端

等 30 秒（collector 跑两轮后），验证：

```powershell
# 查 agents 表 — 应有 agent 记录
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "SELECT * FROM agents;"

# 查 metrics 表 — 应有两条以上记录
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "SELECT id, cpu, memory, disk, created_at FROM metrics ORDER BY id;"
```

Expected:
- agents 表：一条记录（name=kkivc-vps, status=online）
- metrics 表：至少 2 条记录，cpu/memory/disk 有数值

### Step 4: API 测试验证

```powershell
cd E:\service-healthcheck
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python -m pytest tests/test_api.py -v
```
Expected: 全部 PASS。

### Step 5: 提交最终版本

```bash
cd E:/service-healthcheck
git add -A
git commit -m "feat: SmartOps Phase 1 - data ingestion pipeline complete"
```
