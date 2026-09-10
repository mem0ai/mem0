# Changelog

## 0.3.2

- Add explicit save, project-scoped list, and resume through shared local resources in `~/.mem0/handoffs/`. Every plugin uses one converter, validator, and resource store; memory extraction is not a transcript source.
- Installable plugins share one pinned runtime cache through a small launcher. First use downloads the exact GitHub commit and verifies SHA-256 digests; subsequent uses verify and reuse the local cache. No transcript is uploaded to GitHub.
- Preserve the session title, project, readable compaction context, supported images, and completed tool calls/results. Hidden reasoning and harness configuration are excluded. Unsupported records, opaque compaction, and unfinished responses fail explicitly.
- Requires Python 3.11+. Pi save additionally requires Node.js 22.19+ for its native SDK; list/resume work on Node.js 20. Other source formats may require an explicit completed transcript, directory, and title.
- Handoff needs no destination CLI, model call, or Mem0 credentials. Resources are private, uniquely named files; saving preserves full supported context and resume returns it as historical evidence without replaying tools.
- Live host checks: align the handoff skill’s shell permission with its quoted command; accept Codex harness/usage metadata without importing it as conversation; resolve DeepSeek attachment storage through its native optional-service API.
- Replace strict before-answer and repeated-search instructions with focused optional retrieval. Existing context can answer the question without another search. Search scoping, retrieval limits, and capture scheduling are unchanged.
