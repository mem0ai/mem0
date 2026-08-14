# Skills (`skills/`)

Claude Code skill definitions published from this repo. Agents fetch them by raw URL, so treat every file here as a public API.

## The two kinds

**Reference skills** carry SDK knowledge and are always available:

| Skill | Covers |
|-------|--------|
| `mem0/` | Python + TypeScript SDKs, Platform and OSS, framework integrations |
| `mem0-cli/` | Terminal workflows for `mem0-cli` and `@mem0/cli` |
| `mem0-vercel-ai-sdk/` | The `@mem0/vercel-ai-provider` package |

**Pipeline skills** run on demand and have side effects:

| Skill | Does |
|-------|------|
| `mem0-integrate/` | Wires Mem0 into an existing repo through a TDD pipeline. Writes a feature branch plus `.mem0-integration/` artifacts. |
| `mem0-test-integration/` | Verifies what the integrator produced, on the same branch. Read-only against the repo. |
| `mem0-oss-to-platform/` | Migrates a project from OSS to the hosted Platform SDK. Plans first, executes on approval. |

`mem0-integrate` and `mem0-test-integration` are **loosely coupled**: they share state only through `.mem0-integration/` files, never through conversation context.

## File layout

```
skills/<name>/
├── SKILL.md          entry point, always loaded when the skill triggers
├── README.md         human-facing, GitHub renders this
├── LICENSE           Apache-2.0
├── references/       loaded on demand, one file per topic
├── client/           optional, per-runtime call patterns
└── scripts/          optional executables
```

## Size budget

`SKILL.md` is loaded in full every time the skill fires, so it is the expensive file. Keep it **under 500 lines**. Everything past the decision-making core belongs in `references/`, which the agent loads only when it needs that topic.

Rule of thumb for what stays in `SKILL.md`:

- Frontmatter, including the trigger and do-not-trigger conditions.
- Anything the agent must honor on **every** run: non-negotiable principles, preconditions, gates.
- A one-line-per-step overview of the pipeline.
- Invocation, modes, exit codes.

Everything else, meaning full step mechanics, document templates, and verbatim subagent prompts, goes in `references/` with a link from the overview.

Current sizes, longest first:

```
mem0/references/use-cases.md              720   reference, on demand
mem0-cli/references/command-reference.md  694   reference, on demand
mem0/client/python.md                     487   reference, on demand
mem0-integrate/references/pipeline.md     375   reference, on demand
mem0-test-integration/SKILL.md            368   entry point, under budget
mem0-integrate/SKILL.md                   220   entry point
mem0/SKILL.md                             193   entry point
mem0-vercel-ai-sdk/SKILL.md               192   entry point
mem0-cli/SKILL.md                         169   entry point
mem0-oss-to-platform/SKILL.md             120   entry point
```

`mem0-integrate` is the one skill that needed splitting: it was 620 lines, now
220, with the ten-step mechanics in `references/pipeline.md` and the two
verbatim subagent system prompts in `references/subagent-prompts.md`. The
`SKILL.md` keeps only what every run must honor: canonical sources, the seven
integration principles, the delegation table, preconditions, a one-line-per-step
pipeline overview, artifacts, modes, invocation, and exit codes.

Reference files may run long. They are only read when the agent asks for that topic, so a 700-line `use-cases.md` costs nothing on a run that never opens it.

## Frontmatter

```yaml
---
name: <matches the directory name>
description: >
  What it does, then TRIGGER when: ... then DO NOT TRIGGER when: ...
  The trigger conditions are what routing depends on. Be specific and
  name the sibling skill to use instead.
license: Apache-2.0
metadata:
  author: mem0ai
  version: "0.1.0"
  category: ai-memory
  tags: "comma, separated"
  mem0_tested_versions: "mem0ai (PyPI) >=2.0.0,<3.0.0; mem0ai (npm) >=3.0.0,<4.0.0"
---
```

Bump `mem0_tested_versions` whenever the SDK majors move. Skills that pin call shapes against a version that no longer exists produce code that fails at runtime, which is worse than a skill that declines to fire.

## Conventions

- Cite canonical sources by URL (`https://docs.mem0.ai/llms.txt`, `openapi.json`, raw skill URLs). Skills must not rely on ambient model knowledge of the Mem0 API.
- When one skill's territory is covered by another, delegate to it by raw URL rather than paraphrasing its patterns.
- Pipeline skills declare **exit codes** in a table and mean them.
- Cross-references between files use relative paths so the skill works when vendored into another repo.
