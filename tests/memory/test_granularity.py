import os
os.environ["OPENAI_API_KEY"] = "sk-" + "a"*48

from unittest.mock import MagicMock, patch
from mem0.configs.base import MemoryConfig
from mem0.configs.prompts import CHUNK_EXTRACTION_PROMPT

# Mock factories before importing Memory to avoid API key requirements
with patch('mem0.utils.factory.EmbedderFactory.create'), \
     patch('mem0.utils.factory.VectorStoreFactory.create'), \
     patch('mem0.utils.factory.LlmFactory.create'), \
     patch('mem0.utils.factory.RerankerFactory.create'), \
     patch('mem0.memory.main.SQLiteManager'), \
     patch('mem0.memory.main.capture_event'):
    from mem0.memory.main import Memory

def test_entry_mode_selection():
    config = MemoryConfig()
    
    with patch('mem0.memory.main.VectorStoreFactory.create'):
        mem = Memory(config)
    
    mem.llm = MagicMock()
    mem.llm.generate_response.return_value = '{"facts": ["fact1"]}'
    mem.embedding_model = MagicMock()
    mem.vector_store = MagicMock()
    
    # 1. Test DEFAULT (fact)
    mem.add("Test", user_id="test")
    call_args = mem.llm.generate_response.call_args_list[0]
    messages = call_args[1].get('messages') or call_args[0][0]
    system_prompt = messages[0]['content']
    assert "fact" in system_prompt.lower()
    assert "chunk" not in system_prompt.lower()

    # 2. Test CHUNK mode via config
    mem.llm.reset_mock()
    mem.config.entry_mode = "chunk"
    mem.add("Test", user_id="test")
    call_args = mem.llm.generate_response.call_args_list[0]
    messages = call_args[1].get('messages') or call_args[0][0]
    system_prompt = messages[0]['content']
    assert "Document Information Splitter" in system_prompt

    # 3. Test CHUNK mode via override
    mem.llm.reset_mock()
    mem.config.entry_mode = "fact"
    mem.add("Test", user_id="test", entry_mode="chunk")
    call_args = mem.llm.generate_response.call_args_list[0]
    messages = call_args[1].get('messages') or call_args[0][0]
    system_prompt = messages[0]['content']
    assert "Document Information Splitter" in system_prompt

if __name__ == "__main__":
    test_entry_mode_selection()
    print("Test Granularity: OK")
