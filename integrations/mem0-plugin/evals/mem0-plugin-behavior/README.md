# Mem0 Plugin Behavior Evals

These evals target the existing Mem0 editor plugin surface in `integrations/mem0-plugin`. They focus on plugin behavior: memory operation intent, privacy boundaries, expected metadata, and safe handling of CRUD workflows.

They do not evaluate Mem0 as a memory system. They evaluate whether the agent plugin gives maintainers and users clear, safe, verifiable behavior when memory tools are invoked from Claude, Codex, Cursor, or another agent harness.

## Coverage

- Add memory with scoped project metadata.
- Search memories without leaking raw prompts or files.
- Update and delete memories with explicit user intent.
- Report plugin failures with sanitized error classes.

## Telemetry Boundary

Safe plugin events include `plugin.component.invoked`, `plugin.component.error`, and `skill.*` events with metadata such as component name, outcome, duration bucket, harness name, and sanitized error class. Do not capture prompts, source files, tool arguments, connector payloads, credentials, or model outputs.
