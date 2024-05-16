import os 
from embedchain import App 
from embedchain.config import BaseLlmConfig
from embedchain.llm.premai import PremAILlm

os.environ["PREMAI_API_KEY"]="G91lPIK3XDX7ohwxu6EIlmRDiHQnmO7SMn"
app = App.from_config(config_path="config.yaml")

app.add("https://www.forbes.com/profile/elon-musk")

response = app.query("what is the net worth of Elon Musk?")

print(response)