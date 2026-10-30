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
DOCS_HOST = urllib.parse.urlsplit(DOCS_BASE).netloc
LLMS_INDEX = f"{DOCS_BASE}/llms.txt"
ENTRY_URL = re.compile(r"\((https?://[^)\s]+)\)")
MAX_RESULTS = 20
MAX_PAGE_CHARS = 10000
MAX_INDEX_BYTES = 2_000_000

SECTION_PREFIXES = {
    "platform": ("/platform/",),
    "api": ("/api-reference/",),
    "open-source": ("/open-source/", "/components/"),
    "integrations": ("/integrations",),
}


def require_docs_url(url: str) -> None:
    """Exit unless the URL is an https URL on the Mem0 docs host."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc != DOCS_HOST:
        sys.exit(f"Refusing to fetch {url}: only {DOCS_BASE} is allowed")


class DocsRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects only when they stay on the Mem0 docs host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require_docs_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url(url: str, max_bytes: int) -> tuple[str, bool]:
    """Fetch at most max_bytes from a docs URL, returning the text and whether it was cut short."""
    require_docs_url(url)
    opener = urllib.request.build_opener(DocsRedirectHandler)
    req = urllib.request.Request(url, headers={"User-Agent": "Mem0DocSearchAgent/1.0"})
    try:
        with opener.open(req, timeout=15) as resp:
            data = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        sys.exit(f"Error fetching {url}: HTTP {e.code} {e.reason}")
    except OSError as e:
        sys.exit(f"Error fetching {url}: {e}")
    return data[:max_bytes].decode("utf-8", errors="replace"), len(data) > max_bytes


def index_entries() -> list:
    """Return the page entries listed in the llms.txt index."""
    content, truncated = fetch_url(LLMS_INDEX, MAX_INDEX_BYTES)
    if truncated:
        sys.exit(f"Error: {LLMS_INDEX} exceeds {MAX_INDEX_BYTES} bytes")
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
    content, cut_short = fetch_url(url, MAX_PAGE_CHARS * 4)
    return {"url": url, "content": content[:MAX_PAGE_CHARS], "truncated": cut_short or len(content) > MAX_PAGE_CHARS}


def get_index() -> dict:
    """Fetch the full documentation index from llms.txt."""
    urls = index_entries()
    return {"total_pages": len(urls), "urls": urls, "sections": list(SECTION_PREFIXES)}


def list_section(section: str) -> dict:
    """List the llms.txt index entries in a documentation section."""
    if section not in SECTION_PREFIXES:
        return {"error": f"Unknown section: {section}", "available": list(SECTION_PREFIXES)}
    pages = [e for e in index_entries() if entry_path(e).startswith(SECTION_PREFIXES[section])]
    return {"section": section, "pages": pages}


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
                    print(f"[Content truncated to {MAX_PAGE_CHARS} chars]")
                print(result["content"])
            elif "error" in result:
                print(f"Error: {result['error']}")
                if result.get("available"):
                    print(f"Available sections: {', '.join(result['available'])}")
            else:
                print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
