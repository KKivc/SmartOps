"""
1. 遍历 data/ops-skill-tree/ 下所有 .md 文件
2. 按 ## 标题切分成片段（chunk）
3. 分片 → embedding → 写入 ChromaDB
"""

import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()

# 把项目根目录加入路径,从项目的根目录找模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.rag import add_documents_batch, get_collection

BATCH_SIZE = 50   # 每 50 条调一次 API

KB_PATH = "data/ops-skill-tree"

def chunk_markdown(file_path):
     """
    把 markdown 文件按 ## 二级标题进行分片
    返回: [(标题, 内容), (标题, 内容), ...]
    """
     with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
          content = f.read()

          # 正则找所有 ## 标题
          pattern = r"^##\s+(.+)$"
          splits = re.split(pattern, content, flags=re.M)   # re.split() — 按正则切分字符串

          # splits 结果是: [标题前内容, 标题1, 标题1下内容, 标题2, 标题2下内容, ...]
          chunks = []
          for i in range(1, len(splits) - 1, 2):
               title = splits[i].strip()    # 奇数索引放标题
               body = splits[i+1].strip()   # 偶数索引放内容
               if body:
                    chunks.append((title, body))
            
          return chunks
     
def main():
     print("🔄 开始初始化知识库...")

     collection = get_collection()

     # 获取已有 doc_id 集合，用于去重
     existing_ids = set()
     if collection.count() > 0:
        existing = collection.get(limit=99999)
        existing_ids = set(existing["ids"])
        print(f"  已有 {len(existing_ids)} 条，跳过重复")

     # 遍历所有 .md 文件
     md_files = []
     for root, dirs, files in os.walk(KB_PATH):
          for f in files:
               if f.endswith('.md'):
                    md_files.append(os.path.join(root, f))

     print(f"  找到 {len(md_files)} 个 markdown 文件")

     batch = []   # 攒一批
     new_count = 0
     seen_in_run = set()   # 本轮已处理过的 ID，防同一批重复
     for file_path in md_files:
          chunk = chunk_markdown(file_path)
          relative = os.path.relpath(file_path, KB_PATH)
          category = relative.split(os.sep)[0]
          filename = os.path.basename(file_path)
          chunk_index = 0     # 同一文件内计数器，防止标题重复

          for title, body in chunk:
               doc_text = f"# {title}\n\n{body}"
               doc_id = f"{category}/{filename}#{title}"
               chunk_index += 1

               # 数据库已有或本轮已处理 → 跳过
               if doc_id in existing_ids or doc_id in seen_in_run:
                    # 加序号再试一次
                    doc_id = f"{category}/{filename}#{title}_{chunk_index}"
                    if doc_id in existing_ids or doc_id in seen_in_run:
                         continue

               seen_in_run.add(doc_id)

               batch.append({
                    "id": doc_id,
                    "text": doc_text,
                    "metadata": {"category": category, "title": title, "file": f"{category}/{filename}"}
               })

               # 攒够 BATCH_SIZE 条就发一批
               if len(batch) >= BATCH_SIZE:
                    add_documents_batch(batch)
                    new_count += len(batch)
                    print(f"  已处理 {new_count} 个新片段...")
                    batch = []

     # 最后剩下不足一批的零头
     if batch:
          add_documents_batch(batch)
          new_count += len(batch)

     print(f"✅ 完成！新增 {new_count} 个知识片段到 ChromaDB（共 {collection.count()} 条）")

if __name__ == '__main__':
     main()