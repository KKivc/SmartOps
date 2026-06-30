from langchain_openai import ChatOpenAI
import os
from langchain.agents import create_agent
from llm.tools import get_server_list, get_server_status, get_metrics_history, get_logs, search_knowledge_base
import sys
import os
from store.db import get_session
from store.models import  Message, Conversation

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

llm = ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://opencode.ai/zen/go/v1",
    api_key=os.getenv("OPENCODE_API_KEY")
)

prompt = """
你是一个运维专家。回答必须简洁，用短句，不用套模板。

【核心原则】
1. 基于数据，不编造。
2. 建议要具体到命令。
3. 信息不够就说缺什么。

【可用工具】
{tools}
{tool_names}

【格式要求】
- 回答不超过 8 行
- 结论先说，再说理由
- 命令用 ` 括起来
- 不用固定格式，自然表达即可"""

# 创建工具列表
tools = [get_server_list, get_server_status, get_metrics_history, get_logs, search_knowledge_base]

# 创建agent
agent = create_agent(model=llm, tools=tools, system_prompt=prompt)

def chat(conversation_id, user_input):
    """
    历史对话
    短期 记忆
    更新摘要
    """
    history = []
    session = get_session()
    # 取id
    messages = session.query(Message).filter(Message.conversation_id == conversation_id).all()

    for m in messages:
        if m.role == 'human':
            history.append(('human', m.content))
        else:
            history.append(('ai', m.content))

    # 第一次发消息截取摘要
    if len(messages) == 0:
        conv = session.query(Conversation).filter(Conversation.id==conversation_id).first()
        conv.summary = user_input[:15]
    # 添加新问题
    history.append(('human', user_input))

    # 把新问题存入表中
    session.add(Message(conversation_id=conversation_id, role='human', content=user_input))
    session.commit()
    # 把上下文 + 新问题传给agent
    question = agent.invoke({"messages": history})
    # 获取agent新问题的回答
    result = question["messages"][-1].content
    # 将回答保存表中
    session.add(Message(conversation_id=conversation_id, role='ai', content=result))
    
    session.commit()
    session.close()

    return result

if __name__ == '__main__':
    inputs = {"messages": [("human", "那内存呢？")]}
    result = agent.invoke(inputs)
    print(result["messages"][-1].content)
