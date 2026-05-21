# mem0 Plugin v0.2.1 — Manual Testing Guide

## Prerequisites

```bash
export MEM0_API_KEY="<your-api-key>"
cd mem0-plugin
```

Verify key works:
```bash
curl -s -X POST https://api.mem0.ai/v3/memories/search/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"test","user_id":"test","limit":1}' | python3 -m json.tool
```

---

## Tier 1 — First 30 Seconds

### 1.1 SessionStart identity banner
```bash
export MEM0_API_KEY="<key>"
echo '{"source":"startup","cwd":"'$(pwd)'"}' | bash scripts/on_session_start.sh
```
**Expected:** `## Mem0 Active` header with `user=<you> | project=<slug> | branch=<branch> | memories=<N>`

### 1.2 Onboarding detection (first run)
Delete the marker file first:
```bash
_PID=$(printf '%s' "$(python3 scripts/_project.py)" | tr '/:' '--')
rm -f ~/.mem0/.onboarded_${_PID}
```
Re-run SessionStart:
```bash
echo '{"source":"startup","cwd":"'$(pwd)'"}' | bash scripts/on_session_start.sh
```
**Expected:** Output includes `## Mem0 First Run — Automatic Onboarding`

### 1.3 Session stats + Stop hook
```bash
python3 scripts/session_stats.py init
python3 scripts/session_stats.py add "decision"
python3 scripts/session_stats.py add "anti_pattern"
python3 scripts/session_stats.py search
python3 scripts/session_stats.py search
python3 scripts/session_stats.py search
echo '{"stop_hook_active":false,"cwd":"."}' | bash scripts/on_stop.sh
```
**Expected:** Report shows `wrote 2 memories, retrieved 3. Categories touched: decision, anti_pattern.`

### 1.4 Auto-import check
```bash
MEM0_CWD="$(pwd)" python3 scripts/auto_import.py
```
**Expected:** Silently imports CLAUDE.md if present. Check `~/.mem0/file_hashes.json` for hash entries.

---

## Tier 2 — Project Scoping

### 2.1 Project ID from git remote
```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); from _project import resolve_project_id; print(resolve_project_id())"
```
**Expected:** `mem0ai-mem0` (or your repo's `owner-repo` slug)

### 2.2 Branch detection
```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); from _project import resolve_branch; print(resolve_branch())"
```
**Expected:** Current git branch name (e.g., `feat/mem0-plugin`)

### 2.3 Project map persistence
```bash
cat ~/.mem0/project_map.json 2>/dev/null || echo "No map yet"
```

### 2.4 app_id scoping in write paths
Verify all write scripts pass `app_id` (project scope) to the API:
```bash
for script in auto_import.py on_pre_compact.py capture_compact_summary.py on_pre_commit.py import_competing_tools.py; do
  if grep -q '"app_id"' scripts/$script 2>/dev/null; then
    echo "PASS: $script uses app_id"
  else
    echo "FAIL: $script missing app_id"
  fi
done
```
**Expected:** All 5 scripts PASS.

### 2.5 Branch tagging in write paths
```bash
for script in auto_import.py on_pre_compact.py capture_compact_summary.py on_pre_commit.py; do
  if grep -q 'branch' scripts/$script 2>/dev/null; then
    echo "PASS: $script includes branch"
  else
    echo "FAIL: $script missing branch"
  fi
done
```
**Expected:** All 4 PASS.

---

## Tier 3 — Cross-Tool

### 3.1 Import competing tools (dry run)
```bash
python3 scripts/import_competing_tools.py cursorrules --dry-run 2>&1 || echo "No .cursorrules found (OK)"
```

### 3.2 Export format parser
```bash
echo '---
id: test-123
type: decision
---
Use PostgreSQL for auth module.
---
id: test-456
type: anti_pattern
---
Never use eval() in templates.' | python3 scripts/parse_export_file.py -
```
**Expected:** JSON array with 2 blocks

### 3.3 Export skill exists
```bash
test -f skills/mem0-export/SKILL.md && echo "PASS" || echo "FAIL"
```

### 3.4 Import skill exists
```bash
test -f skills/mem0-import/SKILL.md && echo "PASS" || echo "FAIL"
```

### 3.5 Import-tools skill exists
```bash
test -f skills/mem0-import-tools/SKILL.md && echo "PASS" || echo "FAIL"
```

---

## Tier 4 — Dreaming

### 4.1 Retention policy parser
```bash
cat > /tmp/test_mem0.md << 'EOF'
## Retention
session_state: 90d
decision: forever
anti_pattern: 365d
EOF
python3 scripts/parse_mem0_config.py /tmp
```
**Expected:** `{"session_state": 90, "decision": null, "anti_pattern": 365}`

### 4.2 Full config parser
```bash
cat > /tmp/test_mem0.md << 'EOF'
## Retention
session_state: 90d

## Search
default_limit: 20

## Categories
- architecture_decisions
- bug_fixes

## Identity
user_id: kartik
EOF
python3 scripts/parse_mem0_config.py --full /tmp
```
**Expected:** JSON with `retention`, `search`, `categories`, `identity` keys

### 4.3 Dream skill exists and has no fake scheduling
```bash
test -f skills/mem0-dream/SKILL.md && echo "PASS: exists" || echo "FAIL"
# Must NOT reference a /schedule skill (fabricated in earlier version)
grep -c '/schedule' skills/mem0-dream/SKILL.md && echo "FAIL: references fake /schedule" || echo "PASS: no fake scheduling"
```
**Expected:** PASS: exists, PASS: no fake scheduling

### 4.4 Dream skill has auto mode
```bash
grep -c '\-\-auto' skills/mem0-dream/SKILL.md > /dev/null && echo "PASS: --auto documented" || echo "FAIL"
```
**Expected:** PASS

---

## Tier 5 — Categories

### 5.1 Category count
```bash
python3 -c "
import sys; sys.path.insert(0,'scripts')
from setup_coding_categories import CODING_CATEGORIES
print(f'Categories: {len(CODING_CATEGORIES)}')
for k in sorted(CODING_CATEGORIES): print(f'  {k}')
"
```
**Expected:** 17 categories listed

### 5.2 Confidence field in MCP skill
```bash
grep -c 'metadata.confidence' skills/mem0-mcp/SKILL.md
```
**Expected:** > 0 (confidence guidance documented)

### 5.3 Recall rubric (recency filter)
```bash
grep -c 'Recency filter' skills/mem0-mcp/SKILL.md
```
**Expected:** > 0 (recency-based recall documented)

### 5.4 Citation format
```bash
grep -c '\[mem0:' skills/mem0-mcp/SKILL.md
```
**Expected:** > 0 (inline citation format documented)

### 5.5 Expiration on session_state writes
```bash
grep -c 'expiration_date' scripts/on_pre_compact.py
```
**Expected:** > 0 (session_state memories auto-expire)

---

## Tier 6 — Observability

### 6.1 Session stats peek (JSON without clearing)
```bash
python3 scripts/session_stats.py init
python3 scripts/session_stats.py add "decision"
python3 scripts/session_stats.py peek
python3 scripts/session_stats.py peek  # should still work — file not cleared
```
**Expected:** JSON with `adds=1`, `category_counts={"decision":1}`. Second peek returns same data.

### 6.2 Category counts tracked across adds
```bash
python3 scripts/session_stats.py init
python3 scripts/session_stats.py add "decision"
python3 scripts/session_stats.py add "decision"
python3 scripts/session_stats.py add "anti_pattern"
python3 scripts/session_stats.py peek
```
**Expected:** JSON with `adds=3`, `category_counts={"decision":2, "anti_pattern":1}`

### 6.3 Skills exist
```bash
for skill in mem0-stats mem0-health mem0-digest; do
  if [ -f "skills/$skill/SKILL.md" ]; then
    echo "PASS: $skill"
  else
    echo "FAIL: $skill"
  fi
done
```

### 6.4 Stats skill content check
```bash
grep -c 'session_stats.py' skills/mem0-stats/SKILL.md > /dev/null && echo "PASS: references session_stats" || echo "FAIL"
grep -c 'get_memories' skills/mem0-stats/SKILL.md > /dev/null && echo "PASS: references lifetime stats" || echo "FAIL"
```

### 6.5 Health skill has 5 checks
```bash
grep -c 'PASS\|FAIL\|check' skills/mem0-health/SKILL.md
```
**Expected:** Multiple references to pass/fail checks (API key, identity, MCP, write/read, session tracker)

---

## Tier 7 — Smart Retrieval

### 7.1 Stack trace detection
```bash
echo '{"prompt":"Getting TypeError: Cannot read property of undefined at src/auth.ts:42 in validateToken","cwd":"."}' | bash scripts/on_user_prompt.sh 2>&1 | grep "ERROR DETECTED"
```
**Expected:** `**ERROR DETECTED in prompt.**`

### 7.2 File path detection
```bash
echo '{"prompt":"Fix the bug in src/middleware/auth.ts and update config/secrets.ts","cwd":"."}' | bash scripts/on_user_prompt.sh 2>&1 | grep "FILE PATHS"
```
**Expected:** `**FILE PATHS detected:** src/middleware/auth.ts config/secrets.ts`

### 7.3 Short prompt skipped
```bash
echo '{"prompt":"ok thanks","cwd":"."}' | bash scripts/on_user_prompt.sh 2>&1
```
**Expected:** Empty output (prompts < 20 chars are skipped)

### 7.4 Pre-commit script
```bash
echo "3 files changed, 42 insertions(+), 10 deletions(-)" | python3 scripts/on_pre_commit.py; echo "exit: $?"
```
**Expected:** `exit: 0` (fire-and-forget, no output)

### 7.5 Pre-commit uses v3 endpoint
```bash
grep -c 'v3/memories/add' scripts/on_pre_commit.py
```
**Expected:** 1

### 7.6 Pre-commit uses infer=False
```bash
grep -c '"infer"' scripts/on_pre_commit.py
```
**Expected:** 1

### 7.7 Citation format in MCP skill
```bash
grep 'mem0:' skills/mem0-mcp/SKILL.md | head -3
```
**Expected:** Shows `[mem0:<short_id>]` citation format (first 8 chars of memory ID)

---

## Tier 8 — Power User

### 8.1 Skills exist
```bash
for skill in mem0-remember mem0-forget mem0-pin mem0-peek; do
  if [ -f "skills/$skill/SKILL.md" ]; then
    echo "PASS: $skill"
  else
    echo "FAIL: $skill"
  fi
done
```

### 8.2 Remember skill stores with infer=False
```bash
grep -c 'infer.*[Ff]alse\|infer=False' skills/mem0-remember/SKILL.md
```
**Expected:** > 0

### 8.3 Remember skill auto-classifies type
```bash
grep -c 'metadata.*type\|classify' skills/mem0-remember/SKILL.md
```
**Expected:** > 0

### 8.4 Forget skill requires confirmation
```bash
grep -c 'confirm\|confirmation' skills/mem0-forget/SKILL.md
```
**Expected:** > 0

### 8.5 Pin skill uses update_memory
```bash
grep -c 'update_memory' skills/mem0-pin/SKILL.md
```
**Expected:** > 0

### 8.6 Peek skill outputs compact format
```bash
grep -c '\[mem0:' skills/mem0-peek/SKILL.md
```
**Expected:** > 0

### 8.7 Config wired into SessionStart
```bash
cat > /tmp/test_mem0.md << 'EOF'
## Retention
session_state: 90d
EOF
# Simulate session start with a cwd that has mem0.md
mkdir -p /tmp/test_mem0_project
cp /tmp/test_mem0.md /tmp/test_mem0_project/mem0.md
echo '{"source":"startup","cwd":"/tmp/test_mem0_project"}' | bash scripts/on_session_start.sh 2>&1 | grep -A3 "Project Config"
rm -rf /tmp/test_mem0_project
```
**Expected:** Shows `### Project Config (mem0.md)` with JSON containing retention

---

## All v3 Endpoints

Every REST script must use `/v3/memories/add/` (not v1/v2):
```bash
for script in auto_import.py on_pre_compact.py capture_compact_summary.py on_pre_commit.py import_competing_tools.py; do
  V=$(grep -o 'v[0-9]/memories' scripts/$script 2>/dev/null | head -1)
  if [ "$V" = "v3/memories" ]; then
    echo "PASS: $script → v3"
  else
    echo "FAIL: $script → $V"
  fi
done
```
**Expected:** All 5 PASS with v3.

SessionStart search must also use v3:
```bash
grep -o 'v[0-9]/memories/search' scripts/on_session_start.sh | head -1
```
**Expected:** `v3/memories/search`

---

## All 16 Skills

```bash
expected="mem0 mem0-digest mem0-dream mem0-export mem0-forget mem0-health mem0-import mem0-import-tools mem0-mcp mem0-onboard mem0-peek mem0-pin mem0-remember mem0-stats mem0-switch-project mem0-tour"
found=$(ls -d skills/*/SKILL.md 2>/dev/null | xargs -I{} dirname {} | xargs -I{} basename {} | sort | tr '\n' ' ' | sed 's/ $//')
if [ "$found" = "$expected" ]; then
  echo "PASS: all 16 skills present"
else
  echo "FAIL: expected 16 skills"
  echo "  expected: $expected"
  echo "  found:    $found"
fi
```

---

## Plugin Versions

All three plugin manifests must be 0.2.1:
```bash
for p in .claude-plugin .cursor-plugin .codex-plugin; do
  V=$(python3 -c "import json; print(json.load(open('$p/plugin.json'))['version'])" 2>/dev/null)
  echo "$p: $V"
done
```
**Expected:** All show `0.2.1`

---

## Robustness Checks

### Cursor stop hook loop guard
```bash
grep -c 'loop_count' scripts/on_stop_cursor.sh
```
**Expected:** > 0 (prevents infinite re-entry)

### on_stop.sh no set -e
```bash
grep 'set -' scripts/on_stop.sh | head -1
```
**Expected:** `set -uo pipefail` (no `-e`, so stats failure doesn't kill the hook)

### _identity.py fallback stubs accept cwd
```bash
python3 -c "
import sys; sys.path.insert(0,'scripts')
from _identity import resolve_project_id_fallback
# If _project.py is missing, fallback should accept cwd kwarg without TypeError
"
echo "exit: $?"
```
**Expected:** `exit: 0`

### on_pre_compact.py uses infer=False
```bash
grep '"infer"' scripts/on_pre_compact.py
```
**Expected:** `"infer": False`

---

## Unit Tests

```bash
cd mem0-plugin
python -m pytest tests/ -v
```
**Expected:** 91 tests pass

---

## In Claude Code (live test)

1. Open a new Claude Code session in any git repo with mem0 plugin installed
2. Verify identity banner appears: `user=X | project=Y | branch=Z | memories=N`
3. Run `/mem0:onboard` — should detect project files, offer to import
4. Run `/mem0:tour` — should show grouped memories
5. Run `/mem0:stats` — should show session + lifetime stats
6. Run `/mem0:health` — should show 5-check table, all PASS
7. Run `/mem0:peek auth` — should show compact search results
8. Run `/mem0:remember always use pnpm not npm` — should store with confirmation
9. Run `/mem0:forget pnpm` — should find the memory, ask to confirm delete
10. Paste an error with a stack trace — should see `ERROR DETECTED` in hook output
11. Work for a while, then check Stop hook prints session stats

---

## Checklist

- [ ] SessionStart banner shows correct user/project/branch/memory count
- [ ] First-run triggers onboarding prompt
- [ ] Stop hook shows session stats report
- [ ] Stack trace detection fires on errors
- [ ] File path detection fires on file mentions
- [ ] Short prompts (<20 chars) produce no hook output
- [ ] `session_stats.py peek` returns JSON without clearing
- [ ] `parse_mem0_config.py --full` parses all 4 sections
- [ ] All 17 categories present in `setup_coding_categories.py`
- [ ] All 16 skill SKILL.md files exist
- [ ] 91 unit tests pass
- [ ] All plugin versions are 0.2.1
- [ ] All REST scripts use v3 endpoints
- [ ] `app_id` scoping in all write paths
- [ ] Branch tagging in all write paths
- [ ] Confidence guidance in MCP skill
- [ ] Citation format in MCP skill
- [ ] Recency filter documented in MCP skill
- [ ] `infer=False` in session_state writes
- [ ] `expiration_date` on session_state writes
- [ ] Cursor stop hook has loop guard
- [ ] `on_stop.sh` has no `set -e`
- [ ] Dream skill has no fake `/schedule` reference
- [ ] Remember skill uses `infer=False`
- [ ] Forget skill requires confirmation before delete
- [ ] Pin skill uses `update_memory`
- [ ] Pre-commit script is fire-and-forget (exit 0)
- [ ] Category counts tracked in session stats
