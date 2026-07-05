"""
RAG 评估脚本 — 检索评估 + LLM 生成评估 (Ragas 风格)
=====================================================
流程：检索 → 生成 → Judge 评分 → 对比

用法：
    1. 先跑 init_knowledge_base.py 初始化 ChromaDB
    2. 再跑本脚本: python kb/evaluate.py

对比模式：hybrid_search vs vector_only
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.retriever import hybrid_search, build_bm25_index
from llm.rag import embed_text, get_collection
from openai import OpenAI
import time
import json
import math


# ============================================================
# 配置
# ============================================================

OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY")
OPENCODE_BASE_URL = "https://opencode.ai/zen/go/v1"
GENERATOR_MODEL = "deepseek-v4-flash"     # 生成答案
JUDGE_MODEL = "qwen3.6-35b-a3b"             # 评估打分
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL")

EVAL_DIR = "data/eval"
os.makedirs(EVAL_DIR, exist_ok=True)

# OpenAI 兼容客户端
client = OpenAI(api_key=OPENCODE_API_KEY, base_url=OPENCODE_BASE_URL)

# ============================================================
# 测试集 — 15 条 query
# ============================================================

TEST_QUERIES = [
    # ---- Linux 主机排障 ----
    {
        "query": "top 命令查看 CPU 使用率",
        "relevant_files": [
            "02-Linux/02-CPU、内存与负载排查常用命令.md",
        ],
    },
    {
        "query": "free 命令查看内存",
        "relevant_files": [
            "02-Linux/02-CPU、内存与负载排查常用命令.md",
        ],
    },
    {
        "query": "服务器 CPU 使用率突然飙高怎么排查",
        "relevant_files": [
            "02-Linux/09-高级 CPU 排查：线程、上下文切换、软中断与 perf.md",
            "02-Linux/02-CPU、内存与负载排查常用命令.md",
        ],
    },
    {
        "query": "OOM Killer 杀进程的机制是什么，怎么预防",
        "relevant_files": [
            "02-Linux/10-高级内存排查：OOM、内存泄漏、page cache、slab 与 cgroup.md",
        ],
    },
    {
        "query": "线上服务突然不可用，我该按什么步骤排查",
        "relevant_files": [
            "02-Linux/01-主机层面排障总览与系统资源排查.md",
        ],
    },
    {
        "query": "磁盘空间不足怎么排查",
        "relevant_files": [
            "02-Linux/03-磁盘空间、inode 与磁盘 IO 排查.md",
        ],
    },
    # ---- Docker ----
    {
        "query": "Docker 容器日志太多怎么清理",
        "relevant_files": [
            "03-Docker/05-Docker 存储、日志与磁盘优化.md",
        ],
    },
    {
        "query": "Docker 镜像构建优化方法",
        "relevant_files": [
            "03-Docker/10-Dockerfile 基础：镜像构建与最佳实践.md",
            "03-Docker/12-BuildKit、buildx 与高级镜像构建.md",
        ],
    },
    # ---- Kubernetes ----
    {
        "query": "Pod 一直 Pending 怎么排查",
        "relevant_files": [
            "04-Kubernetes/08-运维/03-集群基础排障/02-Pod Pending 排查：资源不足、调度失败、镜像与 PVC.md",
        ],
    },
    {
        "query": "Node NotReady 怎么排查",
        "relevant_files": [
            "04-Kubernetes/08-运维/03-集群基础排障/01-Node NotReady 排查：kubelet、containerd、CNI 与节点事件.md",
        ],
    },
    # ---- 中间件 ----
    {
        "query": "MySQL 慢查询怎么定位和优化",
        "relevant_files": [
            "07-中间件/数据库/MySQL.md",
        ],
    },
    {
        "query": "Kafka 消息堆积怎么处理",
        "relevant_files": [
            "07-中间件/消息队列/Kafka.md",
        ],
    },
    # ---- 监控 ----
    {
        "query": "Prometheus 告警规则怎么配置",
        "relevant_files": [
            "09-监控/Prometheus.md",
        ],
    },
    # ---- 网络 ----
    {
        "query": "Linux 网络连通性排查常用命令",
        "relevant_files": [
            "02-Linux/06-网络连通性、端口、路由与流量排查.md",
        ],
    },
    # ---- 安全 ----
    {
        "query": "Linux 服务器安全加固基本措施",
        "relevant_files": [
            "14-安全/Linux安全加固.md",
            "14-安全/SSH安全.md",
            "14-安全/防火墙策略.md",
        ],
    },
]


# ============================================================
# 检索评估（已有指标，保留）
# ============================================================

def compute_retrieval_metrics(query, relevant_ids, retrieved_items, k=5):
    """Recall@k、Precision@k、MRR"""
    relevant_files = set()
    for rid in relevant_ids:
        if "#" in rid:
            relevant_files.add(rid.split("#")[0])
        else:
            relevant_files.add(rid)

    retrieved_files = []
    for item in retrieved_items:
        meta = item.get("metadata", {})
        doc_id = meta.get("file", "")
        retrieved_files.append(doc_id)

    retrieved_at_k = retrieved_files[:k]
    relevant_set = relevant_files

    matched = [f for f in retrieved_at_k if f in relevant_set]
    recall = len(set(matched)) / len(relevant_set) if relevant_set else 0

    unique_retrieved = []
    seen = set()
    for f in retrieved_at_k:
        if f not in seen:
            seen.add(f)
            unique_retrieved.append(f)
    precision = (
        len([f for f in unique_retrieved if f in relevant_set]) / len(unique_retrieved)
        if unique_retrieved else 0
    )

    mrr = 0.0
    for i, f in enumerate(retrieved_at_k):
        if f in relevant_set:
            mrr = 1.0 / (i + 1)
            break

    return {
        "recall": recall, "precision": precision, "mrr": mrr,
        "retrieved": unique_retrieved,
    }


# ============================================================
# LLM 调用辅助
# ============================================================

def call_llm(model, system_prompt, user_prompt, temperature=0.0, max_tokens=1024):
    """调用 OpenCode API（OpenAI 兼容）"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        )
    return resp.choices[0].message.content


# ============================================================
# Phase 1: 检索（已有）
# ============================================================

def vector_search(query, top_k=3):
    """纯向量搜索"""
    collection = get_collection()
    vector = embed_text(query)
    results = collection.query(
        query_embeddings=[vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    if not results["documents"] or not results["documents"][0]:
        return []
    output = []
    for i in range(len(results["documents"][0])):
        output.append({
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i],
        })
    return output


def run_retrieval(search_fn, name):
    """对所有 query 执行检索，存 JSON"""
    path = f"{EVAL_DIR}/retrieval_{name}.json"

    # 检查缓存
    if os.path.exists(path):
        print(f"  [CACHE] 命中检索缓存: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    results = []
    for tq in TEST_QUERIES:
        chunks = search_fn(tq["query"])
        results.append({
            "query": tq["query"],
            "relevant_files": tq["relevant_files"],
            "chunks": [
                {"content": c["content"], "metadata": c["metadata"], "score": c["score"]}
                for c in chunks
            ],
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  [DONE] 检索完成: {path} ({len(results)} 条)")
    return results


# ============================================================
# Phase 2: 生成答案
# ============================================================

GENERATOR_SYSTEM = """你是一个运维专家助手。请严格基于提供的上下文回答问题。

规则：
- 只使用上下文中提供的信息，不要编造
- 如果上下文不足以准确回答，直接说"根据现有信息无法确定"
- 回答要简洁具体，包含可操作的命令或步骤
- 不要调用工具，不要执行命令"""


def generate_answer(query, chunks):
    """根据检索到的 chunks 生成答案"""
    if not chunks:
        return "（无可用上下文）"

    context_parts = []
    for i, c in enumerate(chunks, 1):
        file = c["metadata"].get("file", "未知")
        context_parts.append(f"[来源{i}] {file}\n{c['content']}")
    context = "\n\n".join(context_parts)

    user_prompt = f"上下文：\n{context}\n\n问题：{query}\n\n请基于上下文回答："

    try:
        answer = call_llm(GENERATOR_MODEL, GENERATOR_SYSTEM, user_prompt)
        return answer
    except Exception as e:
        return f"[生成失败: {e}]"


def run_generation(retrieval_results, name):
    """对所有检索结果生成答案，存 JSON"""
    path = f"{EVAL_DIR}/generation_{name}.json"

    # 检查缓存
    if os.path.exists(path):
        print(f"  [CACHE] 命中生成缓存: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    results = []
    for i, item in enumerate(retrieval_results):
        print(f"  生成 [{name}] {i+1}/{len(retrieval_results)}: {item['query'][:40]}...")
        answer = generate_answer(item["query"], item["chunks"])
        item["answer"] = answer
        results.append(item)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  [DONE] 生成完成: {path}")
    return results


# ============================================================
# Phase 3: Ragas 评分（固定 max_tokens 修复版）
# ============================================================

def run_evaluation(generation_results, name, judge_model="deepseek-v4-pro"):
    """用 Ragas 对生成结果评分，存 JSON"""
    path = f"{EVAL_DIR}/evaluation_{name}.json"

    # 缓存检查
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if "ragas_scores" in cached[0]:
            print(f"  [CACHE] 命中评估缓存: {path}")
            return cached

    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import faithfulness
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper
    from ragas.run_config import RunConfig

    # 转为 HuggingFace Dataset
    rows = []
    for item in generation_results:
        rows.append({
            "question": item["query"],
            "answer": item.get("answer", ""),
            "contexts": [c["content"] for c in item.get("chunks", [])],
        })

    dataset = Dataset.from_list(rows)

    # judge LLM — 走 DashScope (Qwen 官方), qwen3.7-plus 推理模型需 bypass_n
    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=judge_model,
            base_url=DASHSCOPE_BASE_URL,
            api_key=DASHSCOPE_API_KEY,
            max_tokens=8192,
        ),
        bypass_n=True,
        run_config=RunConfig(timeout=300),
    )

    # 绑定 OPENAI_API_KEY（Ragas 需要，OpenCode 兼容）
    import os as _os
    if not _os.getenv("OPENAI_API_KEY"):
        _os.environ["OPENAI_API_KEY"] = OPENCODE_API_KEY

    print(f"  评估 [{name}] 共 {len(rows)} 条...")
    _run_config = RunConfig(timeout=300)
    result = evaluate(
        dataset,
        metrics=[faithfulness],
        llm=judge_llm,
        run_config=_run_config,
    )

    # result 是 EvaluationResult，转成 DataFrame
    df = result.to_pandas()

    # 把分数写回原数据
    for i, item in enumerate(generation_results):
        raw = float(df.loc[i, "faithfulness"])
        item["ragas_scores"] = {
            "faithfulness": raw if not math.isnan(raw) else 0.0,
        }

    # JSON dump 前清掉 NaN（nan → null）
    with open(path, "w", encoding="utf-8") as f:
        json.dump(generation_results, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(f"  [DONE] 评估完成: {path}")
    return generation_results


# ============================================================
# Phase 4: 检索指标对比（保留原有逻辑）
# ============================================================

def evaluate_retrieval(search_fn, test_queries, k=5):
    """计算传统检索指标"""
    all_metrics = []
    for tq in test_queries:
        try:
            results = search_fn(tq["query"])
        except Exception as e:
            print(f"  [ERR] {tq['query'][:40]}... → {e}")
            all_metrics.append({"recall": 0, "precision": 0, "mrr": 0, "retrieved": []})
            continue
        m = compute_retrieval_metrics(tq["query"], tq["relevant_files"], results, k)
        all_metrics.append(m)
    avg = {}
    for key in ["recall", "precision", "mrr"]:
        avg[key] = sum(m[key] for m in all_metrics) / len(all_metrics) if all_metrics else 0
    return avg, all_metrics


# ============================================================
# 汇总 & 对比
# ============================================================

def print_header(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_metrics(label, metrics, indent="  "):
    print(f"{indent}{label}:")
    for k, v in metrics.items():
        print(f"{indent}  {k:<20}: {v:.2%}" if isinstance(v, float) and v <= 1 else f"{indent}  {k:<20}: {v}")


def run_comparison():
    """完整对比：hybrid vs vector"""
    print_header("RAG 评估 — 完整流程")
    print("  Judge 模型:", JUDGE_MODEL)
    print("  生成模型:", GENERATOR_MODEL)

    # 确保 BM25 索引
    print("\n[0] 初始化 BM25 索引...")
    build_bm25_index()

    # ============================================================
    # Pipeline A: Hybrid
    # ============================================================
    print_header("Pipeline A: hybrid_search")
    hybrid_retrieval = run_retrieval(hybrid_search, "hybrid")
    hybrid_gen = run_generation(hybrid_retrieval, "hybrid")
    hybrid_eval = run_evaluation(hybrid_gen, "hybrid", JUDGE_MODEL)

    # ============================================================
    # Pipeline B: Vector Only
    # ============================================================
    print_header("Pipeline B: vector_only")
    vector_retrieval = run_retrieval(vector_search, "vector")
    vector_gen = run_generation(vector_retrieval, "vector")
    vector_eval = run_evaluation(vector_gen, "vector", JUDGE_MODEL)

    # ============================================================
    # 检索指标对比
    # ============================================================
    print_header("检索指标对比（文件命中率）")

    start = time.time()
    hybrid_metrics, hybrid_detail = evaluate_retrieval(hybrid_search, TEST_QUERIES, k=5)
    hybrid_time = time.time() - start

    start = time.time()
    vector_metrics, vector_detail = evaluate_retrieval(vector_search, TEST_QUERIES, k=5)
    vector_time = time.time() - start

    print(f"\n  {'指标':<15} {'hybrid':>12} {'vector':>12} {'提升':>10}")
    print(f"  {'-' * 50}")
    for key in ["recall", "precision", "mrr"]:
        diff = hybrid_metrics[key] - vector_metrics[key]
        sign = "+" if diff > 0 else ""
        print(f"  {key:<15} {hybrid_metrics[key]:>11.2%} {vector_metrics[key]:>11.2%} {sign}{diff:>9.2%}")
    print(f"  {'耗时':<15} {hybrid_time:>11.1f}s {vector_time:>11.1f}s")

    # ============================================================
    # LLM 评估指标对比
    # ============================================================
    print_header(f"LLM 评估指标对比（Judge: {JUDGE_MODEL}）")

    llm_metrics = ["faithfulness"]
    metric_labels = {
        "faithfulness": "Faithfulness（答案忠实度）",
    }

    hybrid_scores = {}
    vector_scores = {}

    for metric in llm_metrics:
        h_vals = [item["ragas_scores"][metric] for item in hybrid_eval
                  if metric in item.get("ragas_scores", {})
                  and not (isinstance(item["ragas_scores"][metric], float) and math.isnan(item["ragas_scores"][metric]))]
        v_vals = [item["ragas_scores"][metric] for item in vector_eval
                  if metric in item.get("ragas_scores", {})
                  and not (isinstance(item["ragas_scores"][metric], float) and math.isnan(item["ragas_scores"][metric]))]
        hybrid_scores[metric] = sum(h_vals) / len(h_vals) if h_vals else 0
        vector_scores[metric] = sum(v_vals) / len(v_vals) if v_vals else 0

    print(f"\n  {'指标':<30} {'hybrid':>10} {'vector':>10} {'提升':>10}")
    print(f"  {'-' * 65}")
    for metric in llm_metrics:
        diff = hybrid_scores[metric] - vector_scores[metric]
        sign = "+" if diff > 0 else ""
        label = metric_labels.get(metric, metric)
        print(f"  {label:<30} {hybrid_scores[metric]:>9.2%} {vector_scores[metric]:>9.2%} {sign}{diff:>9.2%}")

    # ============================================================
    # 单条详情
    # ============================================================
    print_header("单条 Query 详情 (hybrid_search)")

    for i, item in enumerate(hybrid_eval):
        scores = item.get("ragas_scores", {})
        score = scores.get("faithfulness", 0)

        if isinstance(score, str) or math.isnan(score):
            status = "[ERR]"
            score_str = "N/A"
        elif score >= 0.8:
            status = "[OK]"
            score_str = f"{score:.0%}"
        elif score >= 0.5:
            status = "[WARN]"
            score_str = f"{score:.0%}"
        else:
            status = "[FAIL]"
            score_str = f"{score:.0%}"

        print(f"  {status} Q{i+1:02d}: {item['query'][:55]:<55}")
        print(f"      Faithfulness={score_str}")

    # ============================================================
    # 总结
    # ============================================================
    print_header("对比总结")

    # 检索指标总结
    h_better = sum(1 for k in ["recall", "precision", "mrr"] if hybrid_metrics[k] > vector_metrics[k])
    v_better = 3 - h_better
    print(f"  检索指标: hybrid 赢 {h_better}/3, vector 赢 {v_better}/3")

    # LLM 指标总结
    h_better_llm = sum(1 for m in llm_metrics if hybrid_scores[m] > vector_scores[m])
    v_better_llm = len(llm_metrics) - h_better_llm
    print(f"  LLM 指标: hybrid 赢 {h_better_llm}/{len(llm_metrics)}, vector 赢 {v_better_llm}/{len(llm_metrics)}")

    print(f"\n  中间产物已保存到 {EVAL_DIR}/")
    print(f"  改 Judge prompt 后可直接重跑 evaluate 阶段，无需重新生成。")


if __name__ == "__main__":
    run_comparison()
