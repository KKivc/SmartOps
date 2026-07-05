---
name: auto-coder
description: "Automated spec-driven development for SmartOps. Reads the multi-agent MCP architecture spec, finds the next pending implementation task from the schedule, writes code following the architecture and patterns, runs qa-tester with up to 3 auto-fix rounds, and persists progress with commits. Use when user says 'auto code', '自动开发', '自动写代码', 'auto dev', '一键开发', '继续实现', or wants automated task-by-task implementation from the design spec."
---

# SmartOps Auto Coder

One trigger completes: **read spec → find task → implement → self-test → persist**.

> **⚠️ CRITICAL: Activate `.venv` before ANY `python`/`pytest` command**
> - Windows: `.\.venv\Scripts\Activate.ps1`
> - macOS/Linux: `source .venv/bin/activate`

---

## Pipeline

```
Sync Spec → Find Task → Read Context → Implement → Test (≤3 fix rounds) → Persist
```

---

## Reference Map

All files under `.github/skills/auto-coder/references/`:

| File | Content | When to Read |
|------|---------|-------------|
| `05-architecture.md` | Architecture & module design | Every cycle |
| `03-tech-stack.md` | Tech stack & interfaces | When implementing MCP/Agent |
| `06-schedule.md` | Task schedule & status | Every cycle |

**Spec doc:** `docs/superpowers/specs/2026-07-05-smartops-multi-agent-mcp-design.md`

---

## Step 1: Sync Spec

If any spec file has been updated, re-read the schedule:

```powershell
# Re-read the schedule to get latest task statuses
type .github/skills/auto-coder/references/06-schedule.md
```

**Task markers:**

| Marker | Status |
|--------|--------|
| `⬜` | Not started |
| `🔶` | In progress |
| `✅` | Completed |
| `❌` | Blocked |

---

## Step 2: Find Task

1. Pick the first `🔶` (in progress) task → continue it
2. If none in progress → pick the first `⬜` (not started) task
3. If user specified a task ID (e.g. `auto code B2`) → target that one
4. Check dependencies: if dependency is `⬜` or `❌`, warn and stop

---

## Step 3: Read Context

Read the relevant reference files:

| Task Type | Read These |
|-----------|-----------|
| MCP (B-series) | `05-architecture.md` (MCP section), `03-tech-stack.md` |
| Agent (C-series) | `05-architecture.md` (full), `03-tech-stack.md` |
| Cleanup (D-series) | `05-architecture.md` (files to modify) |

---

## Step 4: Implement

1. **Extract** from spec: inputs/outputs, interfaces, design principles, file paths
2. **Plan** files to create/modify before writing any code
3. **Code** following existing project patterns:
   - Match existing code style (docstrings, imports, error handling)
   - Follow the architecture spec exactly
   - Use `.env` values, never hardcode URLs/keys
4. **Self-review** before testing: verify all created files exist and imports are correct

---

## Step 5: Test & Auto-Fix

```powershell
# Run relevant tests
pytest -v [relevant test file or -k filter]
```

**Fix loop:**

```
Round 0..2:
  Run pytest on relevant file
  If pass → continue to Step 6
  If fail → analyze error, apply fix, re-run

Round 3 still failing → STOP, show failure report
```

For tasks that don't have dedicated tests yet, verify manually:
- MCP tasks: write a small Python snippet to import and call the module
- Agent tasks: verify the agent can be instantiated

---

## Step 6: Persist

1. **Update schedule**: change task marker `⬜` → `✅` (or `🔶` if partially done)
2. **Update `06-schedule.md`**: update the "当前进度" section
3. **Show summary**:

```
✅ [B2] 实现 llm/mcp/loki_mcp.py — done
   Files: llm/mcp/__init__.py, llm/mcp/loki_mcp.py
   Tests: 3/3 passed
   Commit: feat(mcp): [B2] implement Loki MCP layer

   "commit" → git add + commit
   "skip"   → end
   "next"   → commit + start next task
```

4. On "next" → loop back to Step 1

---

## 实现注意事项

| 任务 | 关键要点 |
|------|---------|
| B2 (Loki MCP) | 用 `requests` 调 Loki HTTP API；`analyze_errors` 需解析日志行统计错误码 |
| B3 (Prom MCP) | 用 `requests` 调 Prometheus HTTP API；`range_query` 需处理时间范围参数 |
| C2 (Supervisor) | LangGraph StateGraph；循环条件边路由到 Worker 或 FINISH |
| C3 (Workers) | 工具函数，不要调 LLM；从 intermediate_results 读/写 |
| D1 (精简 tools) | 删除 get_logs, get_metrics_history；get_server_status 改为查 Prometheus |
| D2 (精简 collector) | 只保留心跳 + 离线检测；删除指标/日志采集 |
