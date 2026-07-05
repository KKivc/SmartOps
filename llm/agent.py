"""Agent 入口 — 对外暴露 chat() 接口，内部转发 LangGraph Supervisor

与上游调用方保持签名兼容：
  chat(conversation_id, user_input) → str
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store.db import get_session
from store.models import Conversation, Message
from llm.supervisor import build_supervisor

# 编译 Supervisor（单例）
_supervisor = build_supervisor()


def chat(conversation_id: int, user_input: str) -> str:
    """
    处理用户消息，通过 Supervisor 多 Agent 协作返回回答

    流程：
      1. 加载对话历史
      2. 存入用户消息
      3. 调用 Supervisor StateGraph
      4. 保存回答 → 返回
    """
    session = get_session()

    # 1. 加载历史消息
    old_messages = session.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.id).all()

    # 2. 首条消息更新摘要
    if len(old_messages) == 0:
        conv = session.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        if conv:
            conv.summary = user_input[:15]

    # 3. 保存用户消息
    session.add(Message(conversation_id=conversation_id, role="human", content=user_input))
    session.commit()

    # 4. 构建 Supervisor 输入状态
    initial_state = {
        "messages": [("human", user_input)],
        "next": "supervisor",
        "intermediate_results": {},
        "final_report": "",
        "iteration": 0,
    }

    # 5. 调用 Supervisor
    try:
        final_state = _supervisor.invoke(initial_state)
        result = final_state.get("final_report", "")
        # 如果 final_report 为空，尝试从 intermediate_results 生成回复
        if not result:
            ir = final_state.get("intermediate_results", {})
            if ir:
                from llm.supervisor import _auto_report
                result = _auto_report(ir)
            else:
                # Supervisor 未调度任何 Worker，直接用 LLM 回答
                from langchain_openai import ChatOpenAI
                import os
                llm = ChatOpenAI(
                    model="deepseek-v4-flash",
                    base_url="https://opencode.ai/zen/go/v1",
                    api_key=os.getenv("OPENCODE_API_KEY"),
                )
                resp = llm.invoke([("human", user_input)])
                result = resp.content
    except Exception as e:
        import traceback
        print(f"[agent] 诊断异常: {e}\n{traceback.format_exc()}", flush=True)
        result = f"【系统错误】诊断过程异常：{e}"

    # 6. 保存 AI 回答
    session.add(Message(conversation_id=conversation_id, role="ai", content=result))
    session.commit()
    session.close()

    return result
