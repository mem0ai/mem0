export const SEARCH_WHEN =
  "before repeating investigation or when earlier decisions, fixes, commands, or results may help";

export const SEARCH_TOOL_DESCRIPTION = `Search memories from earlier work in this repository. Use it ${SEARCH_WHEN}.`;
export const SEARCH_QUERY_DESCRIPTION = "A direct question about earlier work in this repository.";
export const RECALL_HEADING = "Mem0 found these relevant memories from earlier work in this repository:";

export const USER_SEARCH_TOOL_DESCRIPTION = `Search memories from earlier work. Use it ${SEARCH_WHEN}.`;
export const USER_SEARCH_QUERY_DESCRIPTION = "A direct question about earlier work.";
export const USER_RECALL_HEADING = "Mem0 found these relevant memories from earlier work:";

export const PROJECT_MEMORY_INSTRUCTIONS = `Save concise repository facts that will help with future coding work.

A completed change should produce one memory explaining the resulting behavior, where it is implemented when useful, and any important constraints or reasoning. Exploration or accepted decisions may produce separate memories only when they are independently useful.

Use the coding agent's final response for conclusions about current repository behavior. Do not save proposed or recommended changes unless the user accepted them or the coding agent completed them. Treat subagent responses as supporting repository evidence, not as decisions.

Write about the repository, not the user, assistant, session, or task. Do not include test results, documentation updates, release notes, or temporary state.

If nothing useful was established, return no memories.`;

export const PERSONAL_MEMORY_INSTRUCTIONS = `Save concise facts about the user that will help in any repository: preferred tools, package managers, languages, coding style, review and communication preferences, and anything the user explicitly asked to be remembered about themselves.

Write in the third person about the user, not about the repository, the assistant, the session, or the task. Do not save repository facts, project decisions, commands, or what was built.

Never save that the user has no preferences or that nothing was learned. If nothing was learned about the user, return no memories.`;

export const CODING_MEMORY_CATEGORIES: Record<string, string>[] = [
  { project_knowledge: "What the project is and how its code, APIs, data, files, and components work." },
  {
    decisions_and_constraints:
      "Why an approach was chosen, what must remain true, and rules future work must follow.",
  },
  { workflows: "How to run, test, debug, deploy, configure, or otherwise work on the project." },
  { problems_and_fixes: "Bugs, failures, known pitfalls, their causes, and how to fix or avoid them." },
  { results: "Outcomes and measurements from tests, benchmarks, experiments, or investigations." },
];
