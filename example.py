from embedchain import App, OpenSourceApp
from embedchain.config import ChatConfig
import time

app = App()

#app.add("youtube_video", "https://www.youtube.com/watch?v=3qHkcs3kG44")
#app.add("pdf_file", "https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf")
app.add("web_page", "https://nav.al/feedback")
app.add("web_page", "https://nav.al/agi")

# app.add_local("qna_pair", ("Who is Naval Ravikant?", "Naval Ravikant is an Indian-American entrepreneur and investor."))


resp = app.chat("What did Naval achieve in his lifetime?", ChatConfig(stream_response=True))


for chunk in resp:
    print(chunk, end="", flush=True)