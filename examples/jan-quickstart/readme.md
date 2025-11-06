Mem0 Quickstart using model hosted locally by JanAI

** Jan **
1. [Install Jan](https://www.jan.ai/) on your computer
2. Download openai_gpt-oss-20b-IQ2_M from the [Jan hub](https://www.jan.ai/docs/desktop/manage-models#adding-models)
3. Run openai_gpt-oss-20b-IQ2_M in a Jan session by clicking on the "Use" button next to the downloaded model's name
4. Start a local Jan server as per [these instructions](https://www.jan.ai/docs/desktop/api-server).
Set the api key to be "JanServer"!!

Note that the model must support function calling!

** Quickstart using Jan **

1. Test that the model is accessible via Jan using its direct http APIs
  ```
  python3 llmquery.py
  ```
  
2. Test that a memory can be created, stored and retrieved using mem0
  
Run the quickstart
  ```
  python3 quickstart_jan.py
  ```