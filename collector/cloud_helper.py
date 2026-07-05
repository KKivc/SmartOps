"""
云服务器助手 — 自动更新 Prometheus 抓取目标

当添加/删除服务器时，SSH 到云服务器更新 prometheus.yml 并热加载。
如果未配置 CLOUD_SSH_* 环境变量，自动跳过并提示用户手动配置。
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

# 判断是否有云服务器 SSH 配置
def _cloud_ssh_configured() -> bool:
    return bool(os.getenv("CLOUD_SSH_HOST") and os.getenv("CLOUD_SSH_USER"))


def update_prometheus_targets(servers: list[dict]) -> bool:
    """更新云服务器上的 Prometheus 抓取目标。

    Args:
        servers: [{name, ip, status}] 列表

    Returns:
        True 如果更新成功, False 如果跳过或失败
    """
    # 只取在线且有 IP 的服务器
    targets = []
    for s in servers:
        ip = s.get("ip", "").strip()
        if ip and s.get("status") == "online":
            targets.append(f"{ip}:9100")

    if not _cloud_ssh_configured():
        logger.warning("CLOUD_SSH_HOST/USER 未配置，无法自动更新 Prometheus。")
        logger.warning("如需自动配置，添加环境变量：")
        logger.warning("  CLOUD_SSH_HOST=<云服务器IP>")
        logger.warning("  CLOUD_SSH_USER=<SSH用户名>")
        logger.warning("  CLOUD_SSH_PASSWORD=<密码> 或 CLOUD_SSH_KEY_PATH=<密钥路径>")
        return False

    # 生成 prometheus target 配置
    target_lines = ""
    for t in targets:
        target_lines += f"        - '{t}'\n"

    prometheus_config = f"""global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "node"
    static_configs:
      - targets:
{target_lines}
"""

    try:
        # SSH 到云服务器更新 prometheus.yml
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
            logger.warning("CLOUD_SSH_PASSWORD 或 CLOUD_SSH_KEY_PATH 均未设置")
            return False

        ssh.connect(**connect_kwargs)
        logger.info(f"✅ SSH 连接到 {os.getenv('CLOUD_SSH_HOST')} 成功")

        # 云服务器上 SmartOps 基础设施目录（docker-compose.yml 所在目录）
        cloud_path = os.getenv("CLOUD_INFRA_DIR", "/root/smartops-infra")
        ssh.exec_command(f"mkdir -p {cloud_path}")

        # 写入 prometheus.yml
        sftp = ssh.open_sftp()
        remote_file = f"{cloud_path}/prometheus.yml"
        logger.info(f"📝 写入 {remote_file}")
        with sftp.open(remote_file, "w") as f:
            f.write(prometheus_config)
        sftp.close()

        # 重启 Prometheus 容器
        logger.info("🔄 重启 Prometheus...")
        stdin, stdout, stderr = ssh.exec_command(
            f"docker compose -f {cloud_path}/docker-compose.yml restart prometheus"
        )
        exit_code = stdout.channel.recv_exit_status()
        ssh.close()

        if exit_code == 0:
            logger.info(f"✅ Prometheus 配置已更新，目标: {targets}")
            return True
        else:
            err = stderr.read().decode().strip()
            logger.error(f"Prometheus 重启失败: {err}")
            return False

    except paramiko.SSHException as e:
        logger.error(f"SSH 连接失败: {e}")
        return False
    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e} — 请检查 CLOUD_INFRA_DIR 路径是否正确")
        return False
    except Exception as e:
        logger.error(f"云服务器 SSH 更新失败: {type(e).__name__}: {e}")
        return False
