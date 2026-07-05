"""
Chroma 封装 — 运维知识库的向量存储与语义搜索
提供ChromaDB 连接、embedding、写入、搜索等功能

"""

import os
import chromadb
from openai import OpenAI


CHROMA_PATH = 'data/chromadb'   #  ChromaDB 自动生成的向量索引

DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
DASHSCOPE_BASE_URL = os.getenv('DASHSCOPE_BASE_URL')

# SiliconFlow（用来调 embedding）
SILICONFLOW_API_KEY = os.getenv('SILICONFLOW_API_KEY')

def get_collection():
     """
     连接chromadb
     获取/创建 knowledge 集合（child chunks）
     """
     client = chromadb.PersistentClient(path=CHROMA_PATH)
     return client.get_or_create_collection(
          name='ops-knowledge',
          metadata={'description': '运维知识库 - child chunks'}
     )

def get_parent_collection():
     """
     获取/创建 parent chunks 集合（按 ## 合并的大片段）
     """
     client = chromadb.PersistentClient(path=CHROMA_PATH)
     return client.get_or_create_collection(
          name='ops-parents',
          metadata={'description': '运维知识库 - parent chunks'}
     )

def embed_text(texts):
    """
    调 SiliconFlow embedding API，把文本转成向量
    支持单条和批量：传字符串返回单个向量，传列表返回多个
    """
    client = OpenAI(
        api_key=SILICONFLOW_API_KEY,
        base_url="https://api.siliconflow.cn/v1"
    )
    # 判断是单条还是批量
    single = isinstance(texts, str)
    input_list = [texts] if single else texts

    resp = client.embeddings.create(
        model="Qwen/Qwen3-Embedding-8B",
        input=input_list
    )
    # resp.data 是按传入顺序返回的
    result = [item.embedding for item in resp.data]
    return result[0] if single else result


def add_documents_batch(docs):
       """批量写入文档到 ChromaDB"""
       if not docs:
             return

       # 1. 提取所有文本 → 一次 API 调用
       texts = [d["text"] for d in docs]
       vectors = embed_text(texts)

       # 2. 批量写入 ChromaDB
       collection = get_collection()
       collection.add(
             ids=[d["id"] for d in docs],
             embeddings=vectors,   # 向量
             documents=texts,      # 文档原文
             metadatas=[d["metadata"] for d in docs]   # 分类信息
       )

def add_parent_documents_batch(docs):
       """批量写入 parent chunks 到 ChromaDB"""
       if not docs:
             return
       texts = [d["text"] for d in docs]
       vectors = embed_text(texts)
       collection = get_parent_collection()
       collection.add(
             ids=[d["id"] for d in docs],
             embeddings=vectors,
             documents=texts,
             metadatas=[d["metadata"] for d in docs]
       )

def search_knowledge_base(query, limit=5):
       """语义搜索知识库，返回最相关的文档片段"""
       collection = get_collection()
       vector = embed_text(query)

       results = collection.query(      # chroma余弦距离计算，排序
             query_embeddings=[vector],  # 用户问题的向量
             n_results=limit,            # 要返回几条
             include=['documents', 'metadatas', 'distances']
       )

       if not results['documents'] or not results['documents'][0]:
             return []
       
       output = []
       for i in range(len(results['documents'][0])):
             output.append({
                   "content": results['documents'][0][i],    # 原文内容
                   "metadata": results['metadatas'][0][i],   # 分类信息
                   # ChromaDB 返回的是距离——0 表示完全一样，1 表示完全无关
                   "score": 1 - results['distances'][0][i]   # 相似度分数
             })
       return output
