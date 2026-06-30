# SmartOps Phase 3 — 教学稿

> 目标：把面板做成能 SSH 自动采集 + AI 对话排错 + 知识库 RAG 的运维系统

---

## 阶段 1：SSH 客户端 — 远程连接服务器取数据

---

### 🎯 这个阶段我们要做什么？

SmartOps 要管多台 Linux 服务器，需要知道它们的 CPU、内存、磁盘、日志。

但我们**不想在每台服务器上装软件**——太麻烦。

方案是：**面板主动 SSH 连过去，发命令，拿结果。**

```
你本机（跑 SmartOps）──SSH──→ Linux 服务器
                           │
                           ├─ top       → CPU
                           ├─ free      → 内存
                           ├─ df -h /   → 磁盘
                           └─ tail      → 日志
```

这个阶段我们就写一个 **Python 的 SSH 工具箱**。后面所有阶段都靠它。

---

### 📦 第一步：认识 paramiko

paramiko 是 Python 的 SSH 库。它帮你做这件事：

```
你手动 SSH 登录：    ssh root@1.2.3.4 -p 22
                         然后敲命令： top
                         看结果：    CPU: 12.5%

Python 用 paramiko： client.exec("top")  → 拿到 "CPU: 12.5%"
```

paramiko 已经装好了，不用你管。

---

### 📝 第二步：看代码——SSH 客户端

文件 `collector/ssh_client.py` 我已经写好了。你打开它，我一行行解释。

#### 开头——建立连接

```python
import paramiko

class SSHClient:
    def __init__(self, host, port, user, key_path=None, password=None):
```

这个类叫 `SSHClient`，翻译：**SSH 客户端**。

初始化时你要告诉它四个信息：
- `host` — 服务器 IP
- `port` — SSH 端口（默认 22）
- `user` — 登录用户名（一般 root）
- `password` 或 `key_path` — 密码或密钥文件，二选一

接下来三行是关键：

```python
        self.ssh = paramiko.SSHClient()
        # 创建一个 SSH 客户端对象
        # 相当于打开终端，准备敲 ssh 命令

        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # 设置"自动接受陌生服务器"
        # 平时你第一次连一台服务器，终端会问：
        #   "这个服务器的指纹没见过，确认连接吗？(yes/no)"
        # 这一行就是自动回答 yes

        self.ssh.connect(
            hostname=host,
            port=port,
            username=user,
            password=password  # 或 key_filename=key_path
        )
        # 真正发起 SSH 连接
        # 相当于你敲了： ssh root@1.2.3.4 -p 22
```

#### 核心方法——执行命令

```python
    def exec(self, command):
        """执行一条 shell 命令，返回文本结果"""
        _, stdout, stderr = self.ssh.exec_command(command)
        err = stderr.read().decode().strip()
        if err:
            raise RuntimeError(f"SSH 命令错误: {err}")
        return stdout.read().decode().strip()
```

`exec_command` 是 paramiko 提供的方法。它返回三个东西：
- `stdin` — 标准输入（我们不用，所以用 `_` 忽略）
- `stdout` — 命令的正常输出
- `stderr` — 命令的错误输出

我们拿 `stdout` 的内容，转成文本（`.decode()`），去掉首尾空格（`.strip()`）。

#### 四个采集方法

```python
    def get_cpu(self):
        """CPU 使用率"""
        result = self.exec("top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'")
        return round(float(result), 1)
```

这条命令拆开看：

| 部分 | 说明 |
|------|------|
| `top -bn1` | 跑一次 top，不循环，立即退出 |
| `grep 'Cpu(s)'` | 只保留包含 "Cpu(s)" 的那一行 |
| `awk '{print $2+$4}'` | 提取第 2 列（user）和第 4 列（system），加起来 |

在服务器上手动跑一下看看：

```bash
ssh root@你的IP "top -bn1 | grep 'Cpu(s)'"
```

你会看到类似：`%Cpu(s): 12.5 us,  3.2 sy,  0.0 ni, 84.3 id, ...`

第 2 列是用户态 CPU（12.5），第 4 列是系统态 CPU（3.2），加起来 = **15.7%**，就是 CPU 总使用率。

---

```python
    def get_memory(self):
        """内存使用率"""
        result = self.exec("free | grep Mem | awk '{print $3/$2 * 100}'")
        return round(float(result), 1)
```

`free` 命令输出内存信息：
```
              total        used        free
Mem:        8000000     3000000     5000000
```

`awk '{print $3/$2 * 100}'` 就是 `3000000 / 8000000 * 100 = 37.5%`。

---

```python
    def get_disk(self):
        """磁盘使用率"""
        result = self.exec("df -h / | tail -1 | awk '{print $5}' | tr -d '%'")
        return float(result)
```

`df -h /` 查看根分区磁盘使用率，第 5 列是百分比，`tr -d '%'` 去掉百分号。

---

```python
    def get_logs(self, log_path, limit=50):
        """读取日志最新 N 行"""
        result = self.exec(f"tail -n {limit} {log_path}")
        return result.splitlines() if result else []
```

`tail -n 50 /var/log/syslog` — 看日志文件最后 50 行。

---

### 🔧 第三步：配置服务器

打开 `config/servers.yml`。这是一个 YAML 格式的配置文件（类似 JSON，但更简洁）。

当前内容：

```yaml
servers:
  - name: kkivc-vps
    host: 你的服务器IP     # 改成你的真实 IP
    port: 22
    user: root
    password: "你的密码"   # 改成你的 SSH 密码
```

**你做：** 把 `host` 和 `password` 改成你的真实信息。

> ⚠️ 注意：密码用了引号包裹，以防密码里有特殊字符。

---

### 🧪 第四步：写测试脚本

新建文件 `test_ssh.py`，内容如下：

```python
# test_ssh.py — 测试 SSH 连接和数据采集
from collector.ssh_client import SSHClient
import yaml

# 1. 读取 YAML 配置文件
with open("config/servers.yml") as f:
    config = yaml.safe_load(f)

# 2. 遍历每台服务器，依次连接采集
for s in config["servers"]:
    print(f"\n=== 连接 {s['name']} ({s['host']}) ===")
    
    # 创建 SSH 客户端 → 相当于 ssh root@IP
    client = SSHClient(
        host=s["host"],
        port=s["port"],
        user=s["user"],
        password=s["password"]
    )
    
    # 执行三条采集命令
    cpu = client.get_cpu()        # CPU 使用率
    mem = client.get_memory()      # 内存使用率
    disk = client.get_disk()       # 磁盘使用率
    
    # 打印结果
    print(f"CPU:  {cpu}%")
    print(f"内存: {mem}%")
    print(f"磁盘: {disk}%")
    
    # 断开连接
    client.close()

print("\n✅ 完成！")
```

**你做：** 把这段代码保存到 `test_ssh.py`。

---

### ▶️ 第五步：运行测试

```bash
python test_ssh.py
```

如果一切正常，你会看到：

```
=== 连接 kkivc-vps (1.2.3.4) ===
CPU:  12.5%
内存: 45.2%
磁盘: 68.0%

✅ 完成！
```

---

### ❓ 可能遇到的问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `Connection refused` | 服务器没开 SSH，或 IP/端口错了 | 检查服务器 SSH 服务是否启动 |
| `Authentication failed` | 用户名或密码错了 | 检查 `user` 和 `password` |
| `timed out` | 网络不通 | ping 一下服务器能通吗？ |
| 中文乱码 | 服务器返回了非英文字符 | 不影响，后面会处理 |

---

### ✅ 验收清单

- [ ] `config/servers.yml` 填好了真实 IP 和密码
- [ ] `test_ssh.py` 创建并保存好了
- [ ] `python test_ssh.py` 成功输出了 CPU/内存/磁盘
- [ ] 理解了 `paramiko.SSHClient()` 在做什么
- [ ] 理解了 `get_cpu()` 那条 Linux 命令是什么意思

---

### 📐 这节课你学到了

| 概念 | 一句话 |
|------|--------|
| SSH | 远程登录 Linux 服务器的协议 |
| paramiko | Python 里用来做 SSH 连接的库 |
| SSHClient | 一个类，封装了 SSH 连接和命令执行 |
| exec() | 在远程服务器上跑一条命令，拿回结果 |
| get_cpu/memory/disk | 用 Linux 命令采集系统指标 |

---

**你就做：**
1. 打开 `config/servers.yml` 填 IP 密码 ✅
2. 新建 `test_ssh.py` 贴代码 ✅
3. 跑 `python test_ssh.py` ✅

做完告诉我结果。
