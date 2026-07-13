from mem0.llms.azure_openai import AzureOpenAILLM
llm = AzureOpenAILLM()
messages = [{"role": "user", "content": "I need financial assistance."}]
# The method mutates the content globally
rewritten = llm._rewrite_assistant_keyword(messages)
print(rewritten[-1]["content"])
