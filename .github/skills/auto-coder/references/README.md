# auto-coder References — 使用说明

`references/` 目录包含 auto-coder skill 读取的上下文文件。这些文件是**模板**，你需要将它们填充为项目实际的描述文档后，auto-coder 才能正确理解你的项目并生成合适的代码。

## 文件概览

| 文件 | 用途 | 必须？ |
|------|------|--------|
| `03-tech-stack.md` | 项目的技术栈、依赖、接口约定 | ✅ 建议 |
| `05-architecture.md` | 项目的架构设计、目录结构、数据流 | ✅ 建议 |
| `06-schedule.md` | 开发排期表，标记任务状态 | ✅ 必须（auto-coder 依赖它找任务） |

## 快速开始

### 1. 填排期表（必须）

编辑 `06-schedule.md`，按 Phase 分阶段填入开发任务：

```markdown
| ID | 任务 | 依赖 | 状态 | 备注 |
|----|------|------|------|------|
| A1 | 搭建项目 | — | ⬜ | |
| A2 | 用户登录 | A1 | ⬜ | 使用 JWT |
```

状态标记：`⬜` 未开始 · `🔶` 进行中 · `✅` 已完成 · `❌` 阻塞

### 2. 填架构和栈说明（建议）

编辑 `05-architecture.md` 和 `03-tech-stack.md`，让 auto-coder 了解你的项目结构和设计原则。

### 3. 开始使用

```
auto code        → 从排期表第一个未开始任务开始
auto code A2     → 指定任务 ID
继续实现          → 继续上次进行中的任务
```

## 模板 vs 实际内容

当模板被填充为实际内容后，**此 README.md 和模板注释可以删除**。

`auto-coder` 的 pipeline 会按以下优先级查找这些文件：
1. 项目 `.claude/settings.json` 中显式配置的路径
2. `references/` 下对应的文件
3. `CLAUDE.md` 中隐含的项目描述（兜底）
