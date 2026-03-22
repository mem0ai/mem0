#!/usr/bin/env python3
"""
Claude-Powered Security Code Review

Uses Claude to analyze code changes for:
- Backdoors and malicious code
- Data exfiltration patterns
- Credential exposure
- Vendor lock-in attempts
- Obfuscated code
- Security vulnerabilities
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed")
    print("Install with: pip install anthropic")
    sys.exit(1)


# Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
MAX_TOKENS = 8192


SECURITY_REVIEW_PROMPT = """You are a security expert reviewing code changes for potential backdoors, data exfiltration, and security vulnerabilities.

Your task is to analyze the following git diff and identify ANY security concerns. Be thorough and paranoid - this code is from an external source and we need to ensure it's safe before deploying.

## What to Look For

### Critical (MUST flag):
1. **Backdoors**: Code that allows unauthorized access (eval with user input, exec, hidden endpoints)
2. **Data Exfiltration**: Code sending data to external servers (especially API keys, credentials, user data)
3. **Credential Harvesting**: Code that captures, logs, or transmits sensitive credentials
4. **Hidden Network Calls**: HTTP/HTTPS requests to suspicious or hardcoded external endpoints
5. **Obfuscated Code**: Base64 encoded execution, hex strings, intentionally confusing code
6. **Command Injection**: Unsanitized input passed to shell commands or system calls

### High (Should flag):
7. **Vendor Lock-in**: Code that forces dependency on specific external services without opt-out
8. **Telemetry without consent**: Analytics/tracking that can't be disabled
9. **Insecure Deserialization**: pickle.loads, yaml.load without SafeLoader, marshal.loads
10. **Hardcoded Secrets**: API keys, passwords, tokens in the code
11. **Privilege Escalation**: Code that requests unnecessary permissions

### Medium (Note for review):
12. **New External Dependencies**: New network endpoints or third-party services
13. **Cryptographic Changes**: Changes to encryption, hashing, or authentication
14. **Permission Changes**: Modifications to access control or authentication

## Response Format

Respond with a JSON object (and ONLY the JSON object, no markdown):
{
    "verdict": "SAFE" | "SUSPICIOUS" | "DANGEROUS",
    "confidence": 0.0-1.0,
    "summary": "Brief summary of findings",
    "critical_issues": [
        {
            "type": "backdoor|exfiltration|injection|etc",
            "severity": "critical|high|medium",
            "file": "path/to/file.py",
            "line": "line number or range",
            "code": "the suspicious code snippet",
            "explanation": "why this is dangerous",
            "recommendation": "what to do about it"
        }
    ],
    "warnings": [
        {
            "type": "string",
            "description": "string",
            "file": "string",
            "line": "string"
        }
    ],
    "safe_changes": "Brief description of changes that appear safe",
    "requires_human_review": true|false,
    "human_review_reason": "Why human review is needed (if applicable)"
}

If the diff is empty or contains only safe changes, return:
{
    "verdict": "SAFE",
    "confidence": 0.95,
    "summary": "No security concerns found",
    "critical_issues": [],
    "warnings": [],
    "safe_changes": "Description of changes",
    "requires_human_review": false
}

## Git Diff to Review

```diff
{diff}
```

Remember: Be paranoid. It's better to flag something suspicious that turns out to be safe than to miss an actual backdoor. The cost of a false positive is low; the cost of missing malicious code is very high.
"""


def get_git_diff(base_branch: str = "main", target_branch: str = "HEAD") -> str:
    """Get the git diff between branches."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{base_branch}...{target_branch}"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e.stderr}")
        sys.exit(1)


def get_changed_files(base_branch: str = "main", target_branch: str = "HEAD") -> list:
    """Get list of changed files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...{target_branch}"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        return []


def chunk_diff(diff: str, max_chars: int = 100000) -> list:
    """Split large diffs into reviewable chunks."""
    if len(diff) <= max_chars:
        return [diff]

    chunks = []
    current_chunk = ""

    # Split by file boundaries
    files = diff.split("diff --git")

    for file_diff in files:
        if not file_diff.strip():
            continue

        file_diff = "diff --git" + file_diff

        if len(current_chunk) + len(file_diff) > max_chars:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = file_diff
        else:
            current_chunk += file_diff

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def review_with_claude(diff: str, client: anthropic.Anthropic) -> dict:
    """Send diff to Claude for security review."""
    prompt = SECURITY_REVIEW_PROMPT.format(diff=diff)

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text

        # Parse JSON response
        try:
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse Claude's response as JSON: {e}")
            return {
                "verdict": "SUSPICIOUS",
                "confidence": 0.5,
                "summary": "Could not parse review response",
                "critical_issues": [],
                "warnings": [{"type": "parse_error", "description": response_text[:500]}],
                "requires_human_review": True,
                "human_review_reason": "Automated review response was not parseable"
            }

    except anthropic.APIError as e:
        print(f"Error calling Claude API: {e}")
        return {
            "verdict": "SUSPICIOUS",
            "confidence": 0.0,
            "summary": f"API error: {e}",
            "critical_issues": [],
            "warnings": [],
            "requires_human_review": True,
            "human_review_reason": "Automated review failed - API error"
        }


def merge_reviews(reviews: list) -> dict:
    """Merge multiple chunk reviews into one."""
    if len(reviews) == 1:
        return reviews[0]

    # Take the worst verdict
    verdicts = [r.get("verdict", "SAFE") for r in reviews]
    if "DANGEROUS" in verdicts:
        final_verdict = "DANGEROUS"
    elif "SUSPICIOUS" in verdicts:
        final_verdict = "SUSPICIOUS"
    else:
        final_verdict = "SAFE"

    # Merge issues
    all_critical = []
    all_warnings = []
    for r in reviews:
        all_critical.extend(r.get("critical_issues", []))
        all_warnings.extend(r.get("warnings", []))

    # Average confidence
    confidences = [r.get("confidence", 0.5) for r in reviews]
    avg_confidence = sum(confidences) / len(confidences)

    return {
        "verdict": final_verdict,
        "confidence": avg_confidence,
        "summary": f"Merged review of {len(reviews)} chunks",
        "critical_issues": all_critical,
        "warnings": all_warnings,
        "requires_human_review": any(r.get("requires_human_review", False) for r in reviews),
        "human_review_reason": "; ".join(filter(None, [r.get("human_review_reason") for r in reviews]))
    }


def print_review_report(review: dict, changed_files: list):
    """Print formatted review report."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

    print()
    print("=" * 60)
    print("    CLAUDE SECURITY REVIEW REPORT")
    print("=" * 60)
    print()

    # Verdict with color
    verdict = review.get("verdict", "UNKNOWN")
    confidence = review.get("confidence", 0)

    if verdict == "SAFE":
        print(f"{GREEN}VERDICT: {verdict}{NC} (confidence: {confidence:.0%})")
    elif verdict == "SUSPICIOUS":
        print(f"{YELLOW}VERDICT: {verdict}{NC} (confidence: {confidence:.0%})")
    else:
        print(f"{RED}VERDICT: {verdict}{NC} (confidence: {confidence:.0%})")

    print()
    print(f"Summary: {review.get('summary', 'No summary')}")
    print()

    # Files reviewed
    print(f"{BLUE}Files reviewed:{NC}")
    for f in changed_files[:20]:
        print(f"  - {f}")
    if len(changed_files) > 20:
        print(f"  ... and {len(changed_files) - 20} more")
    print()

    # Critical issues
    critical = review.get("critical_issues", [])
    if critical:
        print(f"{RED}CRITICAL ISSUES ({len(critical)}):{NC}")
        for i, issue in enumerate(critical, 1):
            print(f"\n  [{i}] {issue.get('type', 'unknown').upper()}")
            print(f"      File: {issue.get('file', 'unknown')}")
            print(f"      Line: {issue.get('line', 'unknown')}")
            print(f"      Severity: {issue.get('severity', 'unknown')}")
            print(f"      Explanation: {issue.get('explanation', 'N/A')}")
            if issue.get('code'):
                print(f"      Code: {issue.get('code')[:200]}...")
            print(f"      Recommendation: {issue.get('recommendation', 'Review manually')}")
    else:
        print(f"{GREEN}No critical issues found.{NC}")

    print()

    # Warnings
    warnings = review.get("warnings", [])
    if warnings:
        print(f"{YELLOW}WARNINGS ({len(warnings)}):{NC}")
        for w in warnings[:10]:
            print(f"  - [{w.get('type', 'warning')}] {w.get('description', 'No description')}")
            if w.get('file'):
                print(f"    File: {w.get('file')}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more warnings")

    print()

    # Human review needed?
    if review.get("requires_human_review"):
        print(f"{YELLOW}⚠️  HUMAN REVIEW REQUIRED{NC}")
        print(f"   Reason: {review.get('human_review_reason', 'See above')}")

    print()
    print("=" * 60)


def save_report(review: dict, changed_files: list, output_path: Path):
    """Save review report to file."""
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model": MODEL,
        "files_reviewed": changed_files,
        "review": review
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Claude-powered security code review")
    parser.add_argument("--base", default="main", help="Base branch (default: main)")
    parser.add_argument("--target", default="HEAD", help="Target branch (default: HEAD)")
    parser.add_argument("--output", help="Output report file path")
    parser.add_argument("--quiet", action="store_true", help="Only output verdict")
    parser.add_argument("--diff-file", help="Read diff from file instead of git")
    args = parser.parse_args()

    # Check API key
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key'")
        sys.exit(1)

    # Get diff
    if args.diff_file:
        with open(args.diff_file) as f:
            diff = f.read()
        changed_files = ["(from file)"]
    else:
        diff = get_git_diff(args.base, args.target)
        changed_files = get_changed_files(args.base, args.target)

    if not diff.strip():
        print("No changes to review.")
        sys.exit(0)

    # Filter out deploy-fly-io changes from review (our own code)
    filtered_lines = []
    skip_file = False
    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            skip_file = "deploy-fly-io/" in line
        if not skip_file:
            filtered_lines.append(line)

    diff = "\n".join(filtered_lines)

    if not diff.strip():
        print("No upstream changes to review (only deploy-fly-io changes).")
        sys.exit(0)

    print(f"Reviewing {len(changed_files)} changed files with Claude ({MODEL})...")

    # Initialize client
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Chunk if necessary
    chunks = chunk_diff(diff)

    if len(chunks) > 1:
        print(f"Large diff - reviewing in {len(chunks)} chunks...")

    # Review each chunk
    reviews = []
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"  Reviewing chunk {i+1}/{len(chunks)}...")
        review = review_with_claude(chunk, client)
        reviews.append(review)

    # Merge reviews
    final_review = merge_reviews(reviews)

    # Output
    if args.quiet:
        print(final_review.get("verdict", "UNKNOWN"))
    else:
        print_review_report(final_review, changed_files)

    # Save report
    if args.output:
        save_report(final_review, changed_files, Path(args.output))
    else:
        # Default save location
        report_dir = Path(__file__).parent.parent / "docs"
        report_path = report_dir / f"claude_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_report(final_review, changed_files, report_path)

    # Exit code based on verdict
    verdict = final_review.get("verdict", "UNKNOWN")
    if verdict == "DANGEROUS":
        sys.exit(2)
    elif verdict == "SUSPICIOUS":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
