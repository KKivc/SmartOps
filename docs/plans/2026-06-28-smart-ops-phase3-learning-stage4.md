# SmartOps Phase 3 — 教学稿 阶段 4

> 目标：把 ops-skill-tree 运维知识库变成 AI 可以"翻书"的知识引擎

---

## 先搞懂三个概念

在写代码之前，必须理解 **RAG** 是什么。不然你抄完代码也不知道自己写了什么。

### 概念 1：什么是 RAG？

**RAG = Retrieval Augmented Generation（检索增强生成）**

拆开看：

```
你问："K8s pod CrashLoopBackOff 怎么排查？"

                ┌─ 去知识库翻书 ──→ 找到相关文档
  传统 LLM ──→  AI 凭记忆回答        │
                 （可能瞎编）        ↓
                              把文档塞给 AI
                                │
                                ↓
                          AI 看着文档回答
                          （有依据，不乱说）
```

**RAG = 先查资料，再回答**，不是让 AI 硬想。

就像考试可以**开卷**——不靠背，靠翻书。

### 概念 2：什么是向量和嵌入（Embedding）？

计算机看不懂文字，只看懂数字。

**嵌入（Embedding）** 就是把"文字"变成"数字列表（向量）"的过程。

```
"K8s pod 启动失败"  →  [0.12, 0.87, -0.33, 0.54, ...]  ← 1536 个数字
"磁盘满了怎么办"    →  [-0.45, 0.21, 0.76, -0.12, ...]  ← 1536 个数字
```

**关键：** 意思相近的文字，向量也相近。

```
"K8s pod 启动失败"  ──── 距离近 ────→  "Pod CrashLoopBackOff 排查"
                                          ↑
"磁盘满了怎么办"    ──── 距离远 ────→  不相关
```

这个"距离"叫**余弦相似度**：1 表示完全一样，0 表示完全无关。

### 概念 3：什么是向量数据库（ChromaDB）？

普通数据库存文字，搜的时候用 `LIKE "%关键字%"`。

向量数据库存向量，搜的时候**比距离**，找"意思最接近"的。

```
普通搜索：  LIKE "%磁盘%"    → 只找到包含"磁盘"二字的

向量搜索：  "存储空间不足"  → 找到"磁盘满了""硬盘快满了""分区使用率过高"
```

ChromaDB 就是这样一个向量数据库。我们把 **ops-skill-tree** 的知识点都向量化存进去，用户问问题时也向量化，去 ChromaDB 里找最接近的知识点。

---

## 整体流程

```
① 初始化（一次性的）：
   ops-skill-tree/**/*.md  →  按标题切分  →  每段转向量  →  存入 ChromaDB

② 查询（每次提问）：
   用户问题  →  转向量  →  ChromaDB 找最近似的 5 段  →  塞给 LLM 回答
```

---

## 第一步：克隆知识库

Ops-skill-tree 是一个开源运维知识库，覆盖 Linux/Docker/K8s/中间件/故障案例等。

```bash
cd E:\service-healthcheck
git clone https://gitee.com/shiyq1013/ops-skill-tree.git data/ops-skill-tree
```

看一下结构：

```bash
ls data/ops-skill-tree/
```

应该看到 00、01、02…… 等编号目录，每个目录下是 markdown 文件。

---

## 第二步：理解 ChromaDB 封装

我们要写一个 `llm/rag.py`，里面包含：

| 函数 | 作用 |
|------|------|
| `get_collection()` | 连接 ChromaDB，获取或创建集合 |
| `embed_text(text)` | 调用阿里云 DashScope API，把文字转成向量 |
| `add_document(id, text, metadata)` | 把一段知识点写入 ChromaDB |
| `search_knowledge_base(query, limit)` | 搜索知识库，返回最相关的知识点 |

### 2.1 什么是 Collection？

ChromaDB 里，**Collection = 一个分类的文件夹**。

```
ChromaDB
  ├── collection "ops-knowledge"    ← 我们用的
  ├── collection "other-stuff"
  └── ...
```

可以理解成数据库里的一张表。我们所有运维知识都存在 `ops-knowledge` 这个 collection 里。

### 2.2 先看 ChromaDB 怎么存数据

每一条存入 ChromaDB 的数据有三个部分：

```python
collection.add(
    ids=["唯一ID"],                 # 每条数据一个ID，不能重复
    embeddings=[[0.12, 0.87, ...]], # 文字转成的向量
    documents=["原文内容"],          # 原始文字（查出来直接用）
    metadatas=[{"category": "K8s",  # 附加信息，方便过滤
                "title": "Pod排障"}]
)
```

### 2.3 再看怎么查

```python
results = collection.query(
    query_embeddings=[向量],    # 把用户问题也转成向量
    n_results=5                 # 返回最相似的5条
)
# results 里包含 documents + metadatas + distances
```

---

## 第三步：写 `llm/rag.py`

在 `llm/` 目录下新建 `rag.py`。

### 3.1 开头——导入和常量

```python
"""
ChromaDB 封装 — 运维知识库的向量存储与语义搜索
"""
import os
import chromadb
from openai import OpenAI

# ChromaDB 持久化路径
CHROMA_PATH = "data/chromadb"

# DashScope API 配置（跟 LLM 同一个 API）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL")
```

**解释：**
- `chromadb` — 向量数据库，数据持久化到本地 `data/chromadb/` 目录
- `OpenAI` — 兼容 OpenAI 格式的客户端，用来调阿里云的 embedding API
- `DASHSCOPE_API_KEY` — 环境变量，你之前配过的

### 3.2 连接 ChromaDB

```python
def get_collection():
    """获取或创建 ops-knowledge 集合"""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name="ops-knowledge",
        metadata={"description": "Ops Skill Tree 运维知识库"}
    )
```

**解释：**
- `PersistentClient` — 持久化客户端，数据存在硬盘上，程序重启不丢
- `get_or_create_collection` — 有就用，没有就创建
- 类比：`PersistentClient` = 打开一个文件夹，`get_or_create_collection` = 在文件夹里建一个文件

### 3.3 文本转向量

```python
def embed_text(text):
    """调阿里云 DashScope embedding API，把文本转成向量"""
    client = OpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL
    )
    resp = client.embeddings.create(
        model="qwen3-vl-embedding",
        input=text
    )
    return resp.data[0].embedding
```

**解释：**
- 这就是"嵌入"的核心——把文字变成一堆数字
- `model="qwen3-vl-embedding"` — 阿里云的 embedding 模型
- 返回的 `embedding` 是一个列表，里面有几百到一千多个小数

### 3.4 写入单条文档

```python
def add_document(doc_id, text, metadata):
    """写入一条文档到 ChromaDB"""
    collection = get_collection()
    vector = embed_text(text)
    collection.add(
        ids=[doc_id],
        embeddings=[vector],
        documents=[text],
        metadatas=[metadata]
    )
```

### 3.5 搜索知识库

```python
def search_knowledge_base(query, limit=5):
    """语义搜索知识库，返回最相关的文档片段"""
    collection = get_collection()
    vector = embed_text(query)
    
    results = collection.query(
        query_embeddings=[vector],
        n_results=limit,
        include=["documents", "metadatas", "distances"]
    )
    
    if not results["documents"] or not results["documents"][0]:
        return []
    
    # 把结果组装成方便用的格式
    output = []
    for i in range(len(results["documents"][0])):
        output.append({
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i]  # 距离越小越相似，转成0~1的分数
        })
    return output
```

**解释：**
- `query_embeddings` — 把用户问题转成向量
- `n_results=5` — 取最相似的5条
- `include` — 告诉 ChromaDB 我们要文档内容、元数据、距离分数
- `distances` 是余弦距离（0 = 完全一样，1 = 完全不同），所以用 `1 - distance` 转成直观的分数

---

## 第四步：写知识库初始化脚本

新建 `kb/init_knowledge_base.py`。

这个脚本做三件事：

```
1. 遍历 data/ops-skill-tree/ 下所有 .md 文件
2. 按 ## 标题切分成片段（chunk）
3. 每个片段 → embedding → 写入 ChromaDB
```

### 4.1 为什么需要切分？

ops-skill-tree 里一个文件可能很长，比如《K8s 排障手册》可能有几千字。

如果把整个文件当一条数据存进去：
- 搜索时不够精准——你要问"Pod 启动失败"，但整本书的向量是平均意思
- LLM 上下文有限——几千字塞进去浪费 token

所以按 `##` 标题切分，每个知识点独立：

```
《K8s 排障手册.md》
  ├─ ## Pod 启动失败          → chunk 1
  ├─ ## Node 节点异常          → chunk 2
  ├─ ## Service 无法访问       → chunk 3
  └─ ...
```

### 4.2 编写初始化脚本

```python
"""
知识库初始化脚本 — 把 ops-skill-tree 的 markdown 文件
分片 → embedding → 写入 ChromaDB
"""
import os
import re
import sys

# 把项目根目录加入路径，方便 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.rag import add_document, get_collection

# 知识库路径
KB_PATH = "data/ops-skill-tree"


def chunk_markdown(file_path):
    """
    把 markdown 文件按 ## 二级标题切分成片段
    
    返回: [(标题, 内容), (标题, 内容), ...]
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # 用正则找所有 ## 标题
    # re.M 让 ^ 匹配每一行的开头
    pattern = r"^##\s+(.+)$"
    splits = re.split(pattern, content, flags=re.M)
    
    # re.split 的结果是: [标题前的内容, 标题1, 标题1下的内容, 标题2, 标题2下的内容, ...]
    # 第一个元素是文件开头（在第一个 ## 之前的内容），跳过
    chunks = []
    for i in range(1, len(splits) - 1, 2):
        title = splits[i].strip()
        body = splits[i + 1].strip()
        if body:  # 跳过空片段
            chunks.append((title, body))
    
    return chunks


def get_category(file_path):
    """从文件路径中提取分类名称（目录名）"""
    relative = os.path.relpath(file_path, KB_PATH)
    parts = relative.split(os.sep)
    return parts[0] if len(parts) > 1 else "others"


def main():
    print("🔄 开始初始化知识库...")
    
    # 清空旧数据（可选：如果集合已存在，先删后建）
    collection = get_collection()
    count = collection.count()
    if count > 0:
        print(f"  集合已有 {count} 条数据，跳过初始化")
        print("  如需重新初始化，先手动清空 ChromaDB 的 data/chromadb/ 目录")
        return
    
    # 遍历所有 .md 文件
    md_files = []
    for root, dirs, files in os.walk(KB_PATH):
        for f in files:
            if f.endswith(".md"):
                md_files.append(os.path.join(root, f))
    
    print(f"  找到 {len(md_files)} 个 markdown 文件")
    
    total_chunks = 0
    for file_path in md_files:
        chunks = chunk_markdown(file_path)
        category = get_category(file_path)
        filename = os.path.basename(file_path)
        
        for title, body in chunks:
            # 组合标题 + 正文作为文档内容
            doc_text = f"# {title}\n\n{body}"
            doc_id = f"{category}/{filename}#{title}"
            
            # 写入 ChromaDB
            add_document(
                doc_id=doc_id,
                text=doc_text,
                metadata={
                    "category": category,
                    "title": title,
                    "file": f"{category}/{filename}"
                }
            )
            total_chunks += 1
            
            if total_chunks % 50 == 0:
                print(f"  已处理 {total_chunks} 个片段...")
    
    print(f"✅ 完成！共写入 {total_chunks} 个知识片段到 ChromaDB")


if __name__ == "__main__":
    main()
```

### 4.3 理解 `chunk_markdown` 函数

这个函数用 `re.split` 按 `## 标题` 切分文件。

假设文件内容：

```
# K8s 排障

## Pod 启动失败
Pod 启动失败常见原因：
1. 镜像拉取失败
2. 资源不足
...

## Node 节点异常
节点异常时先检查 kubelet 状态
...
```

`re.split(r"^##\s+(.+)$", content, flags=re.M)` 的结果：

```
索引0: "# K8s 排障\n\n"                    ← 第一个 ## 之前的内容
索引1: "Pod 启动失败"                       ← 第一个标题名
索引2: "\nPod 启动失败常见原因：\n1. ..."    ← 标题下的内容
索引3: "Node 节点异常"                      ← 第二个标题名
索引4: "\n节点异常时先检查 kubelet 状态..."  ← 标题下的内容
```

所以 `chunks` 里取的是 `(1,2), (3,4), (5,6)...`，成对打包。

---

## 验收测试

### 先初始化知识库

```bash
python kb/init_knowledge_base.py
```

看到输出：

```
🔄 开始初始化知识库...
  找到 XX 个 markdown 文件
  已处理 50 个片段...
  已处理 100 个片段...
  ...
✅ 完成！共写入 XXX 个知识片段到 ChromaDB
```

### 再测试搜索

新建 `test_kb.py`：

```python
from llm.rag import search_knowledge_base

results = search_knowledge_base("K8s pod 启动失败怎么排查", limit=3)

for r in results:
    print(f"\n📂 [{r['metadata']['category']}] {r['metadata']['title']}")
    print(f"   相似度: {r['score']:.2f}")
    print(f"   内容: {r['content'][:100]}...")
```

运行：

```bash
python test_kb.py
```

应该返回 ops-skill-tree 里关于 K8s pod 排障的知识点。

---

## 这节课你学到了

| 概念 | 一句话 |
|------|--------|
| RAG | 先查资料再回答，让 AI 不瞎编 |
| Embedding | 把文字变成一堆数字，意思相近的数字也相近 |
| 余弦相似度 | 衡量两个向量"意思"有多接近 |
| ChromaDB | 存向量的数据库，搜"意思"而不是搜"关键字" |
| Collection | 一个分类文件夹，类似数据库表 |
| Chunk | 把大文档切成小片段，方便精准检索 |
| Chunk 策略 | 按 ## 标题切，每个知识点独立 |

---

**现在你来做：**

1. 克隆知识库：`git clone ... data/ops-skill-tree`
2. 在 `llm/` 下新建 `rag.py`，把上面的代码写进去
3. 在 `kb/` 下新建 `init_knowledge_base.py`，把初始化代码写进去
4. 运行 `python kb/init_knowledge_base.py`
5. 建 `test_kb.py` 测试搜索

做完告诉我结果。
