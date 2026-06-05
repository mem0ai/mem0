#!/usr/bin/env bun
export {};
const DOCS_BASE = "https://docs.mem0.ai";
const SEARCH_ENDPOINT = `${DOCS_BASE}/api/search`;
const LLMS_INDEX = `${DOCS_BASE}/llms.txt`;

const SECTION_MAP: Record<string, string[]> = {
  platform: [
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
  api: [
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
  openmemory: [
    "/openmemory/overview",
    "/openmemory/quickstart",
  ],
  sdks: ["/sdks/python", "/sdks/js"],
  integrations: ["/integrations"],
};

async function fetchUrl(url: string): Promise<string> {
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "Mem0DocSearchAgent/1.0" },
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return `HTTP Error ${res.status}: ${res.statusText}`;
    return await res.text();
  } catch (e: any) {
    return `Error: ${e.message}`;
  }
}

async function searchDocs(query: string, section?: string) {
  const params = new URLSearchParams({ query });
  try {
    const result = await fetchUrl(`${SEARCH_ENDPOINT}?${params}`);
    const data = JSON.parse(result);
    if (data?.results) {
      let results = data.results;
      if (section && SECTION_MAP[section]) {
        const paths = SECTION_MAP[section];
        results = results.filter((r: any) =>
          paths.some((p) => r.url?.startsWith(p)),
        );
      }
      return { source: "mintlify_search", results };
    }
  } catch {}

  const indexContent = await fetchUrl(LLMS_INDEX);
  const queryLower = query.toLowerCase();
  let matching = indexContent
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#") && l.toLowerCase().includes(queryLower));

  if (section && SECTION_MAP[section]) {
    const paths = SECTION_MAP[section];
    matching = matching.filter((u) => paths.some((p) => u.includes(p)));
  }

  return {
    source: "llms_txt_index",
    query,
    matching_urls: matching.slice(0, 20),
    suggestion: "Fetch specific URLs for detailed content",
  };
}

async function fetchPage(pagePath: string) {
  const url = pagePath.startsWith("/") ? `${DOCS_BASE}${pagePath}` : pagePath;
  const content = await fetchUrl(url);
  return { url, content: content.slice(0, 10000), truncated: content.length > 10000 };
}

async function getIndex() {
  const content = await fetchUrl(LLMS_INDEX);
  const urls = content
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#"));
  return { total_pages: urls.length, urls, sections: Object.keys(SECTION_MAP) };
}

function listSection(section: string) {
  if (!SECTION_MAP[section]) {
    return { error: `Unknown section: ${section}`, available: Object.keys(SECTION_MAP) };
  }
  return { section, pages: SECTION_MAP[section].map((p) => `${DOCS_BASE}${p}`) };
}

function printResult(result: any) {
  if (result.results) {
    console.log(`Source: ${result.source ?? "unknown"}`);
    for (const r of result.results) {
      console.log(`  - ${r.title ?? "N/A"}: ${r.url ?? "N/A"}`);
      if (r.description) console.log(`    ${r.description.slice(0, 200)}`);
    }
  } else if (result.matching_urls) {
    console.log(`Source: ${result.source}`);
    console.log(`Query: ${result.query}`);
    for (const url of result.matching_urls) console.log(`  - ${url}`);
    if (result.suggestion) console.log(`\n${result.suggestion}`);
  } else if (result.urls) {
    console.log(`Total documentation pages: ${result.total_pages}`);
    console.log(`Sections: ${result.sections.join(", ")}`);
    for (const url of result.urls.slice(0, 30)) console.log(`  - ${url}`);
    if (result.total_pages > 30) console.log(`  ... and ${result.total_pages - 30} more`);
  } else if (result.pages) {
    console.log(`Section: ${result.section}`);
    for (const page of result.pages) console.log(`  - ${page}`);
  } else if (result.content) {
    console.log(`URL: ${result.url}`);
    if (result.truncated) console.log("[Content truncated to 10000 chars]");
    console.log(result.content);
  } else if (result.error) {
    console.log(`Error: ${result.error}`);
    if (result.available) console.log(`Available sections: ${result.available.join(", ")}`);
  } else {
    console.log(JSON.stringify(result, null, 2));
  }
}

const args = process.argv.slice(2);
const flags: Record<string, string | boolean> = {};
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--query" && args[i + 1]) flags.query = args[++i];
  else if (args[i] === "--page" && args[i + 1]) flags.page = args[++i];
  else if (args[i] === "--section" && args[i + 1]) flags.section = args[++i];
  else if (args[i] === "--index") flags.index = true;
  else if (args[i] === "--json") flags.json = true;
}

let result: any;
if (flags.index) {
  result = await getIndex();
} else if (flags.section && !flags.query) {
  result = listSection(flags.section as string);
} else if (flags.page) {
  result = await fetchPage(flags.page as string);
} else if (flags.query) {
  result = await searchDocs(flags.query as string, flags.section as string | undefined);
} else {
  console.log("Usage:");
  console.log("  bun scripts/mem0_doc_search.ts --query \"topic\"");
  console.log("  bun scripts/mem0_doc_search.ts --page \"/platform/features/graph-memory\"");
  console.log("  bun scripts/mem0_doc_search.ts --index");
  console.log("  bun scripts/mem0_doc_search.ts --section platform");
  process.exit(1);
}

if (flags.json) {
  console.log(JSON.stringify(result, null, 2));
} else {
  printResult(result);
}
