"""
BM25 + 向量 + RRF 统一检索（Parent-Child Retrieval）
"""
from llm.rag import embed_text, get_collection, get_parent_collection
from rank_bm25 import BM25Okapi
import jieba
import os
import requests

SILICONFLOW_API_KEY = os.getenv('SILICONFLOW_API_KEY')

# 查询 → 分类映射（用于 category 过滤）
CATEGORY_KEYWORDS = {
    "01-Windows": ["windows"],
    "02-Linux": ["linux", "cpu", "内存", "磁盘", "oom", "网络连通性",
                 "服务器", "top", "free", "grep", "ping", "端口", "df", "du",
                 "负载", "inode", "丢包", "tcp", "日志治理", "日志"],
    "03-Docker": ["docker", "容器", "镜像", "compose", "dockerfile", "containerd",
                  "harbor"],
    "04-Kubernetes": ["kubernetes", "k8s", "pod", "node", "集群", "deployment",
                      "service", "ingress", "kube", "etcd", "coredns", "pending",
                      "证书", "drain", "helm", "chart"],
    "05-存储": ["ceph", "minio", "存储", "对象存储", "rbd", "osd", "rbd",
                "rgw", "pool", "pg"],
    "07-中间件": ["mysql", "kafka", "redis", "rabbitmq", "慢查询", "消息堆积",
                 "中间件", "nginx", "elasticsearch", "502", "504", "websocket"],
    "08-CI-CD": ["ci", "cd", "gitlab", "jenkins", "argo", "gitops", "流水线",
                 "helm values", "helm"],
    "09-监控": ["prometheus", "grafana", "告警", "alert", "监控", "metrics", "exporter"],
    "10-日志": ["loki", "日志", "efk", "filebeat", "log", "logql"],
    "11-GPU": ["gpu", "nvidia", "cuda", "cudnn"],
    "14-安全": ["安全加固", "防火墙", "ssh", "证书", "tls", "ssl", "fail2ban",
                "rbac", "kubernetes安全"],
    "15-容器网络": ["calico", "flannel", "cilium", "容器网络", "cni", "网络策略",
                   "service mesh"],
    "16-运维工具": ["ansible", "terraform", "k9s", "kuboard", "运维工具"],
    "18-SRE": ["sla", "sli", "slo", "容量规划", "可观测性"],
    "19-故障案例": ["故障案例", "生产事故", "故障复盘", "生产故障"],
    "20-Runbook": ["runbook", "应急预案", "故障处理", "发布回滚", "备份恢复"],
    "00-运维架构": ["运维架构", "运维知识", "云原生架构", "学习路线"],
    "12-虚拟化": ["kvm", "vmware", "虚拟化", "pve"],
    "13-云平台": ["阿里云", "腾讯云", "aws", "openstack"],
    "17-PVE": ["pve", "proxmox"],
    "24-云迁移": ["云迁移", "数据迁移", "割接", "迁移工具"],
}


def classify_query(query):
    """基于关键字将查询映射到知识库分类，匹配不到返回 None"""
    q = query.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return category
    return None

# 全局变量，启动时初始化
_bm25 = None
_doc_ids = None
_doc_metadatas = None
_doc_texts = None

def build_bm25_index():
    """
    构建 BM25 索引（在 child collection 上）
    """
    global _bm25, _doc_ids, _doc_metadatas, _doc_texts
    collection = get_collection()
    # 分页获取所有文档（SQLite 变量限制约 999）
    all_ids = []
    all_texts = []
    all_metadatas = []
    batch_size = 500
    offset = 0
    while True:
        batch = collection.get(limit=batch_size, offset=offset)
        if not batch['ids']:
            break
        all_ids.extend(batch['ids'])
        all_texts.extend(batch['documents'])
        all_metadatas.extend(batch['metadatas'])
        offset += batch_size
    texts = all_texts
    # 构建 BM25 索引
    tokenized = [list(jieba.cut(text)) for text in texts]
    bm25 = BM25Okapi(tokenized)
    _bm25 = bm25
    _doc_ids = all_ids
    _doc_metadatas = all_metadatas
    _doc_texts = texts


def rerank(query, items, top_n=5):
    """
    对 items 进行重排序
    """
    if not items:
        return []
    url = "https://api.siliconflow.cn/v1/rerank"
    headers = {
        "Authorization": f"Bearer {os.environ.get('SILICONFLOW_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "Qwen/Qwen3-Reranker-8B",
        "query": query,
        "documents": [item['content'] for item in items],
        "top_n": min(top_n, len(items))
    }
    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    results = data['results']
    output = []
    for r in results:
        idx = r['index']
        output.append({
            "content": items[idx]['content'],
            "metadata": items[idx]['metadata'],
            "score": r['relevance_score']
        })
    return output


def _filter_results(ranked, top_k):
    """
    质量过滤：移除分数远低于最高分的噪声 chunk
    改为纯相对阈值，避免 reranker 分数整体偏低时全部误杀
    """
    if not ranked:
        return []
    top_score = ranked[0]["score"]
    threshold = top_score * 0.1
    filtered = [r for r in ranked if r["score"] >= threshold]
    # 保底：至少返回排名最高的一条
    if not filtered:
        filtered = [ranked[0]]
    return filtered[:top_k]


def hybrid_search(query, top_k=5, category=None):
    """
    搜索 child chunks → 映射到 parent chunks → 重排序 → 返回

    参数:
        query: 搜索文本
        top_k: 返回几段
        category: 可选，限制搜索的知识库子类（如 "02-Linux"、"04-Kubernetes"）
    """
    child_collection = get_collection()

    # 1. 向量检索（在 child collection 上）
    vector = embed_text(query)
    where_filter = {"category": category} if category else None
    vector_results = child_collection.query(
        query_embeddings=[vector],
        n_results=top_k + 2,
        where=where_filter,
        include=['documents', 'metadatas', 'distances']
    )
    if not vector_results['documents'] or not vector_results['documents'][0]:
             return []

    vector_output = []
    for i in range(len(vector_results['documents'][0])):
            vector_output.append({
                "content": vector_results['documents'][0][i],
                "metadata": vector_results['metadatas'][0][i],
                "score": 1 - vector_results['distances'][0][i]
            })

    # 2. BM25 检索（在 child collection 上）
    bm25_output = []

    if _bm25 is None:
        build_bm25_index()

    tokenized_query = list(jieba.cut(query))
    bm25_scores = _bm25.get_scores(tokenized_query)
    sorted_results = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)
    # BM25 按 category 过滤
    if category:
        sorted_results = [(idx, score) for idx, score in sorted_results
                          if _doc_metadatas[idx].get("category") == category]
    bm25_results = sorted_results[:top_k + 2]

    for idx, score in bm25_results:
        bm25_output.append({
            "content": _doc_texts[idx],
            "metadata": _doc_metadatas[idx],
            "score": score
        })

    # 3. RRF 融合排序（加权：向量 > BM25）
    K = 30
    VECTOR_WEIGHT = 2.0
    BM25_WEIGHT = 0.5
    rrf_scores = {}
    rrf_items = {}

    for rank, item in enumerate(vector_output, 1):
        doc_id = item['metadata']['file'] + '#' + item['metadata']['title']
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + VECTOR_WEIGHT / (K + rank)
        rrf_items[doc_id] = item

    for rank, item in enumerate(bm25_output, 1):
        doc_id = item['metadata']['file'] + '#' + item['metadata']['title']
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + BM25_WEIGHT / (K + rank)
        if doc_id not in rrf_items:
            rrf_items[doc_id] = item

    # 按 RRF 分数排序
    sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    unique = [rrf_items[doc_id] for doc_id, _ in sorted_docs]

    # 4. 映射到 parent chunks
    parent_ids = set()
    for item in unique:
        pid = item['metadata'].get('parent_id')
        if pid:
            parent_ids.add(pid)

    if not parent_ids:
        ranked = rerank(query, unique, top_n=top_k)
        return _filter_results(ranked, top_k)

    # 从 parent collection 按 ID 获取 parent chunks
    parent_collection = get_parent_collection()
    parent_docs = parent_collection.get(ids=list(parent_ids))

    if not parent_docs or not parent_docs['documents']:
        ranked = rerank(query, unique, top_n=top_k)
        return _filter_results(ranked, top_k)

    parent_items = []
    for i in range(len(parent_docs['documents'])):
        parent_items.append({
            "content": parent_docs['documents'][i],
            "metadata": parent_docs['metadatas'][i],
            "score": 1.0,  # 占位，rerank 会重新打分
        })

    # 5. 重排序
    ranked = rerank(query, parent_items, top_n=top_k)

    # 6. 质量过滤：移除分数远低于最高分的噪声 chunk
    return _filter_results(ranked, top_k)
