---
name: package
description: "Clean and package SmartOps for distribution. Removes __pycache__, .venv, build artifacts, data caches, IDE files, stale logs; sanitizes secrets in .env/config. Then builds Docker image, pushes to cloud server, and restarts service stack. Use when user says '打包', '部署', 'package', 'deploy', 'docker', 'clean project', '清理项目', '清理缓存', 'clean up', '上线', 'build image', 'prepare for distribution', or wants to deliver a clean copy of the code or deploy to production."
---

# SmartOps Package — 清理打包与部署

> **⚠️ 每次执行 `python`/`pytest` 命令前必须先激活 `.venv`**
> - Windows: `.\.venv\Scripts\Activate.ps1`
> - macOS/Linux: `source .venv/bin/activate`

## Pipeline

```
Dry-run → Confirm → Clean → Build → Deploy → Verify
```

---

## Phase 1：Dry Run

展示将要清理的内容，不实际删除：

```powershell
python .github/skills/package/scripts/clean.py
```

输出示例：
```
📁 __pycache__/ — 12 directories (3.2 MB)
📁 .pytest_cache/ — 1 directory (0.1 MB)
📁 data/chromadb/ — 50+ files (120 MB) [--keep-data to preserve]
🔐 .env — contains API keys (sanitize only)
```

---

## Phase 2：确认

向用户展示待删除摘要，提供选项：

| 选项 | 效果 |
|------|------|
| 直接回车 / `--execute` | 全量清理 |
| `--keep-data` | 保留 `data/chromadb/` 等数据目录 |
| `--no-sanitize` | 跳过 .env 密钥替换 |

**等待用户确认后再执行。**

---

## Phase 3：执行清理

```powershell
# 默认（全量清理 + 密钥脱敏）
python .github/skills/package/scripts/clean.py --execute

# 保留数据
python .github/skills/package/scripts/clean.py --execute --keep-data
```

### 清理范围

| 类别 | 内容 |
|------|------|
| Python 缓存 | `__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/` |
| 虚拟环境 | `.venv/` |
| 数据目录 | `data/chromadb/`, `data/eval/`（`--keep-data` 跳过） |
| IDE 文件 | `.vscode/`, `*.swp` |
| 日志 | `logs/`, `__pycache__/` |
| 密钥脱敏 | `.env` 中的 API Key → `YOUR_KEY_HERE` |
| 测试脚本 | `test.py`（可选） |

### 验证清理结果

```powershell
# 检查无 __pycache__ 残留
python -c "import pathlib; p=list(pathlib.Path('.').rglob('__pycache__')); print(f'{len(p)} 个残留') if p else print('✅ 干净')"

# 检查 .venv 已删除
python -c "import pathlib; print('.venv 仍存在') if pathlib.Path('.venv').exists() else print('✅ 已清理')"
```

---

## Phase 4：构建 Docker 镜像

```powershell
# 检查 Dockerfile 是否存在，不存在则创建
if (-not (Test-Path Dockerfile)) {
    @"
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["python", "api.py"]
"@ | Set-Content Dockerfile
}

# 构建
docker build -t smartops:latest -f Dockerfile .
```

**验证：** `docker images smartops:latest` — 显示大小和创建时间

---

## Phase 5：推送与部署（云服务器）

### 5.1 读取配置

从 `.env` 读取（若无，提示用户输入）：
- `CLOUD_HOST` — 云服务器 IP
- `CLOUD_USER` — SSH 用户
- `CLOUD_SSH_KEY` — SSH 密钥路径（可选）

### 5.2 传输镜像

```powershell
docker save smartops:latest | bzip2 | ssh -C {{CLOUD_USER}}@{{CLOUD_HOST}} "bunzip2 | docker load"
```

### 5.3 更新 docker-compose.yml（服务器端）

确保服务器端 `docker-compose.yml` 包含 SmartOps 服务：

```yaml
services:
  smartops:
    image: smartops:latest
    ports: ["5001:5001"]
    env_file: .env
    restart: unless-stopped
```

### 5.4 重启

```powershell
ssh {{CLOUD_USER}}@{{CLOUD_HOST}} "docker compose up -d smartops"
```

---

## Phase 6：验证部署

```powershell
# 检查容器运行
ssh {{CLOUD_USER}}@{{CLOUD_HOST}} "docker ps --filter name=smartops"

# 健康检查
curl http://{{CLOUD_HOST}}:5001/api/servers
curl http://{{CLOUD_HOST}}:3100/ready
curl http://{{CLOUD_HOST}}:9090/-/ready
```

### 回滚

验证失败时：

```powershell
ssh {{CLOUD_USER}}@{{CLOUD_HOST}} "docker compose down smartops && docker compose up -d smartops"
```

---

## 目录结构

```
.github/skills/package/
├── SKILL.md
├── scripts/
│   └── clean.py        # 清理脚本（负责缓存/密钥清理逻辑）
└── references/
```

### 脚本职责

`scripts/clean.py` 负责：
- 递归扫描 `__pycache__`、`.pytest_cache` 等缓存目录
- 扫描 `.env` 中的 API Key 并替换为占位符
- 支持 `--execute`（实际删除）、`--keep-data`（保留数据目录）、`--no-sanitize`（跳过脱敏）
- 默认 dry-run 只展示不操作
