import random
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class ValidationReport(BaseModel):
    total_samples: int
    retrieval_rate: float
    failures: List[Dict[str, Any]] = Field(default_factory=list)

class MemoryValidator:
    def __init__(self, memory_instance):
        self.memory = memory_instance

    def _generate_query_from_memory(self, memory_text: str) -> str:
        # Future improvement: Use LLM to generate diverse queries
        return memory_text 

    def validate(self, user_id: str, sample_size: int = 10, top_k: int = 5) -> ValidationReport:
        # 1. Fetch all memories
        all_memories = self.memory.get_all(user_id=user_id)
        
        # Normalize input to list
        memory_list = []
        if isinstance(all_memories, dict):
            if "results" in all_memories:
                memory_list = all_memories["results"]
            elif "memories" in all_memories:
                memory_list = all_memories["memories"]
            else:
                memory_list = list(all_memories.values())
        elif isinstance(all_memories, list):
            memory_list = all_memories
        
        if not memory_list:
            return ValidationReport(total_samples=0, retrieval_rate=0.0)

        # 2. Sample memories
        target_size = min(len(memory_list), sample_size)
        sampled_memories = random.sample(memory_list, target_size)

        passed_count = 0
        failures = []

        for mem in sampled_memories:
            # Extract text from original memory
            original_text = ""
            original_id = None
            
            if isinstance(mem, dict):
                original_text = mem.get("memory", mem.get("text", str(mem)))
                original_id = mem.get("id")
            else:
                original_text = str(mem)
                original_id = str(hash(original_text))

            query = self._generate_query_from_memory(original_text)
            
            # Search
            try:
                raw_results = self.memory.search(query, user_id=user_id, limit=top_k)
            except TypeError:
                raw_results = self.memory.search(query, user_id=user_id, top_k=top_k)

            # Normalize search results
            search_results = []
            if isinstance(raw_results, dict):
                if "results" in raw_results:
                    search_results = raw_results["results"]
                elif "memories" in raw_results:
                    search_results = raw_results["memories"]
                else:
                    search_results = list(raw_results.values())
            elif isinstance(raw_results, list):
                search_results = raw_results
            
            # 3. Verify results
            found = False
            retrieved_items = []

            for result in search_results:
                res_text = ""
                res_id = None
                
                if isinstance(result, dict):
                    res_text = result.get("memory", result.get("text", str(result)))
                    res_id = result.get("id")
                elif isinstance(result, str):
                    res_text = result
                
                retrieved_items.append(res_text)
                
                # Check for match (ID or Text content)
                if original_id and res_id and original_id == res_id:
                    found = True
                    break
                # Loose text matching
                if original_text.strip().lower() in res_text.strip().lower():
                    found = True
                    break
                if res_text.strip().lower() in original_text.strip().lower():
                    found = True
                    break

            if found:
                passed_count += 1
            else:
                failures.append({
                    "memory_id": original_id,
                    "original_text": original_text,
                    "used_query": query,
                    "retrieved_results": retrieved_items
                })

        retrieval_rate = passed_count / target_size if target_size > 0 else 0.0
        
        return ValidationReport(
            total_samples=target_size,
            retrieval_rate=retrieval_rate,
            failures=failures
        )