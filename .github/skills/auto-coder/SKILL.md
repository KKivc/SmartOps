---
name: auto-coder
description: "通用自动化开发助手。从项目排期表读取下一个开发任务，按架构/技术栈上下文自动实现，自测（≤3 轮自动修复）并提交进度。当用户说 'auto code'、'自动开发'、'自动写代码'、'auto dev'、'一键开发'、'继续实现'、'auto code 任务ID' 或任何要求按排期自动实现的场景时触发。"
---

# Auto Coder — 通用自动化开发助手

一次触发完成：**匹配项目 → 读取排期 → 实现 → 自测 → 提交**

> **🔍 自动探测：** 根据项目文件自动识别类型和测试框架
> **📋 可配置：** 通过 `references/` 目录的模板或项目 `CLAUDE.md` 提供上下文

---

## Pipeline

```
Detect Project → Read Schedule → Read Context → Implement → Test (≤3 fix rounds) → Persist
```

---

## 参考文件

所有文件在 `.github/skills/auto-coder/references/` 下：

| 文件 | 内容 | 何时读取 |
|------|------|---------|
| `05-architecture.md` | 架构设计 & 目录结构 | 每次实现前 |
| `03-tech-stack.md` | 技术栈 & 接口约定 | 每次实现前 |
| `06-schedule.md` | 任务排期 & 状态 | 每次循环 |

如果某文件不存在，从项目 `CLAUDE.md` 或 `.claude/settings.json` 推断信息。

---

## Step 0：探测项目

在进入 pipeline 前自动探测项目类型：

```powershell
# 检查项目类型
Test-Path "requirements.txt"      # → Python
Test-Path "package.json"          # → Node
Test-Path "go.mod"                # → Go
Test-Path "Cargo.toml"            # → Rust
```

**探测结果决定：**

| 属性 | Python | Node | Go |
|------|--------|------|----|
| 测试命令 | `pytest -v` | `npm test` / `npx jest` | `go test ./...` |
| 风格检查 | `ruff check .` | `npx eslint .` | `gofmt` |
| 包管理器 | `pip install` | `npm install` | `go mod tidy` |

如果 `references/` 中存在已填写的 `03-tech-stack.md`，以文件中的配置为准。

---

## Step 1：读取排期

从 `.github/skills/auto-coder/references/06-schedule.md` 读取任务排期。

### 查找下一个任务

1. 找到第一个 **`🔶`（进行中）** 的任务 → 继续它
2. 如果没有进行中的 → 找第一个 **`⬜`（未开始）** 的任务
3. 如果用户指定了 ID（如 `auto code A2`）→ 定位到该任务
4. 检查依赖：如果依赖项是 `⬜` 或 `❌`，警告并停止

### 任务标记

| 标记 | 状态 |
|------|------|
| `⬜` | 未开始 |
| `🔶` | 进行中 |
| `✅` | 已完成 |
| `❌` | 阻塞 |

---

## Step 2：读取上下文

根据任务类型读取参考文件：

| 场景 | 读取 |
|------|------|
| 新建模块 | `05-architecture.md`（文件结构 + 设计原则） |
| 实现接口 | `03-tech-stack.md`（技术栈 + API 约定） |
| 补充功能 | `CLAUDE.md`（项目规则 + 约定） |
| 以上全部 | 三份都读 |

如果 reference 文件还是**空白模板**（含注释说明），则改为从项目 `CLAUDE.md` 和已有代码中推断上下文。

---

## Step 3：实现

1. **提取** 上下文中关键信息：输入/输出、接口定义、设计原则、文件路径
2. **规划** 要创建/修改的文件清单，确认后再写代码
3. **编码** 匹配项目已有风格：
   - 保持一致的注释/docstring 风格
   - 遵循项目架构设计
   - 使用 `.env` 或配置文件中的值，不硬编码
   - 参考项目中已有的类似实现
4. **自检** 测试前验证：所有创建的文件存在、导入正确、语法无误

---

## Step 4：测试 & 自动修复

### 运行测试

```powershell
# Python 项目
pytest -v [相关测试文件或 -k 过滤]

# Node 项目
npm test -- [相关测试文件]

# Go 项目
go test ./[相关模块]/...
```

如果项目没有该语言的测试框架，尝试手动验证：
- Python: `python -c "import 模块; print('OK')"`
- Node: `node -e "require('模块')"`
- Go: `go build ./...`

### 修复循环

```
Round 0..2:
  运行测试
  通过 → 继续到 Step 5
  失败 → 分析错误 → 应用修复 → 重新测试

Round 3 仍失败 → 停止，展示失败报告
```

### 常见修复

| 错误类型 | 修复方法 |
|---------|---------|
| `ModuleNotFoundError` / `Cannot find module` | 安装缺失依赖 |
| 语法错误 | 修复代码 |
| 测试断言失败 | 分析逻辑错误并修改 |
| 类型错误 | 修复类型不匹配 |

---

## Step 5：提交进度

1. **更新排期表**：`⬜` → `✅`（或 `🔶` 如果部分完成）
2. **更新进度摘要**：修改 `06-schedule.md` 的「当前进度」部分
3. **展示摘要**：

```
✅ [A2] 实现用户登录接口 — done
   文件: src/api/auth.py, src/models/user.py
   测试: 3/3 passed
   提交: feat(auth): [A2] 实现用户登录接口

   "commit" → git add + commit
   "skip"   → 结束
   "next"   → commit + 开始下一个任务
```

4. 用户说 `"next"` → 循环回 Step 1

---

## 项目配置（可选）

在项目 `.claude/settings.json` 或 `CLAUDE.md` 中可以配置以下参数：

```json
// .claude/settings.json
{
  "skills": {
    "auto-coder": {
      "schedule": "docs/schedule.md",
      "architecture": "docs/architecture.md",
      "tech-stack": "docs/tech-stack.md",
      "test-command": "pytest -v -x",
      "spec-dir": "docs/specs/"
    }
  }
}
```

## 实现注意事项

| 场景 | 关键要点 |
|------|---------|
| 新建模块 | 先在 `05-architecture.md` 确认目录结构和文件命名规则 |
| 引入新依赖 | 更新 `requirements.txt` / `package.json`，使用现有版本风格 |
| 修改接口 | 保持向后兼容，或同步更新所有调用方 |
| 删除废弃代码 | 只清理自己修改引入的废弃代码，不动原有的 |
