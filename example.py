from embedchain import App, OpenSourceApp
from embedchain.config import QueryConfig

query_config = QueryConfig(stream_response=True)

app = OpenSourceApp()
app.add("web_page", "https://www.myyellow.com/us/en/services")
resp = app.query("What are different services provided by Yellow?")

for chunk in resp:
    print(chunk, end="", flush=True)