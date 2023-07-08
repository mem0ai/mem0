import os
from embedchain import App
from embedchain.config import InitConfig, AddConfig, QueryConfig
from chromadb.utils import embedding_functions
from string import Template

app = App()
app.reset()

app = App()

# app.add_local('text', "lorem ipsum")

# print("##### Without history #####")
# response = app.query("Can you explain that in more detail?")
# print(response)

# history = ['User: Are dolphins fish?', 'Bot: Dolphins are not actually fish.']
# config = QueryConfig(history=history)
# print("##### With history #####")
# print(app.dry_run("Can you explain that in more detail?", config))
# response = app.query("Can you explain that in more detail?", config)
# print("Answer: ", response)

response = app.chat("My name is John Doe. Can you remember that?")
print("Answer: ", response)
response = app.chat("What is my name?")
print("Answer: ", response)