"""
1. 遍历 data/ops-skill-tree/ 下所有 .md 文件
2. 按 ## 标题切分成片段（chunk）
3. 分片 → embedding → 写入 ChromaDB
4. 同时构建 parent chunks 写入 parent collection
"""
import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()

# 把项目根目录加入路径,从项目的根目录找模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.rag import add_documents_batch, add_parent_documents_batch, get_collection, get_parent_collection

BATCH_SIZE = 200   # 每 200 条调一次 API

KB_PATH = "data/ops-skill-tree"

def parse_heading(line):
     """
     判断标题行，
     如果是则返回 (level, title)，
     否则返回 None
     """
     stripped = line.lstrip()
     level = stripped.count('#')   # 标题级别
     title = stripped.lstrip('#').strip()    # 标题内容
     if level != 0 and title:
          return (level, title)
     else:
          return None

def stack_to_path(stack):
     """
     把标题栈转成路径字符串
     """
     return " > ".join(stack)

def chunk_markdown(file_path):
     """
    把 markdown 文件按 # 一级标题进行分片,父chunk，子chunk
    返回: [(标题, 内容), (标题, 内容), ...]
    """

     with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
          content = f.read()

          stack = []
          chunks = []
          current_body = []   # 当前chunk的内容
          for line in content.splitlines():
               # 匹配 标题
               heading = parse_heading(line)
               if heading:
                    level, title = heading

                    #  如果有内容
                    if current_body:
                         doc_text = stack_to_path(stack) + "\n" + "\n".join(current_body)
                         body = "\n".join(current_body)
                         chunk_title = title if not stack else stack[-1]
                         chunks.append((chunk_title, body, doc_text))
                         current_body = []

                    # 同级/上级标题出现，先出栈
                    while len(stack) > level - 1:
                         stack.pop()

                    # 入栈新标题
                    stack.append(title)

               else:
                    # 内容行没有标题、不是空行、不是分隔线，加入当前chunk内容
                    stripped = line.strip()
                    if stripped != "" and stripped != "---":
                         current_body.append(line)

          # 循环结束，收尾flush
          if current_body:
               doc_text = stack_to_path(stack) + "\n" + "\n".join(current_body)
               body = "\n".join(current_body)
               chunk_title = stack[-1] if stack else ""
               chunks.append((chunk_title, body, doc_text))

          return chunks

def build_parents_from_chunks(chunks, category, filename):
     """
    将 child chunks 按 level-2 标题合并为 parent chunks
    返回: [{"id": ..., "text": ..., "metadata": ...}, ...]
    """
     if not chunks:
          return []

     parents = []
     current_group = []   # (title, body, doc_text)
     current_key = None

     for title, body, doc_text in chunks:
          # doc_text 格式: "标题路径\n正文内容"，只取第一行路径部分
          path_only = doc_text.split("\n")[0]
          path_parts = path_only.split(" > ")
          # 取 level-2 作为 parent key（标题栈的第二层）
          parent_key = path_parts[1] if len(path_parts) >= 2 else path_parts[0]

          if parent_key != current_key and current_group:
               # 合并当前 parent
               merged_parts = []
               for t, b, dt in current_group:
                    merged_parts.append(f"[{t}]\n{b}")
               parent_content = "\n\n".join(merged_parts)
               parent_id = f"parent:{category}/{filename}#{current_key}"
               parents.append({
                    "id": parent_id,
                    "text": parent_content,
                    "metadata": {
                         "category": category,
                         "title": current_key,
                         "file": f"{category}/{filename}",
                         "type": "parent",
                    },
                    "key": current_key,
               })
               current_group = []

          current_key = parent_key
          current_group.append((title, body, doc_text))

     # Flush last group
     if current_group and current_key:
          merged_parts = []
          for t, b, dt in current_group:
               merged_parts.append(f"[{t}]\n{b}")
          parent_content = "\n\n".join(merged_parts)
          parent_id = f"parent:{category}/{filename}#{current_key}"
          parents.append({
               "id": parent_id,
               "text": parent_content,
               "metadata": {
                    "category": category,
                    "title": current_key,
                    "file": f"{category}/{filename}",
                    "type": "parent",
               },
               "key": current_key,
          })

     return parents

def get_parent_key(title, doc_text):
     """从 chunk 信息中提取 parent key"""
     path_only = doc_text.split("\n")[0]
     path_parts = path_only.split(" > ")
     return path_parts[1] if len(path_parts) >= 2 else path_parts[0]


def main():
     print("\n开始初始化知识库...\n")

     # ========== Child Collection ==========
     collection = get_collection()
     existing_ids = set()
     if collection.count() > 0:
        existing = collection.get(limit=99999)
        existing_ids = set(existing["ids"])
        print(f"  已有 {len(existing_ids)} 条 child chunks，跳过重复")

     # ========== Parent Collection ==========
     parent_collection = get_parent_collection()
     parent_existing_ids = set()
     if parent_collection.count() > 0:
        parent_existing = parent_collection.get(limit=99999)
        parent_existing_ids = set(parent_existing["ids"])
        print(f"  已有 {len(parent_existing_ids)} 条 parent chunks，跳过重复")

     # 遍历所有 .md 文件
     md_files = []
     for root, dirs, files in os.walk(KB_PATH):
          for f in files:
               if f.endswith('.md'):
                    md_files.append(os.path.join(root, f))

     print(f"  找到 {len(md_files)} 个 markdown 文件\n")

     # Batches
     child_batch = []
     parent_batch = []
     child_new_count = 0
     parent_new_count = 0
     child_seen = set()
     parent_seen = set()

     for file_path in md_files:
          chunks = chunk_markdown(file_path)
          relative = os.path.relpath(file_path, KB_PATH)
          category = relative.split(os.sep)[0]
          filename = os.path.basename(file_path)
          chunk_index = 0

          # ---- Build and store child chunks ----
          for title, body, doc_text in chunks:
               doc_id = f"{category}/{filename}#{title}"
               chunk_index += 1

               if doc_id in existing_ids or doc_id in child_seen:
                    doc_id = f"{category}/{filename}#{title}_{chunk_index}"
                    if doc_id in existing_ids or doc_id in child_seen:
                         continue

               child_seen.add(doc_id)

               # parent_id 用于检索后回查 parent
               parent_key = get_parent_key(title, doc_text)
               parent_id = f"parent:{category}/{filename}#{parent_key}"

               child_batch.append({
                    "id": doc_id,
                    "text": doc_text,
                    "metadata": {
                         "category": category,
                         "title": title,
                         "file": f"{category}/{filename}",
                         "type": "child",
                         "parent_id": parent_id,
                    }
               })

               if len(child_batch) >= BATCH_SIZE:
                    add_documents_batch(child_batch)
                    child_new_count += len(child_batch)
                    print(f"  已处理 {child_new_count} 个 child 片段...")
                    child_batch = []

          # ---- Build and store parent chunks ----
          parents = build_parents_from_chunks(chunks, category, filename)
          for p in parents:
               if p["id"] in parent_existing_ids or p["id"] in parent_seen:
                    continue
               parent_seen.add(p["id"])
               parent_batch.append(p)

               if len(parent_batch) >= BATCH_SIZE:
                    add_parent_documents_batch(parent_batch)
                    parent_new_count += len(parent_batch)
                    print(f"  已处理 {parent_new_count} 个 parent 片段...")
                    parent_batch = []

     # Flush remaining
     if child_batch:
          add_documents_batch(child_batch)
          child_new_count += len(child_batch)
     if parent_batch:
          add_parent_documents_batch(parent_batch)
          parent_new_count += len(parent_batch)

     print(f"\n完成！新增 {child_new_count} 个 child chunks（共 {collection.count()} 条）")
     print(f"完成！新增 {parent_new_count} 个 parent chunks（共 {parent_collection.count()} 条）")

if __name__ == '__main__':
     main()
