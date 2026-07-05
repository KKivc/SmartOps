---
name: qa-tester
description: "SmartOps 全链路质量评估。自动执行 pytest 单元测试、RAG 检索评估（Recall/Precision/MRR）、Faithfulness 忠实度评分、Agent EDD（Evaluation-Driven Development）多模型/多场景对比评估。逐项串行执行，自动修复失败项（≤3 轮），记录进度到 QA_TEST_PROGRESS.md。Use when user says '跑测试', 'qa', '评估', '测试', 'quality', 'faithfulness', 'agent eval', '模型评估', '选模型', 'EDD', '全量评估', or wants to run any test or evaluation pipeline."
---

# SmartOps QA Tester — 全链路质量评估

> **⚠️ 每次执行 `python` 命令前必须先激活 `.venv`**
> - Windows: `.\.venv\Scripts\Activate.ps1`
> - macOS/Linux: `source .venv/bin/activate`

## Pipeline（严格串行）

```
Read Plan → Pick Item → Execute → Record → Loop
```

---

## Step 0：初始化进度追踪

检查 `.github/skills/qa-tester/QA_TEST_PROGRESS.md` 是否存在：
- **存在** → 读取，继续未完成的评估项
- **不存在** → 创建，写入全量评估清单（见底部默认清单），标记所有项为 ⬜

### 进度文件格式

```markdown
# QA Test Progress

## Summary
⬜ Pending: N | ✅ Pass: 0 | ❌ Fail: 0 | ⏭️ Skip: 0 | 🔧 Fix: 0 | Total: N

## Results

| ID | Test | Status | Note |
|----|------|--------|------|
| P-01 | pytest 单元测试 | ⬜ | |
| R-01 | RAG Recall@K | ⬜ | |
| R-02 | RAG Precision@K | ⬜ | |
| R-03 | RAG MRR | ⬜ | |
| F-01 | Faithfulness 评估 | ⬜ | |
| A-01 | Agent 工具调用正确性 | ⬜ | |
| A-02 | Agent 信息覆盖率 | ⬜ | |
| A-03 | Agent RCA 结构完整性 | ⬜ | |
```

---

## Step 1：选择测试项

1. 读 `QA_TEST_PROGRESS.md` 找第一个 ⬜ 项
2. 如果用户指定了 ID（如 `qa-tester A-01`）→ 定位到该项
3. 如果有 🔧 项 → 优先重测

---

## Step 2：执行评估（串行）

### P-01：pytest 单元测试

```powershell
pytest -v
```

**验证：**
- 全部通过 → ✅
- 有失败 → 分析错误 → 修复 → 最多 3 轮

**Note 格式：** `passed=N, failed=N, skipped=N, duration=Xs`

### R-01 ~ R-03：RAG 检索评估

```powershell
python kb/evaluate.py
```

**验证：** 从输出提取 `hybrid` 和 `vector_only` 的指标

**Note 格式：** `hybrid_recall=X%, vector_recall=X%, diff=+X%`

### F-01：Faithfulness 忠实度评估

```powershell
python -m ragas ...  # 或运行现有的评估脚本
```

**评级标准：**
- ≥ 0.9 → ✅ 优秀
- 0.7~0.9 → ⚠️ 需改进
- < 0.7 → ❌ 差

**Note 格式：** `faithfulness=X.XX, rating=优秀/需改进/差`

### A-01 ~ A-03：Agent EDD 评估

读取 `.github/skills/qa-tester/references/agent_test_cases.md` 中的测试用例。

**对每个测试用例评估：**

```
query: "查看 web-01 最近的 CPU 情况"
expected: 应调用 Prometheus MCP / query_metric
```

**评估方法：** 运行 Supervisor Agent 或静态分析工具调用链路

**A-01 工具调用正确性：** Agent 是否调用了预期工具
**A-02 信息覆盖率：** 输出是否覆盖问题所需的关键信息
**A-03 RCA 结构完整性：** 是否包含 root_cause / impact / recommendation

### 多模型对比模式（当用户说"选模型"时触发）

1. 修改 `llm/supervisor.py` 中的 `model` 字段
2. 对每个候选模型跑 A-01~A-03
3. 输出对比矩阵：

```
| 模型 | 工具正确率 | 信息覆盖率 | Faithfulness | 综合评分 |
|------|-----------|-----------|-------------|---------|
| deepseek-v4-flash | X% | X% | X.XX | X.X |
| deepseek-v4 | X% | X% | X.XX | X.X |
```

---

## Step 3：记录结果

**⛔ GATE — 每完成一项，先记录再选下一项。**

编辑 `QA_TEST_PROGRESS.md`，更新对应行的状态 + Note：

| 状态 | 含义 |
|------|------|
| ✅ | 通过——有终端输出证据 |
| ❌ | 失败——3 轮修复后仍未通过 |
| ⏭️ | 跳过——依赖不可用 |
| 🔧 | 已修复——需要重测 |
| ⬜ | 未开始 |

**Note 格式规则：**
- 必须包含 ≥2 个从终端输出抄录的具体数值
- 禁止写 "应该可以"、"代码使用了"、"已验证" 等推断性描述
- 禁止跨引用 "同 X-XX"

---

## Step 4：修复循环（≤3 轮）

```
Round 0..2:
  如果测试失败 → 分析错误 → 修代码 → 重新执行
  如果通过 → 标记 ✅
Round 3 仍失败 → 标记 ❌，报告失败详情
```

---

## 默认全量评估清单

| ID | 测试 | 类别 |
|----|------|------|
| P-01 | pytest 单元测试 | Unit |
| R-01 | RAG Recall@K | Retrieval |
| R-02 | RAG Precision@K | Retrieval |
| R-03 | RAG MRR | Retrieval |
| F-01 | Faithfulness 忠实度 | Generation |
| A-01 | Agent 工具调用正确性 | Agent EDD |
| A-02 | Agent 信息覆盖率 | Agent EDD |
| A-03 | Agent RCA 结构完整性 | Agent EDD |
