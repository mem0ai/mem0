#!/usr/bin/env bash
set -euo pipefail

# upstream-cherry-pick.sh — Evaluate and cherry-pick useful upstream commits
#
# Called by n8n on schedule. Outputs JSON for n8n to process.
#
# Usage:
#   ./scripts/upstream-cherry-pick.sh [--dry-run] [--since SHA] [--auto]

REPO_DIR="${REPO_DIR:-/home/luka/projects/mem0}"
FORK_REMOTE="${FORK_REMOTE:-fork}"
UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-origin}"
FORK_BRANCH="${FORK_BRANCH:-main}"
STATE_FILE="${REPO_DIR}/.upstream-sync-state"
GREP=/usr/bin/grep

cd "$REPO_DIR"

DRY_RUN=true
AUTO=false
SINCE_SHA=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --auto) AUTO=true; DRY_RUN=false; shift ;;
        --since) SINCE_SHA="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Get last synced SHA
if [[ -z "$SINCE_SHA" ]]; then
    if [[ -f "$STATE_FILE" ]]; then
        SINCE_SHA=$(cat "$STATE_FILE")
    else
        git fetch "$FORK_REMOTE" --quiet 2>/dev/null
        SINCE_SHA=$(git rev-parse "$FORK_REMOTE/$FORK_BRANCH")
    fi
fi

# Fetch upstream
git fetch "$UPSTREAM_REMOTE" --quiet 2>/dev/null
UPSTREAM_HEAD=$(git rev-parse "$UPSTREAM_REMOTE/$FORK_BRANCH")

if [[ "$SINCE_SHA" == "$UPSTREAM_HEAD" ]]; then
    echo '{"status":"up_to_date","new_commits":0,"candidates":[]}'
    exit 0
fi

# Evaluate a single commit, output one JSON line
eval_commit() {
    local sha="$1"
    local msg author date short files
    msg=$(git log -1 --format="%s" "$sha")
    author=$(git log -1 --format="%an" "$sha")
    date=$(git log -1 --format="%aI" "$sha")
    short=$(git rev-parse --short "$sha")
    files=$(git diff-tree --no-commit-id --name-only -r "$sha" 2>/dev/null || true)

    local verdict="approve" reason=""

    # Skip by message pattern
    if echo "$msg" | $GREP -qEi "^chore\(docs\)|^docs:|Improve SEO|^chore:.*changelog"; then
        verdict="skip"; reason="skip_msg_pattern"
    fi

    # Check file relevance
    if [[ "$verdict" == "approve" ]]; then
        local has_relevant=false
        while IFS= read -r f; do
            [[ -z "$f" ]] && continue
            case "$f" in
                mem0/*|openmemory/*|server/*|pyproject.toml) has_relevant=true; break ;;
            esac
        done <<< "$files"
        if [[ "$has_relevant" == "false" ]]; then
            verdict="skip"; reason="no_relevant_files"
        fi
    fi

    # Check if all files are docs/skip-only
    if [[ "$verdict" == "approve" ]]; then
        local all_skip=true
        while IFS= read -r f; do
            [[ -z "$f" ]] && continue
            case "$f" in
                docs/*|embedchain/*|.github/*|*CHANGELOG*|*README*|*.md|*mintlify*) ;;
                *) all_skip=false; break ;;
            esac
        done <<< "$files"
        if [[ "$all_skip" == "true" && -n "$files" ]]; then
            verdict="skip"; reason="all_files_skippable"
        fi
    fi

    # Priority
    local priority="normal"
    if echo "$msg" | $GREP -qEi "^fix|^feat|^refactor|^perf|security"; then
        priority="high"
    fi

    # Stats
    local stat insertions deletions file_list
    stat=$(git diff-tree --stat --no-commit-id "$sha" 2>/dev/null | tail -1 || echo "")
    insertions=$(echo "$stat" | $GREP -oP '\d+(?= insertion)' || echo "0")
    deletions=$(echo "$stat" | $GREP -oP '\d+(?= deletion)' || echo "0")
    file_list=$(echo "$files" | head -10 | tr '\n' ',' | sed 's/,$//')

    jq -nc \
        --arg sha "$short" \
        --arg full_sha "$sha" \
        --arg msg "$msg" \
        --arg author "$author" \
        --arg date "$date" \
        --arg verdict "$verdict" \
        --arg reason "$reason" \
        --arg priority "$priority" \
        --arg files "$file_list" \
        --argjson insertions "${insertions:-0}" \
        --argjson deletions "${deletions:-0}" \
        '{sha: $sha, full_sha: $full_sha, msg: $msg, author: $author, date: $date, verdict: $verdict, reason: $reason, priority: $priority, files: $files, insertions: $insertions, deletions: $deletions}'
}

# Collect all commit evaluations
mapfile -t ALL_SHAS < <(git log --reverse --format="%H" "${SINCE_SHA}..${UPSTREAM_HEAD}")
TOTAL=${#ALL_SHAS[@]}

CANDIDATES=$(
    for sha in "${ALL_SHAS[@]}"; do
        eval_commit "$sha"
    done | jq -sc '.'
)

APPROVED_N=$(echo "$CANDIDATES" | jq '[.[] | select(.verdict=="approve")] | length')
SKIPPED_N=$(echo "$CANDIDATES" | jq '[.[] | select(.verdict=="skip")] | length')

# Apply if --auto
APPLIED=0
FAILED=0
APPLY_LOG="[]"
PUSH_STATUS="skipped"

if [[ "$AUTO" == "true" && "$APPROVED_N" -gt 0 ]]; then
    CURRENT=$(git branch --show-current)
    if [[ "$CURRENT" != "$FORK_BRANCH" ]]; then
        echo "{\"error\":\"not on $FORK_BRANCH\",\"current\":\"$CURRENT\"}" >&2
        exit 1
    fi

    while IFS= read -r sha; do
        short=$(git rev-parse --short "$sha")
        msg=$(git log -1 --format="%s" "$sha")

        if git cherry-pick --no-commit "$sha" 2>/dev/null; then
            if git diff --cached --quiet 2>/dev/null; then
                git cherry-pick --abort 2>/dev/null || git reset HEAD --quiet
                entry=$(jq -nc --arg s "$short" --arg m "$msg" '{sha: $s, msg: $m, status: "already_applied"}')
            else
                git commit --no-edit -m "$msg" 2>/dev/null
                APPLIED=$((APPLIED + 1))
                entry=$(jq -nc --arg s "$short" --arg m "$msg" '{sha: $s, msg: $m, status: "applied"}')
            fi
        else
            git cherry-pick --abort 2>/dev/null || git reset --hard HEAD --quiet
            FAILED=$((FAILED + 1))
            entry=$(jq -nc --arg s "$short" --arg m "$msg" '{sha: $s, msg: $m, status: "conflict"}')
        fi

        APPLY_LOG=$(echo "$APPLY_LOG" | jq --argjson e "$entry" '. + [$e]')
    done < <(echo "$CANDIDATES" | jq -r '.[] | select(.verdict=="approve") | .full_sha')

    if [[ "$APPLIED" -gt 0 ]]; then
        if git push "$FORK_REMOTE" "$FORK_BRANCH" 2>/dev/null; then
            PUSH_STATUS="pushed"
        else
            PUSH_STATUS="push_failed"
        fi
    fi

    echo "$UPSTREAM_HEAD" > "$STATE_FILE"
fi

# Output
jq -nc \
    --arg status "ok" \
    --argjson total "$TOTAL" \
    --argjson approved "$APPROVED_N" \
    --argjson skipped "$SKIPPED_N" \
    --argjson applied "$APPLIED" \
    --argjson failed "$FAILED" \
    --argjson candidates "$CANDIDATES" \
    --argjson apply_log "$APPLY_LOG" \
    --arg upstream_head "$UPSTREAM_HEAD" \
    --arg since "$SINCE_SHA" \
    --arg dry_run "$DRY_RUN" \
    --arg push_status "$PUSH_STATUS" \
    '{status: $status, since: $since, upstream_head: $upstream_head, total_new: $total, approved: $approved, skipped: $skipped, applied: $applied, failed: $failed, push_status: $push_status, dry_run: $dry_run, candidates: $candidates, apply_log: $apply_log}'
