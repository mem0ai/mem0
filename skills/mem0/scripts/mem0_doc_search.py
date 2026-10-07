#!/usr/bin/env python3
"""
Mem0 Documentation Search Agent
On-demand search tool for querying Mem0 documentation without storing content locally.

This tool searches the docs.mem0.ai llms.txt index and fetches pages as markdown
to perform just-in-time retrieval of technical information.

Usage:
    python mem0_doc_search.py --query "how to add graph memory"
    python mem0_doc_search.py --query "filter syntax for categories"
    python mem0_doc_search.py --page "/platform/features/graph-memory"
    python mem0_doc_search.py --index
    python mem0_doc_search.py --query "webhook events" --section platform

Purpose:
    - Avoid bloating local context with full documentation
    - Enable just-in-time retrieval of technical details
    - Query specific documentation pages on demand
    - Search across the full Mem0 documentation site
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DOCS_BASE = "https://docs.mem0.ai"
LLMS_INDEX = f"{DOCS_BASE}/llms.txt"
ENTRY_URL = re.compile(r"\((https?://[^)\s]+)\)")
MAX_RESULTS = 20

SECTION_MAP = {
    "platform": [
        "/platform/overview",
        "/platform/quickstart",
        "/platform/features/graph-memory",
        "/platform/features/custom-instructions",
        "/platform/features/custom-categories",
        "/platform/features/v2-memory-filters",
        "/platform/features/async-client",
        "/platform/features/webhooks",
        "/platform/features/multimodal-support",
    ],
    "api": [
        "/api-reference/memory/add-memories",
        "/api-reference/memory/search-memories",
        "/api-reference/memory/get-memories",
        "/api-reference/memory/get-memory",
        "/api-reference/memory/update-memory",
        "/api-reference/memory/delete-memory",
    ],
    "open-source": [
        "/open-source/overview",
        "/open-source/python-quickstart",
        "/open-source/node-quickstart",
        "/open-source/features/overview",
        "/open-source/features/rest-api",
        "/open-source/configuration",
    ],
    "integrations": [
        "/integrations",
    ],
}

SECTION_PREFIXES = {
    "platform": ("/platform/",),
    "api": ("/api-reference/",),
    "open-source": ("/open-source/", "/components/"),
    "integrations": ("/integrations",),
}


def fetch_url(url: str) -> str:
    """Fetch content from a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mem0DocSearchAgent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        sys.exit(f"Error fetching {url}: HTTP {e.code} {e.reason}")
    except OSError as e:
        sys.exit(f"Error fetching {url}: {e}")


def index_entries() -> list:
    """Return the page entries listed in the llms.txt index."""
    content = fetch_url(LLMS_INDEX)
    return [line.strip()[2:] for line in content.splitlines() if line.strip().startswith("- [")]


def entry_path(entry: str) -> str:
    """Extract the URL path from an llms.txt index entry."""
    match = ENTRY_URL.search(entry)
    return urllib.parse.urlparse(match.group(1)).path if match else ""


def search_docs(query: str, section: str | None = None) -> dict:
    """Search the llms.txt index for entries matching the query terms, best matches first."""
    terms = re.findall(r"[a-z0-9_]+", query.lower())
    entries = index_entries()

    if section in SECTION_PREFIXES:
        entries = [e for e in entries if entry_path(e).startswith(SECTION_PREFIXES[section])]

    scored = []
    for entry in entries:
        haystack = entry.lower()
        title = haystack.split("]")[0]
        score = sum((term in haystack) + (term in title) for term in terms)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda item: -item[0])

    return {
        "source": "llms_txt_index",
        "query": query,
        "matching_urls": [entry for _, entry in scored[:MAX_RESULTS]],
        "suggestion": "Fetch specific pages with --page <path> for detailed content",
    }


def fetch_page(page_path: str) -> dict:
    """Fetch a specific documentation page as markdown."""
    parts = urllib.parse.urlsplit(urllib.parse.urljoin(DOCS_BASE, page_path))
    path = parts.path.rstrip("/")
    if not path.endswith(".md"):
        path = f"{path}.md"
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    content = fetch_url(url)
    return {"url": url, "content": content[:10000], "truncated": len(content) > 10000}


def get_index() -> dict:
    """Fetch the full documentation index from llms.txt."""
    urls = index_entries()
    return {"total_pages": len(urls), "urls": urls, "sections": list(SECTION_MAP.keys())}


def list_section(section: str) -> dict:
    """List all known pages in a documentation section."""
    if section not in SECTION_MAP:
        return {"error": f"Unknown section: {section}", "available": list(SECTION_MAP.keys())}
    return {
        "section": section,
        "pages": [f"{DOCS_BASE}{p}" for p in SECTION_MAP[section]],
    }


def main():
    parser = argparse.ArgumentParser(description="Search Mem0 documentation on demand")
    parser.add_argument("--query", help="Search query for documentation")
    parser.add_argument("--page", help="Fetch a specific page path (e.g., /platform/features/graph-memory)")
    parser.add_argument("--index", action="store_true", help="Show full documentation index")
    parser.add_argument("--section", help="Filter by section or list section pages")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.index:
        result = get_index()
    elif args.section and not args.query:
        result = list_section(args.section)
    elif args.page:
        result = fetch_page(args.page)
    elif args.query:
        result = search_docs(args.query, section=args.section)
    else:
        parser.print_help()
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if isinstance(result, dict):
            if "results" in result:
                print(f"Source: {result.get('source', 'unknown')}")
                for r in result["results"]:
                    print(f"  - {r.get('title', 'N/A')}: {r.get('url', 'N/A')}")
                    if r.get("description"):
                        print(f"    {r['description'][:200]}")
            elif "matching_urls" in result:
                print(f"Source: {result['source']}")
                print(f"Query: {result['query']}")
                for url in result["matching_urls"]:
                    print(f"  - {url}")
                if result.get("suggestion"):
                    print(f"\n{result['suggestion']}")
            elif "urls" in result:
                print(f"Total documentation pages: {result['total_pages']}")
                print(f"Sections: {', '.join(result['sections'])}")
                for url in result["urls"][:30]:
                    print(f"  - {url}")
                if result["total_pages"] > 30:
                    print(f"  ... and {result['total_pages'] - 30} more")
            elif "pages" in result:
                print(f"Section: {result['section']}")
                for page in result["pages"]:
                    print(f"  - {page}")
            elif "content" in result:
                print(f"URL: {result['url']}")
                if result.get("truncated"):
                    print("[Content truncated to 10000 chars]")
                print(result["content"])
            elif "error" in result:
                print(f"Error: {result['error']}")
                if result.get("available"):
                    print(f"Available sections: {', '.join(result['available'])}")
            else:
                print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
