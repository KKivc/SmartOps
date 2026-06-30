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
from store.models import Alert
from store.crypto import password_decrypt

LOKI_URL = "http://localhost:3100/loki/api/v1/push"

def load_server():
    """读取 数据库 服务器配置"""
    data = []
    session = get_session()
    servers = session.query(Server).all()
    for s in servers:
        data.append({
            'name': s.name,
            'host': s.ip,
            'port': '22',
            'user': s.user,
            'password': password_decrypt(s.password)
        })
    return data
    
def push_loki(server_name, level, log_line):
    """推送单条日志到 Loki"""
    payload = {
        "streams": [{
            "stream": {
                "server": server_name,
                "level": level
            },
            "values": [[
                str(int(time.time() * 1e9)),    #当前时间的纳秒数——Loki 要求纳秒级别的时间戳
                log_line
            ]]
        }]
    }
    try:
        requests.post(LOKI_URL, json=payload, timeout=5)
    except Exception as e:
        print(f" [Loki 推送失败] {e}")

def parse_level(line):
    """从日志行猜级别"""
    line_upper = line.upper()
    if "ERROR" in line_upper or "FATAL" in line_upper:
        return "error"
    elif "WARN" in line_upper:
        return "warn"
    elif "INFO" in line_upper:
        return "info"
    return "info"

def collect_all():
    """一轮采集，遍历所有服务器"""
    configs = load_server()
    session = get_session()

    for cfg in configs:
        name = cfg["name"]
        print(f"\n[{name}] 开始采集...")

        try:
            # ssh连接
            client = SSHClient(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg.get("password"),
                key_path=cfg.get("key")
            )

            # 采集指标
            cpu=client.get_cpu()
            mem = client.get_memory()
            disk = client.get_disk()
            print(f"CPU={cpu}%  内存={mem}%  磁盘={disk}%")

            # 获取系统信息
            os_info = client.exec("cat /etc/os-release | grep '^PRETTY_NAME' | cut -d'=' -f2 | tr -d '\"'")
            if not os_info:
                os_info = client.exec("uname -o")

            # 确认服务器在数据库存在,不存在则添加
            server = session.query(Server).filter_by(name=name).first()
            if not server:
                server = Server(name=name, ip=cfg['host'], status='online', os=os_info)
                session.add(server)
                session.flush()

            # 写入指标--> postgresql
            metric = Metric(server_id=server.id, cpu=cpu, memory=mem, disk=disk)
            session.add(metric)

            # 更新服务器状态
            server.last_heartbeat = datetime.now(timezone.utc)
            server.status = "online"
            if not server.os:
                server.os = os_info

            # 采集日志
            logs = client.get_logs("/var/log/syslog", limit=20)
            for line in logs:
                if line.strip():
                    log = Log(server_id=server.id, log_name='syslog',
                              content=line, level=parse_level(line))
                    session.add(log)
                    push_loki(name, parse_level(line), line)

            client.close()

            # 告警检查
            thresholds = {'cpu': 80, 'memory': 80, 'disk': 80}
            for key, val in [('cpu', cpu), ('memory', mem), ('disk', disk)]:
                if val is not None and val > thresholds[key]:
                    alert = Alert(server_name=name, type=key, message=f'{key.upper()} 使用率 {val}%',
                                  value=val, status='open')
                    session.add(alert)

        # 采集失败
        except Exception as e:
            print(f"  [错误] {name} 采集失败: {e}")
            server = session.query(Server).filter_by(name=name).first()
            if server:
                server.status = 'offline'
                alert = Alert(server_name=name, type='offline', message=f'服务器离线',
                              value=0, status='open')
                session.add(alert)

    session.commit()
    session.close()

def start_scheduler(interval=60):
    """启动后台调度线程"""
    def loop():
        print(f"🔄 采集调度器已启动，每 {interval} 秒一轮")
        while True:
            collect_all()
            time.sleep(interval)

    """
    创建一个新线程，独立于主线程运行
    target=loop — 线程要执行的函数
    daemon=True — 守护线程：主程序退出时，这个线程自动结束。如果不设，关了面板采集器还卡着不退。
    """
    t = threading.Thread(target=loop, daemon=True)  
    t.start()      #启动线程
    return t