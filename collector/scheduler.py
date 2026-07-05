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
from store.crypto import password_decrypt


def load_servers() -> list[dict]:
    """从数据库加载服务器列表，解密密码"""
    data = []
    session = get_session()
    for s in session.query(Server).all():
        pwd = None
        try:
            if s.password:
                pwd = password_decrypt(s.password)
        except Exception as e:
            print(f"  [{s.name}] 密码解密失败: {e}")
        data.append({
            "name": s.name,
            "host": s.ip,
            "port": 22,
            "user": s.user,
            "password": pwd,
        })
    session.close()
    return data


def heartbeat_all():
    """一轮心跳检测，遍历所有服务器"""
    configs = load_servers()
    session = get_session()

    for cfg in configs:
        name = cfg["name"]
        server = session.query(Server).filter_by(name=name).first()
        if not server:
            print(f"  [{name}] 数据库不存在，跳过")
            continue

        was_offline = (server.status == "offline")

        try:
            client = SSHClient(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg.get("password"),
            )
            uptime = client.exec("echo ok")
            client.close()

            server.last_heartbeat = datetime.now(timezone.utc)
            server.status = "online"
            print(f"[{name}] 心跳正常: {uptime}")

            # 自动恢复：如果之前是离线，关闭 open 的离线告警
            if was_offline:
                existing = session.query(Alert).filter(
                    Alert.server_name == name,
                    Alert.type == 'offline',
                    Alert.status == 'open'
                ).all()
                for alert in existing:
                    alert.status = "resolved"
                if existing:
                    print(f"[{name}] 服务器恢复在线，自动解决 {len(existing)} 条离线告警")

        except Exception as e:
            print(f"[{name}] 心跳失败: {e}")
            if server.status == "online":
                server.status = "offline"
                existing = session.query(Alert).filter(
                    Alert.server_name == name,
                    Alert.type == 'offline',
                    Alert.status == 'open'
                ).first()
                if not existing:
                    alert = Alert(
                        server_name=name,
                        type="offline",
                        message="服务器离线",
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
