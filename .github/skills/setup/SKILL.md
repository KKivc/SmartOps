---
name: setup
description: "SmartOps 交互式环境配置向导。从空白代码库引导用户完成 Python 版本检查、虚拟环境创建、依赖安装、环境变量配置、知识库初始化、Docker 服务启动、Flask 启动。自动诊断并修复启动失败（≤3 轮重试）。Use when user says 'setup', 'set up', 'configure', 'init project', '初始化', '环境配置', '项目配置', 'first run', 'get started', 'quick start', '一键启动', '启动项目', or wants to configure and launch SmartOps from scratch."
---

# SmartOps Setup — 环境配置向导

交互式配置：检查环境 → 装依赖 → 配密钥 → 初始化 → 启动项目 → 使用指南

> 自动修复：任何步骤失败时诊断 → 修复 → 重试（≤3 轮）

---

## Pipeline

```
Preflight → Install Deps → Config → Init Data → Launch Services → Verify → Usage Guide
```

> **⚠️ 每次执行 `python` 命令前先激活 `.venv`**
> - Windows: `.\.venv\Scripts\Activate.ps1`
> - macOS/Linux: `source .venv/bin/activate`

---

## Step 1: Preflight 检查

### 1.1 Python 版本

```powershell
python --version
```

要求 ≥ 3.10。不满足则停止并提示升级。

### 1.2 创建/激活虚拟环境

```powershell
# 检查 .venv 是否存在
Test-Path ".venv"

# 不存在则创建（用 --without-pip 加速）
python -m venv .venv --without-pip

# 激活
.\.venv\Scripts\Activate.ps1

# bootstrap pip
python -m ensurepip --upgrade

# 验证
pip --version
```

如果 `.venv` 已存在，只激活 + 验证。

### 1.3 检查 Docker

```powershell
docker --version
```

Docker 可选——没有 Docker 也能启动 Flask，只是不跑 Loki。提示用户稍后安装。

---

## Step 2: 安装依赖

```powershell
pip install -r requirements.txt
```

**验证：**

```powershell
python -c "import flask; import chromadb; import paramiko; import yaml; print('Core deps OK')"
```

如果安装失败 → 进入修复循环（换国内镜像源、分步安装等）。

---

## Step 3: 配置环境变量

### 3.1 检查 `.env` 是否存在

```powershell
Test-Path ".env"
```

### 3.2 缺失则引导填写

逐项检查，缺失时提示用户输入：

| 变量 | 说明 | 获取方式 |
|------|------|---------|
| `OPENCODE_API_KEY` | DeepSeek API 密钥 | https://opencode.ai |
| `SILICONFLOW_API_KEY` | Embedding + Rerank API 密钥 | https://siliconflow.cn |
| `DASHSCOPE_API_KEY` | DashScope API 密钥（备用） | https://dashscope.aliyun.com |
| `DATABASE_URL` | PostgreSQL 连接串 | 默认 `postgresql://postgres:postgres@localhost/smartops` |
| `ENCRYPTION_KEY` | Fernet 加密密钥 | 自动生成 |
| `CLOUD_LOKI_URL` | 云服务器 Loki 地址（可选） | 部署后再配 |
| `CLOUD_PROMETHEUS_URL` | 云服务器 Prometheus 地址（可选） | 部署后再配 |

**自动生成 ENCRYPTION_KEY：**

```powershell
python -c "from cryptography.fernet import Fernet; print(f'ENCRYPTION_KEY={Fernet.generate_key().decode()}')" >> .env
```

**提示策略：** 每个缺失变量用 AskUserQuestion 问一次，不要一次性问完。

---

## Step 4: 初始化知识库

```powershell
python kb/init_knowledge_base.py
```

**验证：** 检查 `data/chromadb/` 目录是否创建且有内容

如果失败 → 检查 `SILICONFLOW_API_KEY` 是否有效

---

## Step 5: 启动服务

### 5.1 启动 Docker（Loki）

```powershell
docker compose up -d
```

**验证：**

```powershell
curl http://localhost:3100/ready
```

如果 Docker 不可用 → 跳过（提示 Loki 日志功能不可用）

### 5.2 构建 BM25 索引并启动 Flask

Flask 启动时会自动调用 `build_bm25_index()`，直接启动即可：

```powershell
python api.py
```

后台运行（不阻塞后续验证）。

### 5.3 验证 Flask

```powershell
python -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:5001/api/servers')
    print(f'Flask OK: {r.status}')
except Exception as e:
    print(f'Flask 启动失败: {e}')
"
```

如果失败 → 进入修复循环（检查端口占用、依赖错误、数据库连接）

---

## Step 6: 使用指南

启动成功后展示：

```
🎉 SmartOps 启动完成！

Dashboard: http://127.0.0.1:5001
API:       http://127.0.0.1:5001/api/servers

Quick Start:
  1. 添加服务器: POST /api/servers (name, ip, user, password)
  2. 开始对话: 浏览器打开 Dashboard → 提问
  3. 查看监控: Dashboard → 服务器列表

服务状态:
  - Flask: ✅ 运行中
  - Loki:  {✅/❌}
  - 知识库: {✅/❌}
```

根据实际验证结果适配状态图标。

---

## 自动修复循环

任何步骤失败时：

```
Round 0..2:
  读取错误消息
  诊断根因（缺包？端口占用？密钥无效？）
  执行修复
  重新验证
  通过 → 继续下一步
  失败 → 下一轮
Round 3 仍失败 → 报告错误给用户，给出解决建议
```

| 常见问题 | 修复 |
|---------|------|
| `ModuleNotFoundError` | `pip install <package>` |
| 端口 5001 被占用 | `netstat -ano | findstr :5001` → 杀掉进程或换端口 |
| ChromaDB 导入失败 | 检查 Python 版本和依赖 |
| Loki 连接拒绝 | 检查 Docker 是否运行 |
| BM25 索引构建失败 | 检查 `data/ops-skill-tree/` 目录是否有文档 |
