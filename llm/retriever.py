"""
BM25 + 向量 + RRF 统一检索（Parent-Child Retrieval）
"""
from llm.rag import embed_text, get_collection, get_parent_collection
from rank_bm25 import BM25Okapi
import jieba
import os
import requests

SILICONFLOW_API_KEY = os.getenv('SILICONFLOW_API_KEY')

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
    # 获取所有文档
    docs = collection.get(limit=99999)
    texts = docs['documents']
    # 构建 BM25 索引
    tokenized = [list(jieba.cut(text)) for text in texts]
    bm25 = BM25Okapi(tokenized)
    _bm25 = bm25
    _doc_ids = docs['ids']
    _doc_metadatas = docs['metadatas']
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
    """
    if not ranked:
        return []
    top_score = ranked[0]["score"]
    threshold = max(top_score * 0.1, 0.05)
    filtered = [r for r in ranked if r["score"] >= threshold]
    return filtered[:top_k]


def hybrid_search(query, top_k=5):
    """
    搜索 child chunks → 映射到 parent chunks → 重排序 → 返回
    """
    child_collection = get_collection()

    # 1. 向量检索（在 child collection 上）
    vector = embed_text(query)
    vector_results = child_collection.query(
        query_embeddings=[vector],
        n_results=top_k + 2,
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
    bm25_results = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)[:top_k + 2]

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
