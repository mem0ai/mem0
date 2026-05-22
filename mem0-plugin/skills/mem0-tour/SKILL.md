---
name: mem0-tour
description: >
  Show what mem0 knows about the current project. Dumps top memories
  grouped by category. Power-user-friendly proof of value.
  TRIGGER: user runs /mem0:tour, or asks "what do you know about this project",
  "show me my memories", "what has mem0 stored".
---

# Mem0 Project Tour

Show the user what mem0 has stored for the current project.

## Execution

1. Run the following `search_memories` calls in parallel (all with the active `user_id` and `metadata.project_id`):

   - `query="architecture decisions"`, `filters={"AND": [{"user_id": "<id>"}, {"metadata": {"project_id": "<pid>"}}, {"metadata": {"type": "decision"}}]}`, `limit=5`
   - `query="anti patterns failures"`, `filters={"AND": [{"user_id": "<id>"}, {"metadata": {"project_id": "<pid>"}}, {"metadata": {"type": "anti_pattern"}}]}`, `limit=5`
   - `query="task learnings strategies"`, `filters={"AND": [{"user_id": "<id>"}, {"metadata": {"project_id": "<pid>"}}, {"metadata": {"type": "task_learning"}}]}`, `limit=5`
   - `query="coding conventions"`, `filters={"AND": [{"user_id": "<id>"}, {"metadata": {"project_id": "<pid>"}}, {"metadata": {"type": "convention"}}]}`, `limit=5`
   - `query="user preferences"`, `filters={"AND": [{"user_id": "<id>"}, {"metadata": {"project_id": "<pid>"}}, {"metadata": {"type": "user_preference"}}]}`, `limit=5`
   - `query="project profile"`, `filters={"AND": [{"user_id": "<id>"}, {"metadata": {"project_id": "<pid>"}}, {"metadata": {"type": "project_profile"}}]}`, `limit=5`
   - `query="tooling setup environment"`, `filters={"AND": [{"user_id": "<id>"}, {"metadata": {"project_id": "<pid>"}}, {"metadata": {"type": "environmental"}}]}`, `limit=5`

2. Group results by category. For each category with results, print:

   ```
   ## <category_name> (<count> memories)
   - <memory_content_truncated_to_100_chars> (score: <similarity_score>)
   - ...
   ```

3. For categories with zero results, print: `<category_name>: (empty)`

4. Print totals at the end:
   ```
   ---
   Total: <N> memories across <M> categories for project <project_id>
   ```

5. If ALL categories are empty, print:
   ```
   No memories stored yet for project <project_id>.
   Run /mem0:onboard to import project files, or start working — mem0 captures learnings automatically.
   ```
