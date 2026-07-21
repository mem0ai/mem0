const assert = require('assert');
const path = require('path');
const { inferComponentLabels, loadKeywords } = require('./infer-component-labels.js');

const keywords = loadKeywords(path.join(__dirname, '..', 'component-keywords.json'));

const cases = [
  {
    number: 6210,
    title: "but(anthropic): sampling parameters returns 400 error for new model",
    body: "### Component\n\nCore / Python SDK\n\n### Description\n\n### Summary\n\nWhen using Anthropic latest models such as `claude-opus-4-7`, `claude-opus-4-8`, or `claude-sonnet-5`, Mem0 still sends sampling parameters like `temperature` / `top_p`. These models do not support those parameters, causing Anthropic API requests to fail.\n\nSee https://platform.claude.com/docs/en/about-claude/models/migration-guide\n\n### Steps to Reproduce\n\n```python\n  from mem0 import Memory\n\n  m = Memory.from_config({\n      \"llm\": {\n          \"provider\": \"anthropic\",\n          \"config\": {\n              \"model\": \"claude-opus-4-8\",\n              \"api_key\": \"your-anthropic-api-key\"\n          },\n      },\n      ...\n  })\n```\n\n### Expected Behavior\n\nMem0 should detect Anthropic models that do not support sampling parameters and omit temperature and top_p from the request.\n\nFor models that still support sampling parameters, such as claude-opus-4-6, claude-sonnet-4-6, and claude-haiku-4-5, Mem0 should continue sending supported sampling parameters till they're deprecated.\n\n### Actual Behavior\n\nMem0 includes temperature by default for Anthropic requests. With newer Anthropic models that do not support sampling parameters, the API request fails because unsupported parameters are sent.\n\n### Environment\n\n  - mem0 version: 2.0.11\n  - Python/Node version: Python 3.11\n  - OS: macOS\n",
    expected: ["sdk-python"],
  },
  {
    number: 5770,
    title: "feat(ts-sdk): add FastEmbed embedding provider",
    body: "## Summary\n\nThe Python SDK supports **FastEmbed** as an embedding provider, but the TypeScript OSS SDK (`mem0ai/oss`) does not. Add it to bring the TS SDK to parity.\n\n| | |\n|---|---|\n| Python reference | `mem0/embeddings/fastembed.py` |\n| Registered in (Python) | `mem0/utils/factory.py` (EmbedderFactory) |\n| Target file (TypeScript) | `mem0-ts/src/oss/src/embeddings/fastembed.ts` |\n| Suggested implementation | Use the `fastembed` npm package (ONNX local embeddings). |\n\n## Requirements\n\n- [ ] Implement `FastEmbedEmbedder` in `mem0-ts/src/oss/src/embeddings/fastembed.ts`, extending `Embedder` (`mem0-ts/src/oss/src/embeddings/base.ts`) and mirroring the Python provider's behavior (embed / embedBatch).\n- [ ] Register the `\"fastembed\"` provider in `mem0-ts/src/oss/src/utils/factory.ts` (EmbedderFactory).\n- [ ] Add config typing in `mem0-ts/src/oss/src/types/`.\n- [ ] Add a unit test under `mem0-ts/src/oss/src/tests/`.\n- [ ] Add `fastembed` to `mem0-ts/package.json` (optional/peer dependency, lazy-imported like other providers).\n- [ ] Update docs under `docs/` if this provider is user-facing.\n\n## Reference pattern\n\nMirror an existing TS provider: `embeddings/openai.ts`.\n\n## Notes\n\n`fastembed` (v2.x) is the JS port of Qdrant's FastEmbed — local/offline embeddings. Mirror the default model in `mem0/embeddings/fastembed.py`.\n\n---\n_Part of the TypeScript ↔ Python SDK provider-parity effort. One provider per issue (atomic)._\n",
    expected: ["sdk-typescript"],
  },
  {
    number: 3940,
    title: "Milvus database will return distance not similarity score",
    body: "### 🐛 Describe the bug\n\nMilvus database will return distance not similarity score\n\n## in milvus.py\n\ndef _parse_output(self, data: list):\n        \"\"\"\n        Parse the output data.\n\n        Args:\n            data (Dict): Output data.\n\n        Returns:\n            List[OutputData]: Parsed output data.\n        \"\"\"\n        memory = []\n\n        for value in data:\n            uid, score, metadata = (\n                value.get(\"id\"),\n                value.get(\"distance\"),  # here\n                value.get(\"entity\", {}).get(\"metadata\"),\n            )\n\n            memory_obj = OutputData(id=uid, score=score, payload=metadata)\n            memory.append(memory_obj)\n\n        return memory\n",
    expected: ["vector-store"],
  },
  {
    number: 5290,
    title: "Recall search failed: Bad Request Using OpenAI Embedding Model",
    body: "### Component\n\nOpenClaw\n\n### Description\n\n### Summary\nuse openclaw.json config:\n\n```json\n...\n\"embedder\": {\n              \"provider\": \"openai\",\n              \"config\": {\n                \"model\": \"bge-base-zh-v1.5\",\n                \"embedding_dims\": 1024,\n                \"embeddingDims\": 1024,\n                \"url\": \"https://xxxxxxxxx/v1\",\n                \"apiKey\": \"xxxxxxxxxxxx\"\n              }\n            },\n\"vectorStore\": {\n              \"provider\": \"qdrant\",\n              \"config\": {\n                \"url\": \"http://qdrant:6333\",\n                \"apiKey\": \"${QDRANT_API_KEY}\",\n                \"collectionName\": \"mem0\",\n                \"embeddingModelDims\": 1024\n              }\n            }\n```\n```\n\nopenclaw log info is：\n\n```\n23:14:20 Api key is used with unsecure connection.\n23:14:21 [mem0] Recall search failed: Bad Request\n23:14:21 [plugins] openclaw-mem0: skills-mode recall (strategy=smart) injecting 0 memories (~20 tokens)\n23:14:22 [ws] ⇄ res ✓ sessions.list 256ms conn=d1eb9bc4…17da id=201b8113…c9dc\n23:14:22 [ws] ⇄ res ✓ sessions.list 264ms conn=d1eb9bc4…17da id=4939f962…2f16\n23:14:34 [ws] ⇄ res ✓ sessions.list 250ms conn=d1eb9bc4…17da id=f7ad503f…baa6\n23:15:12 [mem0] **Recall search failed: Bad Request**\n23:15:12 [plugins] openclaw-mem0: skills-mode recall (strategy=smart) injecting 0 memories (~20 tokens)\n23:15:12 [ws] ⇄ res ✓ sessions.list 288ms conn=d1eb9bc4…17da id=9e20bb86…371e\n23:15:13 [ws] ⇄ res ✓ sessions.list 268ms conn=d1eb9bc4…17da id=3b49a2ad…7ada\n23:15:20 [ws] ⇄ res ✓ sessions.list 235ms conn=d1eb9bc4…17da id=a192da30…069f\n```\n\n### Actual Behavior\n\nembedding model response ok,response message has 1024 vectors,but the vectors are submitted to vector-db:qdrant with all zero vectors,and vectors has only 256 size.\n\n```http\nPOST /collections/mem0/points/search HTTP/1.1\nhost: qdrant:6333\nconnection: keep-alive\nuser-agent: qdrant-js/1.13.0\napi-key: xxxxxxxxxxxxxxxxxxxxxxxxxxxx\nContent-Type: application/json\nAccept: application/json\naccept-language: *\nsec-fetch-mode: cors\naccept-encoding: gzip, deflate\ncontent-length: 651\n\n{\"vector\":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],\"limit\":120,\"offset\":0,\"filter\":{\"must\":[{\"key\":\"user_id\",\"match\":{\"value\":\"agent\"}}]},\"with_payload\":true,\"with_vector\":false}\n\n**HTTP/1.1 400 Bad Request**\ntransfer-encoding: chunked\ncontent-type: application/json\nvary: accept-encoding, Origin, Access-Control-Request-Method, Access-Control-Request-Headers\ncontent-encoding: gzip\n\n```\n\n### Expected Behavior\n\nembedding model response ok by tcpdump, response message has 1024 vectors,and this vectors are submitted to vector-db:qdrant with the same vectors,and vectors has also 1024 size.\n\n\n### Environment\n\n- openclaw-mem0 version: 1.0.11\n- qdrant: 1.13.6\n",
    expected: ["plugin", "integrations"],
  },
  {
    number: 3696,
    title: "Cannot set expiration_date for memory in REST API server (Docker Compose)",
    body: "### 🐛 Describe the bug\n\nI'm using docker compose to deploy a REST API server. When adding memory, I'm unable to set the expiration_date. Is this feature not supported?",
    expected: ["rest-api"],
  },
  {
    number: 3444,
    title: "Fix: Openmemory run.sh non-existent vector-store route",
    body: "### 🐛 Describe the bug\n\n# Vector_store not implemented\nThere is many references to ` ${NEXT_PUBLIC_API_URL}/api/v1/config/mem0/vector_store` in lines 280, 293, 306, 319,  332, 345, 358, and 371. \n```bash\ncurl -fsS -X PUT \"${NEXT_PUBLIC_API_URL}/api/v1/config/mem0/vector_store\" # Line 280 and for each vector store\n```\nBut the api route is not implemented in `api/app/routers/config.py`.\n# Suggested solution\nI would implement `vector_store` route or remove and use `update_configuration` for all config updates. Also Create class with all config keys for vector_store",
    expected: ["openmemory"],
  },
  {
    number: 6252,
    title: "cursor: on_file_read_cursor.sh ignores auto_search / MEM0_AUTO_SEARCH",
    body: "### Component\n\nCursor / mem0-plugin\n\n### Description\n\n`on_file_read_cursor.sh` never checks `MEM0_AUTO_SEARCH`. In Claude Code, #6065/#6071 added a guard on `on_file_read.sh`, but the Cursor PreToolUse variant still always calls `file_context.py` (and thus Platform search) once `MEM0_API_KEY` is set.\n\n### Expected\n\nWhen `auto_search: false` / `MEM0_AUTO_SEARCH=false`, `on_file_read_cursor.sh` should exit 0 without searching.\n\n### Actual\n\nTimeline search still runs.\n\n### Related\n\n#6065, #6071, #6250\n",
    expected: ["plugin", "integrations"],
  },
  {
    number: 6032,
    title: "docs: fix typos and punctuation errors across docs",
    body: "### Description\n\n### Page\nMultiple pages — see list below.\n\n### What's Wrong or Missing\n1. https://docs.mem0.ai/components/llms/overview — \"a llm\" should be \"an LLM\"\n2. https://docs.mem0.ai/components/vectordbs/dbs/azure — 2 comma splices + \"setup\" used as a verb (should be \"set up\")\n3. https://docs.mem0.ai/components/embedders/models/azure_openai — \"from the Azure.\" is an incomplete sentence\n4. https://docs.mem0.ai/components/llms/models/azure_openai — same incomplete \"from the Azure\" phrasing\n5. https://docs.mem0.ai/cookbooks/companions/voice-companion-openai — \"an important information\" (uncountable noun)\n6. https://docs.mem0.ai/cookbooks/essentials/exporting-memories — comma splice\n7. https://docs.mem0.ai/cookbooks/integrations/tavily-search — \"usecase\" should be \"use case\"\n8. https://docs.mem0.ai/cookbooks/overview — broken parallelism in bullet list\n9. README.md — \"Github App\" should be \"GitHub App\"\n10. https://docs.mem0.ai/platform/overview — table cell not capitalized like other rows\n\n### Suggested Fix\nApply the corrections listed above for each page. I will submit a PR soon addressing all of the issues mentioned.",
    expected: ["documentation"],
  },
];

const cliRegressionCase = {
  number: 3144,
  title: "Bug Report: Memory Score Does Not Match Expected Relevance in Local Search",
  body: "### 🐛 Describe the bug\n\n#### Description\n\nWhen using the locally deployed `mem0` server, the returned memory `score` from the `search` interface does not align with the expected semantic relevance. In particular, irrelevant or less relevant memories sometimes receive higher scores than directly related ones.\n\n#### Reproduction Steps\n\n```python\nmem0 = mem0_client(mode=\"local\")\nprint(\"Mem0 client initialized successfully.\")\n\nprint(\"Adding memories...\")\nresult = mem0.add(messages=[\n    {\"role\": \"user\", \"content\": \"I like drinking coffee in the morning\"},\n    {\"role\": \"user\", \"content\": \"I enjoy reading books at night\"}\n], user_id=\"alice\")\nprint(\"Memory added:\", result)\n\nprint(\"Searching memories...\")\nsearch_result = mem0.search(query=\"coffee\", user_id=\"alice\", top_k=2)\nprint(\"Search results:\", search_result)\n```\n\n#### Actual Output\n\n```json\n{\n  \"results\": [\n    {\n      \"id\": \"5099b5be-c673-4f09-99de-a196f43b6476\",\n      \"memory\": \"Likes drinking coffee in the morning\",\n      \"score\": 0.5115111920687857\n    },\n    {\n      \"id\": \"08df5c51-c52b-4c45-a5b6-b3f864ea149a\",\n      \"memory\": \"Enjoys reading books at night\",\n      \"score\": 0.7755568273863331\n    }\n  ],\n  \"relations\": [\n    {\"source\": \"coffee\", \"relationship\": \"consumed_in\", \"destination\": \"morning\"},\n    {\"source\": \"user_id:_alice\", \"relationship\": \"likes\", \"destination\": \"coffee\"},\n    {\"source\": \"user_id:_alice\", \"relationship\": \"likes_drinking\", \"destination\": \"coffee\"},\n    {\"source\": \"user_id:_alice\", \"relationship\": \"in_time\", \"destination\": \"morning\"},\n    {\"source\": \"user_id:_alice\", \"relationship\": \"drinks_in\", \"destination\": \"morning\"}\n  ]\n}\n```\n\n#### Expected Behavior\n\nThe memory `\"Likes drinking coffee in the morning\"` should have a **higher score** than `\"Enjoys reading books at night\"` when querying for `\"coffee\"`, since it is directly semantically related.",
};

let failures = 0;

function run(name, fn) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (err) {
    failures++;
    console.error(`FAIL ${name}: ${err.message}`);
  }
}

for (const { number, title, body, expected } of cases) {
  const text = `${title}

${body}`;
  run(`#${number}`, () => {
    assert.deepStrictEqual(inferComponentLabels(text, keywords), expected);
  });
}

run('#3144 cliKeywordPrefixSubstringRegression', () => {
  const text = `${cliRegressionCase.title}

${cliRegressionCase.body}`;
  const inferred = inferComponentLabels(text, keywords);
  assert.ok(!inferred.includes('cli'), `expected 'cli' absent (body contains 'Mem0 client', a substring of the removed 'mem0 cli' term), got ${JSON.stringify(inferred)}`);
});

run('noKeywordMatchReturnsEmptyArray', () => {
  const text = 'The weather today is sunny and I went for a walk in the park with my dog.';
  assert.deepStrictEqual(inferComponentLabels(text, keywords), []);
});

run('emptyStringReturnsEmptyArray', () => {
  assert.deepStrictEqual(inferComponentLabels('', keywords), []);
});

if (failures > 0) {
  console.error(`
${failures} test(s) failed.`);
  process.exit(1);
}
console.log(`
All ${cases.length + 3} tests passed.`);
