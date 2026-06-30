# SmartOps Phase 1 — 学习路线

> **这不是"实施计划"，这是"学习计划"。** 每一步的目标是学会一个概念，顺手把系统搭起来。代码你自己敲，我提供思路、示例、和验收标准。

---

## 总览：学完这个阶段你会什么

| 概念 | 学到什么 |
|------|---------|
| PostgreSQL | 装库、建表、SQL 基础、Python 连 PG |
| SQLAlchemy | ORM 是什么、模型怎么定义、表和类怎么映射 |
| Flask API | 全你会的，但这次接的是 PG 不是 SQLite |
| REST API 设计 | 什么该 POST、什么该返回、HTTP 状态码 |
| psutil | 采集 CPU/内存/磁盘，看系统指标 |
| 多层架构 | Collector → API → DB 三层分离 |

**技术债（学完 Phase 1 再回头看）：**

- 没有认证（API key 以后再加）
- 没有前端（Phase 2 做 Streamlit 面板）
- 日志向量搜索还没做（Phase 3）

---

## 学习阶段 1：PostgreSQL 基础

**目标：** 装好 PostgreSQL，学会建库建表、基本 SQL。

### 1.1 安装 PostgreSQL

官网下载 Windows 安装程序：
https://www.postgresql.org/download/windows/

安装时记下管理员密码（设一个你记得住的），端口默认 5432。

**验证：**
```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -c "SELECT version();"
```

> 如果提示 `psql` 找不到，去你安装的版本号目录找（可能是 16、17、18）。

### 1.2 创建数据库 + 启用 pgvector

```powershell
# 创建项目数据库（名字就叫 smartops）
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -c "CREATE DATABASE smartops;"

# 切换到 smartops 数据库，开启 vector 扩展
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "CREATE EXTENSION vector;"
```

**pgvector 是什么？** 让 PostgreSQL 能存向量数据、做相似度搜索的插件。Phase 3 做 RAG 日志检索时会用到。现在先装好。

### 1.3 基础 SQL 练习（自己敲一遍）

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops
```

进了 psql 交互终端后，敲：

```sql
-- 创建一张测试表
CREATE TABLE test_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    ip VARCHAR(45),
    status VARCHAR(20) DEFAULT 'offline',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 插入数据
INSERT INTO test_servers (name, ip, status) VALUES ('vps-1', '1.2.3.4', 'online');
INSERT INTO test_servers (name, ip, status) VALUES ('vps-2', '5.6.7.8', 'offline');

-- 查询
SELECT * FROM test_servers;
SELECT * FROM test_servers WHERE status = 'online';
SELECT COUNT(*) FROM test_servers;

-- 清理
DROP TABLE test_servers;
```

> 熟悉下 PG 的语法，注意跟 SQLite 的区别：`SERIAL` 替代 `INTEGER PRIMARY KEY AUTOINCREMENT`，`NOW()` 替代 `datetime('now')`。

**验收：** `\dt` 显示 0 张表（test_servers 已删），`\q` 退出。

---

## 学习阶段 2：Python 连 PostgreSQL

**目标：** 学会用 Python 操作 PostgreSQL。

### 2.1 安装依赖

```powershell
cd E:\service-healthcheck
.venv\Scripts\python -m pip install psycopg2-binary sqlalchemy psutil pyyaml python-dotenv
```

解释每个包干什么的：
- **psycopg2-binary**：Python 连 PostgreSQL 的驱动，binary 版 Windows 免编译
- **SQLAlchemy**：ORM（对象关系映射），让你用 Python 类操作数据库表
- **psutil**：采集系统指标的库
- **pyyaml**：解析 yml 配置文件的库
- **python-dotenv**：从 `.env` 文件读环境变量

### 2.2 用 psycopg2 直接连 PG

新建一个临时测试文件 `test_pg.py`：

```python
import psycopg2

# 连数据库
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    user="postgres",
    password="你的密码",
    dbname="smartops"
)

cur = conn.cursor()

# 建表
cur.execute("""
    CREATE TABLE IF NOT EXISTS test_metrics (
        id SERIAL PRIMARY KEY,
        cpu FLOAT,
        memory FLOAT,
        created_at TIMESTAMP DEFAULT NOW()
    )
""")

# 插入
cur.execute("INSERT INTO test_metrics (cpu, memory) VALUES (%s, %s)", (45.2, 62.1))
conn.commit()

# 查询
cur.execute("SELECT * FROM test_metrics ORDER BY id DESC LIMIT 5")
rows = cur.fetchall()
for row in rows:
    print(row)

# 清理
cur.execute("DROP TABLE test_metrics")
conn.commit()

cur.close()
conn.close()
```

跑一下：
```powershell
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python test_pg.py
```

> 看到了吗？`%s` 是 psycopg2 的参数占位符，不像 Python 字符串的 `%s`。这是防止 SQL 注入的。

**验收：** 打印出刚插入的那条记录，无报错。

### 2.3 改成 SQLAlchemy ORM 版本

把上面的代码扔掉，用 SQLAlchemy 重新写一遍。新建 `test_orm.py`：

```python
from sqlalchemy import create_engine, Column, Integer, Float, DateTime, func
from sqlalchemy.orm import declarative_base
from datetime import datetime

DATABASE_URL = "postgresql://postgres:你的密码@localhost:5432/smartops"

engine = create_engine(DATABASE_URL)
Base = declarative_base()


class TestMetric(Base):
    __tablename__ = "test_metrics_orm"

    id = Column(Integer, primary_key=True)
    cpu = Column(Float)
    memory = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


# 建表
Base.metadata.create_all(bind=engine)
#
# 插入
from sqlalchemy.orm import Session
session = Session(engine)

metric = TestMetric(cpu=45.2, memory=62.1)
session.add(metric)
session.commit()

# 查询
results = session.query(TestMetric).order_by(TestMetric.id.desc()).limit(5).all()
for r in results:
    print(r.id, r.cpu, r.memory, r.created_at)

# 清理
TestMetric.__table__.drop(engine)

session.close()
```

跑：
```powershell
.venv\Scripts\python test_orm.py
```

**两个要点：**
1. `__tablename__` 指定表名，不写的话 SQLAlchemy 会自动生成奇怪的名字
2. `Column(DateTime, default=datetime.utcnow)` — 注意是传函数名 `datetime.utcnow`，不是调它 `datetime.utcnow()`。传函数名=每创建一行自动设当前时间，调函数名=程序启动时固定值

**验收：** 打印出插入的记录，无报错。删掉两个测试文件 `test_pg.py` 和 `test_orm.py`。

---

## 学习阶段 3：建数据模型

**目标：** 定义 SmartOps 的 6 张表。

现在你已经会 SQLAlchemy 了，新建目录和文件：

```
E:\service-healthcheck\store\__init__.py    # 空的，或者一句注释
E:\service-healthcheck\store\db.py          # 数据库连接管理
E:\service-healthcheck\store\models.py      # 6 个模型类
```

### 3.1 store/db.py

这里要装的是：从环境变量读数据库连接串、建 engine、提供 session。

**提示：**
- `os.getenv("DATABASE_URL", "默认值")` 读环境变量
- `python-dotenv` 的 `load_dotenv()` 从 `.env` 加载
- `create_engine(pool_pre_ping=True)` 自动检测断连、重连
- `scoped_session` 是线程安全的会话工厂

**参考（不看先自己写）：**

```python
from dotenv import load_dotenv
load_dotenv()

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/smartops")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine))


def get_session():
    return SessionLocal()


def init_db():
    # 延迟导入，避免循环依赖
    from store.models import Base
    Base.metadata.create_all(bind=engine)
```

### 3.2 store/models.py

要定义 6 个模型类：

| 类名 | 表名 | 说明 |
|------|------|------|
| `Agent` | agents | 服务器：name, ip, os, last_heartbeat, status |
| `Metric` | metrics | 指标：agent_id, cpu, memory, disk, net_recv, net_sent |
| `Probe` | probes | 探活：agent_id, name, url, status, latency, diagnosis |
| `Log` | logs | 日志：agent_id, log_name, content, level |
| `Conversation` | conversations | 对话：agent_id, summary |
| `Message` | messages | 消息：conversation_id, role, content, tokens |

每个类继承 `declarative_base()` 返回的 `Base`。

**几个细节：**
- `agent_id` 设 `ForeignKey("agents.id")`
- `created_at` 用 `default=lambda: datetime.now(timezone.utc)`（有争议的话用 `datetime.utcnow` 也行，但带时区更规范）
- Log 的 `embedding` 列先不管（Phase 3 再加 pgvector）

**写完后验证：**

```powershell
# PowerShell: 先设环境变量
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python -c "from store.db import init_db; init_db(); print('OK')"
```

再用 psql 看表是否建成功了：
```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "\dt"
```

Expected:
```
              List of relations
 Schema |      Name      | Type  |  Owner
--------|----------------|-------|---------
 public | agents         | table | postgres
 public | conversations  | table | postgres
 public | logs           | table | postgres
 public | messages       | table | postgres
 public | metrics        | table | postgres
 public | probes         | table | postgres
```

**验收：** 看到 6 张表，而且 `\d agents` 能看到字段定义和字段类型。

---

## 学习阶段 4：写 Flask API

**目标：** 写一个 Flask 服务，接收数据写入 PostgreSQL。

新建 `E:\service-healthcheck\api.py`。

### 4.1 启动模板

先把骨架搭起来：

```python
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from store.db import init_db, get_session
from store.models import Agent, Metric, Probe, Log

app = Flask(__name__)

with app.app_context():
    init_db()

# 第一个路由：健康检查
@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
```

**启动验证：**
```powershell
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python api.py
```

浏览器打开 http://127.0.0.1:5001/api/health，看到 `{"status":"ok"}` 就行。

### 4.2 心跳路由 POST /api/heartbeat

这个端点做什么：Collector 定时发心跳，如果服务器没注册过就自动注册，已注册的更新最后心跳时间。

```python
@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json()
    name = data.get("server_name")
    # ... 查 agents 表，存在就更新，不存在就创建
    # ... 返回 {"status": "ok"}
```

**提示：**
- `request.get_json()` 取请求的 JSON body
- `session.query(Agent).filter_by(name=name).first()` 查是否存在
- 不存在：`Agent(name=name, ...)` → `session.add(agent)`
- 已存在：直接改字段
- `session.commit()` 提交
- `session.close()` 关连接（或用 try/finally）

### 4.3 指标上报 POST /api/metrics

```python
@app.route("/api/metrics", methods=["POST"])
def receive_metrics():
    data = request.get_json()
    name = data.get("server_name")
    # 查 agent → 不存在返回 404
    # 创建 Metric 对象，字段从 data 里取
    # 返回 {"status": "ok"}
```

### 4.4 日志上报 POST /api/logs

```python
@app.route("/api/logs", methods=["POST"])
def receive_logs():
    data = request.get_json()
    # data 结构: {"server_name": "...", "logs": [{"log_name": "...", "content": "...", "level": "..."}]}
    # 遍历 logs 列表，每个存一条记录
    # 返回数量和状态
```

### 4.5 测试

启动 API，用 Python requests 测试：

```powershell
# 终端1: API
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python api.py
```

```powershell
# 终端2: 测试心跳
.venv\Scripts\python -c "
import requests
r = requests.post('http://127.0.0.1:5001/api/heartbeat',
    json={'server_name': 'test-vps', 'os': 'Ubuntu 22.04'})
print(r.json())
"
```

```powershell
# 终端2: 测试指标上报
.venv\Scripts\python -c "
import requests
r = requests.post('http://127.0.0.1:5001/api/metrics',
    json={'server_name': 'test-vps', 'cpu': 55.3, 'memory': 70.1, 'disk': 45.0})
print(r.json())
"
```

**验收：** 两个都返回 `{"status": "ok"}`，psql 查 agents 表和 metrics 表有数据。

### 4.6 加自动化测试

新建 `E:\service-healthcheck\tests\__init__.py` 和 `tests\test_api.py`。

```python
import pytest
import os
os.environ["DATABASE_URL"] = "postgresql://postgres:你的密码@localhost:5432/smartops"

from api import app


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
```

**提示：**
- Flask 测试用 `app.test_client()`
- 用 `@pytest.fixture` 创建测试客户端
- 测试建个 fixture 在每个测试结束后清理数据（可选，因为测试数据也不多）
- 跑：`.venv\Scripts\python -m pytest tests/test_api.py -v`

**验收：** 至少 4 个测试全部 PASS（health、心跳注册、指标上报成功、不存在的 agent 返回 404）。

---

## 学习阶段 5：写 Collector

**目标：** 写一个采集器，定时采集系统指标并推送到 API。

### 5.1 Collector 配置

创建一个 `collector/` 目录，里面放：

- `collector.yml` — 采集器配置
- `collector.py` — 采集器主程序

**collector.yml：**
```yaml
server_name: kkivc-vps
api_url: http://127.0.0.1:5001
interval: 30
```

### 5.2 熟悉 psutil

先单独测一下，新建 `test_psutil.py`：

```python
import psutil

print("CPU:", psutil.cpu_percent(interval=1))
print("Memory:", psutil.virtual_memory().percent)
print("Disk:", psutil.disk_usage('/').percent)
print("Net:", psutil.net_io_counters().bytes_recv, psutil.net_io_counters().bytes_sent)
```

跑一下看看数值对不对。

### 5.3 写采集函数

在 `collector.py` 里实现一个函数，采集所有指标：

```python
def collect_metrics() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    # ... 继续
    return {
        "cpu": round(cpu, 1),
        "memory": round(mem.percent, 1),
        # ...
    }
```

### 5.4 写推送函数

```python
def send_metrics(config, metrics):
    url = f"{config['api_url']}/api/metrics"
    metrics["server_name"] = config["server_name"]
    
    for attempt in range(3):    # 失败重试 3 次
        try:
            resp = requests.post(url, json=metrics, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return False
```

### 5.5 主循环

```python
def main():
    config = yaml.safe_load(open("collector.yml"))
    
    # 先发一次心跳
    requests.post(f"{config['api_url']}/api/heartbeat", json={"server_name": config["server_name"]})
    
    while True:
        metrics = collect_metrics()
        send_metrics(config, metrics)
        time.sleep(config["interval"])
```

### 5.6 端到端跑通

```powershell
# 终端1: API
$env:DATABASE_URL="postgresql://postgres:你的密码@localhost:5432/smartops"
.venv\Scripts\python api.py
```

```powershell
# 终端2: Collector
cd collector
..\.venv\Scripts\python collector.py
```

等 30 秒后验证：
```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d smartops -c "SELECT cpu, memory, disk, created_at FROM metrics ORDER BY id DESC LIMIT 5;"
```

**验收：** 每 30s 一条新的指标记录，CPU/内存/磁盘都有数据。

---

## 总结

学完 Phase 1 后你掌握了：

1. ✅ **PostgreSQL** — 安装、建库建表、psql 基本操作
2. ✅ **SQLAlchemy** — ORM 模型定义、自动建表
3. ✅ **Flask + PostgreSQL** — REST API 读写 PG
4. ✅ **psutil** — Python 采集系统指标
5. ✅ **多层架构** — 数据从 Collector → API → DB 单向流动

**Phase 2（后续）学什么：** Streamlit 面板展示数据、实时图表、服务器卡片。

---

> "最快的成长方式不是做简单的事，而是做稍微超出能力的事。"  
> 这些代码都是你写得出来的——卡住的时候，告诉我卡在哪步，我给方向。
