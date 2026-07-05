"""
云服务器助手 — SSH 更新 Prometheus file_sd targets

当添加/删除服务器时，SSH 到云服务器写入 targets JSON，
配合 Prometheus 的 file_sd_configs 自动发现新目标。
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

TARGETS_DIR = os.getenv("CLOUD_PROMETHEUS_TARGETS_DIR", "/etc/prometheus/targets")


def _cloud_ssh_configured() -> bool:
    return bool(os.getenv("CLOUD_SSH_HOST") and os.getenv("CLOUD_SSH_USER"))


def update_prometheus_targets(servers: list[dict]) -> bool:
    """SSH 到云服务器，更新 Prometheus file_sd targets JSON"""
    targets = []
    for s in servers:
        ip = s.get("ip", "").strip()
        if ip and s.get("status") == "online":
            targets.append({
                "targets": [f"{ip}:9100"],
                "labels": {"server": s.name},
            })

    if not _cloud_ssh_configured():
        return False

    try:
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": os.getenv("CLOUD_SSH_HOST"),
            "username": os.getenv("CLOUD_SSH_USER"),
            "port": int(os.getenv("CLOUD_SSH_PORT", "22")),
        }
        pwd = os.getenv("CLOUD_SSH_PASSWORD")
        key = os.getenv("CLOUD_SSH_KEY_PATH")
        if pwd:
            connect_kwargs["password"] = pwd
            connect_kwargs["look_for_keys"] = False
            connect_kwargs["allow_agent"] = False
        elif key:
            connect_kwargs["key_filename"] = key
        else:
            return False

        ssh.connect(**connect_kwargs)

        # 创建 targets 目录，写入 JSON
        ssh.exec_command(f"mkdir -p {TARGETS_DIR}")
        sftp = ssh.open_sftp()
        remote_file = f"{TARGETS_DIR}/smartops-nodes.json"
        with sftp.open(remote_file, "w") as f:
            f.write(json.dumps(targets, indent=2, ensure_ascii=False))
        sftp.close()
        ssh.close()

        logger.info(f"✅ 已写入 {remote_file} ({len(targets)} 个目标)")
        return True
    except Exception as e:
        logger.error(f"云服务器更新失败: {e}")
        return False
