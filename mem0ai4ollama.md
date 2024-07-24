# mem0ai适配ollama

## 适配ollama

- mem0最近非常红火，短短几天功夫，github上的星就飙到了16.9K。[官方文档](https://docs.mem0.ai)中有OpenAI的例子，但是对于同样风头正盛的[ollama](https://ollama.ai/)，却没有相关的例子。检查了下[项目仓库](https://github.com/mem0ai/mem0)中的代码，发现ollama适配工作并未完成。于是自己动手丰衣足食，花了点功夫，适配了ollama。

## 环境说明

- python 3.10

- ollama 0.2.8
  - 假设安装在本机
  - 提前准备ollama模型mistral-nemo和nomic-embed-text

## 相关步骤

- 拉取mem0ai仓库的fork

```bash
git clone https://github.com/Galileo2017/mem0.git
```

- 安装依赖

```bash
pip install ollama
pip install mem0ai
```

- 替换mem0ai安装包

```text
将fork仓库中mem0/mem0目录下所有的文件和目录复制到python安装包目录Lib/site-packages/mem0中进行替换。
```

- 示例脚本

```test.py
import os
from mem0 import Memory


# 配置用户编码
USER_ID = "deshraj"

# ollama配置
# 设置环境变量OLLAMA_HOST=http://127.0.0.1:11434
os.environ['OLLAMA_HOST']="http://127.0.0.1:11434"

config = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "mistral-nemo",
            "temperature": 0.2,
            "max_tokens": 1500
        }
    },
    "embedder":{
        "provider": "ollama"
    },
    "embedding_model_dims":768
}

# 初始化mem0 
memory = Memory.from_config(config)

# 设置用户数据
USER_DATA = """
About me
- I'm Deshraj Yadav, Co-founder and CTO at Mem0 (f.k.a Embedchain). I am broadly interested in the field of Artificial Intelligence and Machine Learning Infrastructure.
- Previously, I was Senior Autopilot Engineer at Tesla Autopilot where I led the Autopilot's AI Platform which helped the Tesla Autopilot team to track large scale training and model evaluation experiments, provide monitoring and observability into jobs and training cluster issues.
- I had built EvalAI as my masters thesis at Georgia Tech, which is an open-source platform for evaluating and comparing machine learning and artificial intelligence algorithms at scale.
- Outside of work, I am very much into cricket and play in two leagues (Cricbay and NACL) in San Francisco Bay Area.
"""

# 添加用户数据至mem0中
memory.add(USER_DATA, user_id=USER_ID)
print("User data added to memory.")

# 设置查询命令
command = "Find papers on arxiv that I should read based on my interests."

relevant_memories = memory.search(command, user_id=USER_ID, limit=3)
relevant_memories_text = '\n'.join(mem['text'] for mem in relevant_memories)
print(f"Relevant memories:")
print(relevant_memories_text)
```

## 问题处理

- 使用ollama生成的embedding保存时会报错:

```text
ValueError: shapes (0,512) and (768,) not aligned: 512 (dim 1) != 768 (dim 0)
```

原因分析：

```python
mem0\memory\main.py
 self.vector_store.create_col(
            name=self.collection_name, vector_size=self.embedding_model.dims
        )
```

用embedding_model.dims初始化vector_size,与实际模型的dims不一样导致报错，可以添加配置"embedding_model_dims":768解决问题。
