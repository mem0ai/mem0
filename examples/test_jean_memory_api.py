import os
import uuid
import time
import random
import pytest
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from openmemory.sdk.client import JeanMemoryClient

# --- Configuration & Fixtures ---

@pytest.fixture(scope="module")
def memory_client():
    """Provides an authenticated JeanMemoryClient for tests."""
    base_url = os.environ.get("OPENMEMORY_API_URL", "http://127.0.0.1:8000")
    auth_token = os.environ.get("JEAN_API_TOKEN")
    
    # In local tests, a dummy token can be used if USER_ID is set
    if not auth_token and os.environ.get("USER_ID"):
        auth_token = "dummy-token-for-local-dev"

    if not auth_token:
        pytest.fail("JEAN_API_TOKEN (or USER_ID for local tests) must be set.")
        
    return JeanMemoryClient(base_url=base_url, auth_token=auth_token)

@pytest.fixture(scope="module")
def llm_client():
    """Provides an OpenAI client, skipping tests if the key is not available."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set, skipping LLM-dependent tests.")
    return OpenAI(api_key=api_key)

# --- Test Cases ---

def test_add_and_search(memory_client):
    """Tests basic memory addition and retrieval."""
    task_id = f"simple_test_{uuid.uuid4()}"
    client_name = "test_app_basic"
    
    # Add a memory
    mem_text = "This is a basic test memory."
    mem_meta = {"task_id": task_id, "test": "basic"}
    response = memory_client.add_tagged_memory(text=mem_text, metadata=mem_meta, client_name=client_name)
    assert "memory_id" in response
    
    # Search for the memory
    time.sleep(1) # Allow for DB commit
    results = memory_client.search_by_tags(filters={"task_id": task_id}, client_name=client_name)
    assert len(results) == 1
    assert results[0]['content'] == mem_text
    assert results[0]['metadata_'] == mem_meta

def test_industrial_swarm_concurrency(memory_client):
    """Tests the API's ability to handle concurrent writes from multiple agents."""
    task_id = f"swarm_test_{uuid.uuid4()}"
    client_name = "test_app_swarm"
    num_agents = 5
    
    def agent_worker(agent_id):
        text = f"Agent {agent_id}'s report for task {task_id}."
        meta = {"task_id": task_id, "agent_id": agent_id}
        try:
            memory_client.add_tagged_memory(text=text, metadata=meta, client_name=client_name)
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=num_agents) as executor:
        futures = [executor.submit(agent_worker, i) for i in range(num_agents)]
        results = [f.result() for f in as_completed(futures)]
    
    assert all(results), "Not all agent workers succeeded."
    
    # Validate
    time.sleep(1)
    all_memories = memory_client.search_by_tags(filters={"task_id": task_id}, client_name=client_name)
    assert len(all_memories) == num_agents

def test_agent_collaboration_workflow(memory_client, llm_client):
    """Tests a multi-step, LLM-driven agent collaboration workflow."""
    task_id = f"llm_collab_test_{uuid.uuid4()}"
    client_name = "test_app_collab"
    topic = "The Planet Mars"

    # 1. Researcher Agent
    facts = [
        "Mars is the fourth planet from the Sun.",
        "It is known as the Red Planet due to its iron oxide surface.",
        "Mars has two small moons, Phobos and Deimos.",
    ]
    for fact in facts:
        memory_client.add_tagged_memory(
            text=fact, 
            metadata={"task_id": task_id, "type": "fact"},
            client_name=client_name
        )

    # 2. Summarizer Agent
    time.sleep(1)
    retrieved_facts = memory_client.search_by_tags(filters={"task_id": task_id, "type": "fact"}, client_name=client_name)
    assert len(retrieved_facts) == len(facts)
    
    fact_list = "\\n".join([f"- {mem['content']}" for mem in retrieved_facts])
    prompt = f"Summarize these facts into one sentence: {fact_list}"
    response = llm_client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    summary = response.choices[0].message.content
    
    memory_client.add_tagged_memory(
        text=summary,
        metadata={"task_id": task_id, "type": "summary"},
        client_name=client_name
    )

    # 3. Validation
    time.sleep(1)
    final_summary = memory_client.search_by_tags(filters={"task_id": task_id, "type": "summary"}, client_name=client_name)
    assert len(final_summary) == 1
    assert "Mars" in final_summary[0]['content'] 