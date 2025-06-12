# Jean Memory Agent API: Cookbook

This cookbook provides advanced, real-world examples to demonstrate how to use the Jean Memory Agent API for complex, multi-agent workflows.

## Use Case: Collaborative Research & Summarization

This pattern simulates a common agentic workflow where one or more "Researcher" agents gather information in parallel, and a separate "Summarizer" agent synthesizes that information into a final product.

This demonstrates:
-   **Task-based Isolation:** Using a `task_id` to keep the data for one job separate from others.
-   **Role-based Tagging:** Using `type` and `source` tags to identify which agent created which piece of data.
-   **Handoffs:** How a downstream agent (Summarizer) can reliably retrieve the work products of upstream agents (Researchers).

### Full Example Code

This script is a complete, runnable example. It can be found in the main repository at `examples/test_jean_memory_api.py` and run via the `jean-memory-cli`.

```python
import os
import uuid
import time
from openai import OpenAI
from openmemory.sdk.client import JeanMemoryClient

# --- Configuration ---
# Ensure you have set the following environment variables:
# OPENMEMORY_API_URL (e.g., http://127.0.0.1:8000)
# JEAN_API_TOKEN (your JWT token)
# OPENAI_API_KEY
BASE_URL = os.environ.get("OPENMEMORY_API_URL", "https://api.jeanmemory.com")
AUTH_TOKEN = os.environ.get("JEAN_API_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# --- Initialize Clients ---
memory_client = JeanMemoryClient(base_url=BASE_URL, auth_token=AUTH_TOKEN)
llm_client = OpenAI(api_key=OPENAI_API_KEY)


def research_agent(task_id: str, topic: str):
    """Agent 1: Discovers facts and adds them to memory."""
    print(f"--- [Research Agent] is discovering facts about '{topic}' ---")
    facts = [
        f"{topic} are a type of flowering plant in the nightshade family Solanaceae.",
        "The tomato is the edible berry of the plant Solanum lycopersicum.",
        "The species originated in western South America and Central America.",
        "Tomatoes are a significant source of umami flavor.",
    ]
    for i, fact in enumerate(facts):
        metadata = {"task_id": task_id, "type": "fact", "step": i + 1}
        memory_client.add_tagged_memory(text=fact, metadata=metadata)
        print(f"  - Added fact #{i+1}")
    print("  ✅ Research complete.")


def summarizer_agent(task_id: str, topic: str):
    """Agent 2: Finds facts, uses an LLM to summarize, and stores the summary."""
    print(f"--- [Summarizer Agent] is creating a summary for '{topic}' ---")
    
    # Give a moment for DB to be consistent before reading
    time.sleep(1) 
    facts = memory_client.search_by_tags(filters={"task_id": task_id, "type": "fact"})
    
    if not facts:
        print("  ❌ ERROR: No facts found to summarize.")
        return

    print(f"  - Found {len(facts)} facts to summarize.")
    
    # Use .get('content', '') for safer access
    fact_list = "\\n".join([f"- {mem.get('content', '')}" for mem in sorted(facts, key=lambda x: x['metadata_'].get('step', 0))])
    prompt = f"Please synthesize the following facts about {topic} into a single, concise paragraph:\\n\\n{fact_list}"
    
    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response.choices[0].message.content
    print(f"  - Generated summary.")
    
    metadata = {"task_id": task_id, "type": "summary"}
    memory_client.add_tagged_memory(text=summary, metadata=metadata)
    print("  ✅ Summary complete and stored.")


def run_collaboration_example():
    """Orchestrates the multi-agent workflow."""
    task_id = f"llm_task_{uuid.uuid4()}"
    topic = "Tomatoes"
    print("="*80)
    print(f"🚀 Starting Agent Collaboration Example (Task ID: {task_id}) 🚀")
    print("="*80)
    
    try:
        # Run agent workflows in sequence
        research_agent(task_id, topic)
        summarizer_agent(task_id, topic)

        # Final validation
        print("\\n--- [Orchestrator] Validating final product ---")
        time.sleep(1)
        summaries = memory_client.search_by_tags(filters={"task_id": task_id, "type": "summary"})
        
        assert len(summaries) == 1, f"Expected 1 summary, but found {len(summaries)}."
        print("  - PASSED: Found exactly one final summary artifact.")
        
        final_product = summaries[0].get('content', '')
        print(f"\\nFinal Summary:\\n---\\n{final_product}\\n---")
        
        print("\\n🏆🏆🏆 Agent Collaboration Example Successful! 🏆🏆🏆")

    except Exception as e:
        print(f"\\n❌❌❌ Test Failed: {e} ❌❌❌")

if __name__ == "__main__":
    run_collaboration_example()
``` 