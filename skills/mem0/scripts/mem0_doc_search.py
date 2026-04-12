#!/usr/bin/env python3
"""
Mem0 Documentation Search Agent (Mintlify-based)
On-demand search tool for querying Mem0 documentation without storing content locally.

This tool leverages Mintlify's documentation structure to perform just-in-time
retrieval of technical information from docs.mem0.ai.

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

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

DOCS_BASE = "https://docs.mem0.ai"
SEARCH_ENDPOINT = f"{DOCS_BASE}/api/search"
LLMS_INDEX = f"{DOCS_BASE}/llms.txt"

# Known documentation sections for targeted retrieval
SECTION_MAP = {
    "platform": [
        "/platform/overview",
        "/platform/quickstart",
        "/platform/features",
        "/platform/features/graph-memory",
        "/platform/features/selective-memory",
        "/platform/features/custom-categories",
        "/platform/features/v2-memory-filters",
        "/platform/features/async-client",
        "/platform/features/webhooks",
        "/platform/features/multimodal-support",
    ],
    "api": [
        "/api-reference/memory/add-memories",
        "/api-reference/memory/v2-search-memories",
        "/api-reference/memory/v2-get-memories",
        "/api-reference/memory/get-memory",
        "/api-reference/memory/update-memory",
        "/api-reference/memory/delete-memory",
    ],
    "open-source": [
        "/open-source/overview",
        "/open-source/python-quickstart",
        "/open-source/node-quickstart",
        "/open-source/features",
        "/open-source/features/graph-memory",
        "/open-source/features/rest-api",
        "/open-source/configure-components",
    ],
    "sdks": [
        "/sdks/python",
        "/sdks/js",
    ],
    "integrations": [
        "/integrations",
    ],
}


def fetch_url(url: str) -> str:
    """Fetch content from a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mem0DocSearchAgent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"URL Error: {e.reason}"


def search_docs(query: str, section: str | None = None) -> dict:
    """
    Search Mem0 documentation using Mintlify's search API.
    Falls back to the llms.txt index for keyword matching if the API is unavailable.
    """
    # Try Mintlify search API first
    params = urllib.parse.urlencode({"query": query})
    search_url = f"{SEARCH_ENDPOINT}?{params}"

    try:
        result = fetch_url(search_url)
        data = json.loads(result)
        if isinstance(data, dict) and data.get("results"):
            results = data["results"]
            if section and section in SECTION_MAP:
                section_paths = SECTION_MAP[section]
                results = [r for r in results if any(r.get("url", "").startswith(p) for p in section_paths)]
            return {"source": "mintlify_search", "results": results}
    except (json.JSONDecodeError, Exception):
        pass

    # Fallback: search llms.txt index for matching URLs
    index_content = fetch_url(LLMS_INDEX)
    query_lower = query.lower()
    matching_urls = []

    for line in index_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if query_lower in line.lower():
            matching_urls.append(line)

    if section and section in SECTION_MAP:
        section_paths = SECTION_MAP[section]
        matching_urls = [u for u in matching_urls if any(p in u for p in section_paths)]

    return {
        "source": "llms_txt_index",
        "query": query,
        "matching_urls": matching_urls[:20],
        "suggestion": "Fetch specific URLs for detailed content",
    }


def fetch_page(page_path: str) -> dict:
    """Fetch a specific documentation page."""
    url = f"{DOCS_BASE}{page_path}" if page_path.startswith("/") else page_path
    content = fetch_url(url)
    return {"url": url, "content": content[:10000], "truncated": len(content) > 10000}


def get_index() -> dict:
    """Fetch the full documentation index from llms.txt."""
    content = fetch_url(LLMS_INDEX)
    urls = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
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
