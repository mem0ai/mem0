# Changelog

## 0.3.2

- Add explicit session handoff to a new Codex task. Host readers supply native active context to one common converter, validator, importer, and recovery implementation; memory extraction is not a transcript source.
- Installable plugins share one pinned runtime cache through a small launcher. First use downloads the exact GitHub commit and verifies SHA-256 digests; subsequent uses verify and reuse the local cache. No transcript is uploaded to GitHub.
- Preserve the session title, project, readable compaction context, supported images, and completed tool calls/results. Hidden reasoning and harness configuration are excluded. Unsupported records, opaque compaction, and unfinished responses fail explicitly.
- Requires Python 3.11+ and a signed-in local Codex CLI supporting external-session import. Pi additionally requires Node.js 22.19+ for its native SDK. Other source formats may require an explicit completed transcript, directory, and title.
- Handoff does not call Mem0. Large imports may invoke Codex’s native model compaction; smaller imports do not generate a summary. Failed creation saves a private recovery bundle under `~/.mem0/handoffs/`.
- Replace strict before-answer and repeated-search instructions with focused optional retrieval. Existing context can answer the question without another search. Search scoping, retrieval limits, and capture scheduling are unchanged.
