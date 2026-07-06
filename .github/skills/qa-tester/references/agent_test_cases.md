# Agent EDD 测试用例

> 用于评估 Supervisor 多 Agent 的工具调用正确性、信息覆盖率、RCA 结构完整性。

## A-01：工具调用正确性

验证 Agent 在收到问题时是否调用了正确的工具组合。

### 用例 1：查询服务器状态

```
query: "查看 web-01 当前的 CPU 和内存情况"
expected_tools: [query_metric]
expected_routing: infra_worker
expected_key_info: [CPU, memory, 负载]
```

### 用例 2：分析错误日志

```
query: "web-01 最近有没有报错？"
expected_tools: [query_logs, analyze_errors, count_by_level]
expected_routing: log_worker
expected_key_info: [错误数量, 错误码, 级别分布]
```

### 用例 3：查知识库

```
query: "nginx 超时怎么排查？"
expected_tools: [search_knowledge_base]
expected_routing: knowledge_worker
expected_key_info: [nginx, 超时, 排查步骤]
```

### 用例 4：综合故障分析

```
query: "web-01 好像挂了，帮我看看怎么回事"
expected_tools: [query_logs, analyze_errors, query_metric, search_knowledge_base]
expected_routing: [log_worker, infra_worker, knowledge_worker]
expected_key_info: [错误分析, 资源使用, 根因, 修复建议]
```

### 用例 5：查看所有服务器

```
query: "所有服务器的运行状态"
expected_tools: [get_server_list]
expected_routing: （不需要 Worker，直接回答）
expected_key_info: [服务器列表, 在线/离线]
```

### 用例 6：查询历史趋势

```
query: "web-01 过去一小时的 CPU 趋势"
expected_tools: [range_query, query_metric]
expected_routing: infra_worker
expected_key_info: [CPU, 趋势, 时间范围]
```

### 用例 7：查看告警

```
query: "当前有什么告警？"
expected_tools: [check_alerts]
expected_routing: infra_worker
expected_key_info: [告警列表, 级别, 状态]
```

### 用例 8：日志级别统计

```
query: "web-01 的 error 日志有多少条？"
expected_tools: [count_by_level, query_logs]
expected_routing: log_worker
expected_key_info: [error 数量, 日志级别分布]
```

---

## A-02：信息覆盖率

验证 Agent 回复是否覆盖了用户问题所需的关键信息。

### 用例 9：服务器状态全覆盖

```
query: "web-01 状态怎么样？"
required_info: [状态（在线/离线）, CPU, 内存]
acceptable_without: [磁盘, 网络]    # 可选但不强制
```

### 用例 10：错误日志全覆盖

```
query: "分析一下 web-01 的日志，有什么异常"
required_info: [是否有错误, 错误类型, 错误数量]
acceptable_without: [具体每行日志, 时间分布]
```

### 用例 11：RCA 关键要素

```
query: "web-01 频繁 502，什么原因？"
required_info: [根因分析, 影响范围, 修复建议]
acceptable_without: [时间线, 证据细节]
```

---

## A-03：RCA 结构完整性

验证 Agent 的 RCA 报告（当涉及故障分析时）是否包含完整结构。

### 用例 12：完整 RCA（故障场景）

```
query: "web-01 出问题了，全面排查一下"
expected_sections: [summary, root_cause, recommendation]
optional_sections: [timeline, impact, evidence]
```

### 用例 13：普通问答（非故障场景）

```
query: "kubernetes 怎么部署 nginx？"
expected_sections: []    # 非故障场景，不要求 RCA 结构
note: 普通知识问答，不需要 RCA 格式
```

### 用例 14：多步排查场景

```
query: "先看看 web-01 的 CPU，再看看日志有没有异常"
expected_sections: [summary, root_cause]    # 如果发现异常
expected_routing: [infra_worker → log_worker]
min_tool_calls: 2
```

---

## 评分标准

| 维度 | 优秀 | 合格 | 不合格 |
|------|------|------|--------|
| A-01 工具调用 | 调用顺序正确，参数准确 | 主要工具已调用，参数基本正确 | 缺失关键工具调用 |
| A-02 信息覆盖 | 覆盖所有 required_info | 覆盖 80% required_info | 缺失关键信息 |
| A-03 RCA 结构 | 包含所有 expected_sections | 包含 2 个 expected_sections | 遗漏 root_cause 或 recommendation |
