# SmartOps Phase 3 — 教学稿 阶段 2

> 目标：自动每 60 秒采集服务器数据（指标→PostgreSQL，日志→Loki）

---

## 阶段 2A：安装 Docker Desktop

Loki 需要 Docker 来跑。我们先装 Docker Desktop。

### 为什么用 Docker？

不然你要在 Windows 上手动下载 Loki 二进制、管理进程、开机自启……很麻烦。

Docker 一键搞定：

```yaml
# docker-compose.yml 写好后，一行命令启动
docker compose up -d
```

---

### ① 下载 Docker Desktop

打开浏览器，去官网下载：

👉 https://www.docker.com/products/docker-desktop/

点 **Download for Windows**（下载 Windows 版）

> 如果官网慢，可以用国内镜像：https://mirrors.aliyun.com/docker-toolbox/windows/docker-for-windows/beta/

### ② 安装

下载完双击安装程序，一路默认下一步就行。

关键点：

| 步骤 | 说明 |
|------|------|
| 安装类型 | 选 **WSL 2 based engine**（默认就是） |
| 额外组件 | 勾上 "Add shortcut to desktop" |
| 安装位置 | 默认 C 盘即可 |

安装完后会自动重启（或要求你重启）。

### ③ 启动 Docker Desktop

重启后，桌面上会有 Docker 图标。双击打开。

第一次启动要等几分钟（它在初始化 WSL2 引擎）。右下角鲸鱼图标转圈 → 变稳定就说明好了。

**确认安装成功：**

```powershell
docker --version
docker compose version
```

看到版本号就 OK。

### ④ 配置 WSL2 集成（重要）

Docker Desktop → Settings → Resources → WSL Integration：

确保你的 **Ubuntu** 开关是打开的（绿色）。

> 这一步让 Docker 能跟 WSL 的 Ubuntu 配合使用。

---

## 阶段 2B：Loki 日志系统

### ① 先理解 Loki 干什么

Loki 是一个**日志服务器**。它做两件事：

```
接收日志：  你的代码 → HTTP POST → Loki（存起来）
查询日志：  你的代码 → HTTP GET  → Loki（搜出来）
```

就像你平时查日志用 `grep` 搜文件，Loki 就是网络版的 `grep`，而且可以按服务器/时间/关键字过滤。

### ② 创建 docker-compose.yml

项目根目录新建 `docker-compose.yml`：

```yaml
services:
  loki:
    image: grafana/loki:3.0.0
    ports:
      - "3100:3100"           # Loki 的 HTTP API 端口
    volumes:
      - loki-data:/loki       # 日志数据持久化

volumes:
  loki-data:
```

### ③ 启动 Loki

```powershell
docker compose up -d
```

`-d` 表示后台运行（detach）。

确认 Loki 在运行：

```powershell
docker compose ps
```

应该看到 loki 的状态是 `Up`。

### ④ 验证 Loki 能收数据

向 Loki 推一条测试日志：

```powershell
curl -s -X POST http://localhost:3100/loki/api/v1/push ^
  -H "Content-Type: application/json" ^
  -d "{\"streams\": [{\"stream\": {\"server\": \"test\", \"level\": \"info\"}, \"values\": [[\"$(Get-Date -UFormat %s)000000000\", \"这是一条测试日志\"]]}]}"
```

查回来看看：

```powershell
curl -s "http://localhost:3100/loki/api/v1/query_range?query={server=\"test\"}" | python -m json.tool
```

看到有结果就说明 Loki 跑通了。

---

## 阶段 2C：SSH 调度器

### ① 先理解我们要写什么

现在你手动 `python test_ssh.py` 才跑一次采集。但 SmartOps 要**自动每 60 秒循环采集**。

调度器做的事情：

```
┌─ 每 60 秒 ──────────────────────────────────┐
│                                               │
│  1. 读 config/servers.yml（服务器列表）        │
│  2. 对每台服务器：                            │
│     ├─ SSH 连上去                             │
│     ├─ get_cpu/memory/disk → 写入 PostgreSQL  │
│     ├─ get_logs → 推送到 Loki                │
│     └─ 更新服务器状态为 online                │
│  3. 等待 60 秒，重复                          │
│                                               │
└───────────────────────────────────────────────┘
```

### ② 写调度器代码

新建 `collector/scheduler.py`：

```python
"""
采集调度器 — 每 60 秒自动 SSH 采集并写入 PostgreSQL + Loki
"""
import time
import yaml
import threading
import requests
from datetime import datetime, timezone
from store.db import get_session
from store.models import Server, Metric, Log
from collector.ssh_client import SSHClient

# Loki 地址（本机 Docker 跑的）
LOKI_URL = "http://localhost:3100/loki/api/v1/push"


def load_servers():
    """读取 YAML 服务器配置"""
    with open("config/servers.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)["servers"]


def push_log_to_loki(server_name, level, log_line):
    """推送单条日志到 Loki"""
    import json
    import time as _time

    payload = {
        "streams": [{
            "stream": {
                "server": server_name,
                "level": level
            },
            "values": [[
                str(int(_time.time() * 1e9)),
                log_line
            ]]
        }]
    }
    try:
        requests.post(LOKI_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"  [Loki 推送失败] {e}")


def collect_all():
    """一轮采集：遍历所有服务器"""
    configs = load_servers()
    session = get_session()

    for cfg in configs:
        name = cfg["name"]
        print(f"\n[{name}] 开始采集...")

        try:
            # SSH 连接
            client = SSHClient(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg.get("password"),
                key_path=cfg.get("key")
            )

            # 采集指标
            cpu = client.get_cpu()
            mem = client.get_memory()
            disk = client.get_disk()
            print(f"  CPU={cpu}%  内存={mem}%  磁盘={disk}%")

            # 确认服务器在数据库里存在
            server = session.query(Server).filter_by(name=name).first()
            if not server:
                server = Server(name=name, ip=cfg["host"], status="online")
                session.add(server)
                session.flush()  # 拿到 server.id

            # 写入指标到 PostgreSQL
            metric = Metric(
                server_id=server.id,
                cpu=cpu,
                memory=mem,
                disk=disk
            )
            session.add(metric)

            # 更新服务器心跳状态
            server.last_heartbeat = datetime.now(timezone.utc)
            server.status = "online"

            # 采集日志（取最近 20 行）
            logs = client.get_logs("/var/log/syslog", limit=20)
            for line in logs:
                if line.strip():
                    # 写入 PostgreSQL
                    log = Log(
                        server_id=server.id,
                        log_name="syslog",
                        content=line,
                        level=parse_log_level(line)
                    )
                    session.add(log)

                    # 推送 Loki
                    push_log_to_loki(name, parse_log_level(line), line)

            client.close()

        except Exception as e:
            print(f"  [错误] {name} 采集失败: {e}")
            # 标记离线
            server = session.query(Server).filter_by(name=name).first()
            if server:
                server.status = "offline"

    session.commit()
    session.close()


def parse_log_level(line):
    """从日志行中猜级别"""
    line_upper = line.upper()
    if "ERROR" in line_upper or "FATAL" in line_upper:
        return "error"
    elif "WARN" in line_upper:
        return "warn"
    elif "INFO" in line_upper:
        return "info"
    return "info"


def start_scheduler(interval=60):
    """启动后台调度线程（daemon 模式，随主程序退出）"""
    def loop():
        print(f"🔄 采集调度器已启动，每 {interval} 秒一轮")
        while True:
            collect_all()
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
```

### ③ 看懂这段代码

**`load_servers()`** — 从 YAML 文件读服务器列表。跟 `test_ssh.py` 一样。

**`collect_all()`** — 核心函数。遍历每台服务器，依次：
1. SSH 连接
2. 拿 CPU/内存/磁盘
3. 写入 PostgreSQL 的 Metric 表
4. 更新 Server 表的在线状态
5. 拿日志，写入 PostgreSQL 的 Log 表 + 推 Loki
6. 出错则标记服务器 offline

**`push_log_to_loki()`** — 把一行日志推给 Loki。Loki 的格式有点特别，它要求传纳秒时间戳和标签（server、level）。

**`start_scheduler()`** — 启动一个后台线程（`daemon=True`），永远不停止地每 60 秒跑一次。

**`daemon=True` 是什么意思？**
- 普通线程：主程序退出后，它还在跑，卡住不退
- daemon 线程：主程序退出时，它自动被干掉
- 刚好符合需求：Flask 退出 → 采集器跟着停

### ④ 在 Flask 启动时自动拉起

修改 `api.py`，在文件末尾（`if __name__ == '__main__':` 之前）加入：

```python
from collector.scheduler import start_scheduler

# 启动后台采集线程（每 60 秒一轮）
start_scheduler(interval=60)
```

这样当你 `python api.py` 启动面板时，采集器自动在后台跑，不需要手动运行。

---

## 阶段 2 验收清单

- [ ] Docker Desktop 安装成功（`docker --version` 有输出）
- [ ] `docker compose up -d` Loki 启动成功
- [ ] 向 Loki 推测试日志，能查回来
- [ ] 调度器代码写好了
- [ ] `python api.py` 启动后，终端每 60 秒打印采集信息
- [ ] PostgreSQL 里有指标数据（查询 Metric 表）
- [ ] Loki 里有日志数据（查询日志）

---

## 这节课你学到了

| 概念 | 一句话 |
|------|--------|
| Docker | 一种"一键跑服务的工具"，不用手动装各种依赖 |
| docker-compose | 用 yaml 文件描述要跑哪些服务 |
| Loki | 日志服务器，收日志 + 搜日志 |
| 调度器 | 后台循环线程，定时干活 |
| daemon 线程 | 主程序退出时自动结束的线程 |
