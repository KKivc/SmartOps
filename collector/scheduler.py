"""
采集调度器 — 精简版，仅保留心跳检测 + 离线告警

指标采集 → Prometheus + node_exporter
日志采集 → promtail → Loki
"""

import time
import threading
from datetime import datetime, timezone

from store.db import get_session
from store.models import Alert, Server
from collector.ssh_client import SSHClient


def load_servers() -> list[dict]:
    """从数据库加载服务器列表"""
    data = []
    session = get_session()
    for s in session.query(Server).all():
        data.append({
            "name": s.name,
            "host": s.ip,
            "port": "22",
            "user": s.user,
        })
    session.close()
    return data


def heartbeat_all():
    """一轮心跳检测，遍历所有服务器"""
    configs = load_servers()
    session = get_session()

    for cfg in configs:
        name = cfg["name"]
        online = False

        try:
            client = SSHClient(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
            )
            # 轻量心跳：执行 uptime 检测连通性
            client.exec("uptime")
            client.close()
            online = True
        except Exception as e:
            print(f"  [{name}] 心跳失败: {e}")
            online = False

        server = session.query(Server).filter_by(name=name).first()
        if not server:
            print(f"  [{name}] 数据库不存在，跳过")
            continue

        if online:
            server.last_heartbeat = datetime.now(timezone.utc)
            server.status = "online"
        else:
            server.status = "offline"
            # 避免重复告警：检查是否已有未关闭的离线告警
            existing = session.query(Alert).filter(
                Alert.server_name == name,
                Alert.type == "offline",
                Alert.status == "open",
            ).first()
            if not existing:
                alert = Alert(
                    server_name=name,
                    type="offline",
                    message=f"服务器离线",
                    value=0,
                    status="open",
                )
                session.add(alert)

    session.commit()
    session.close()


def start_scheduler(interval: int = 60):
    """启动后台心跳调度线程"""
    def loop():
        print(f"❤️  心跳调度器已启动，每 {interval} 秒检测一轮")
        while True:
            heartbeat_all()
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
