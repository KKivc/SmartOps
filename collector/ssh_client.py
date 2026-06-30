"""
SSH 客户端封装 — 用 paramiko 远程执行命令采集系统指标
"""
import paramiko


class SSHClient:
    """通过 SSH 连接远程服务器，执行 shell 命令采集系统数据"""

    def __init__(self, host, port, user, key_path=None, password=None):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_args = {
            "hostname": host,
            "port": port,
            "username": user,
        }
        # 密码或密钥，二选一
        if password:
            connect_args["password"] = password
        elif key_path:
            connect_args["key_filename"] = key_path
        else:
            raise ValueError("必须提供 password 或 key_path 之一")

        self.ssh.connect(**connect_args)

    def exec(self, command):
        """执行一条 shell 命令，返回 stdout 文本"""
        _, stdout, stderr = self.ssh.exec_command(command)
        err = stderr.read().decode().strip()
        if err:
            raise RuntimeError(f"SSH 命令错误: {err}")
        return stdout.read().decode().strip()

    def get_cpu(self):
        """CPU 使用率（百分比）"""
        result = self.exec(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'"
        )
        return round(float(result), 1)

    def get_memory(self):
        """内存使用率（百分比）"""
        result = self.exec(
            "free | grep Mem | awk '{print $3/$2 * 100}'"
        )
        return round(float(result), 1)

    def get_disk(self):
        """磁盘使用率（百分比）"""
        result = self.exec(
            "df -h / | tail -1 | awk '{print $5}' | tr -d '%'"
        )
        return float(result)

    def get_logs(self, log_path, limit=50):
        """读取日志最新 N 行"""
        result = self.exec(f"tail -n {limit} {log_path}")
        return result.splitlines() if result else []

    def close(self):
        self.ssh.close()
