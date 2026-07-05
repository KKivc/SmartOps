from datasets import Dataset
from langchain_openai import ChatOpenAI
import os

dataset = Dataset.from_list([{
    "question": "top 命令怎么看 CPU",
    "answer": "运行 top，看 %%CPU 列",
    "contexts": ["top 命令，%%CPU 列显示进程 CPU 占用率"],
}])

llm = ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://opencode.ai/zen/go/v1",
    api_key=os.getenv("OPENCODE_API_KEY"),
)

from ragas.metrics import faithfulness
metrics = [faithfulness]

# 这步会报错吗？
from ragas import evaluate
result = evaluate(dataset, metrics=metrics, llm=llm)
print(result)