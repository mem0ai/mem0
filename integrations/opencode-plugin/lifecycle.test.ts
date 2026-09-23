import {afterEach, expect, test} from "bun:test";
import Mem0Plugin from "./opencode-mem0";
import {resolveRepoContext} from "../agent-plugin-core/typescript/src/identity.ts";

const originalFetch = globalThis.fetch;
const originalEnv = {...process.env};

afterEach(() => {
  globalThis.fetch = originalFetch;
  process.env = {...originalEnv};
  for (const listener of process.listeners("beforeExit")) process.off("beforeExit", listener);
});

async function startPlugin() {
  const calls: {url: string; body: any}[] = [];
  process.env.MEM0_API_KEY = "m0-test";
  process.env.MEM0_USER_ID = "alice";
  process.env.MEM0_TELEMETRY = "false";
  globalThis.fetch = (async (input: any, init?: any) => {
    const url = typeof input === "string" ? input : input.url;
    const body = init?.body ? JSON.parse(init.body) : undefined;
    calls.push({url, body});
    const response = url.includes("/v1/ping/")
      ? {status: "ok", user_email: "alice@mem0.dev"}
      : url.includes("/search/")
        ? {results: [{id: "m1", memory: "Tests run with bun test"}]}
        : {};
    return new Response(JSON.stringify(response), {status: 200, headers: {"content-type": "application/json"}});
  }) as typeof fetch;
  const hooks: any = await Mem0Plugin({
    client: {app: {log: async () => {}}},
    directory: process.cwd(),
  } as any);
  return {hooks, calls, adds: () => calls.filter((c) => c.url.includes("/memories/add/"))};
}

async function exchange(hooks: any, sessionID: string, prompt: string, reply: string) {
  await hooks["chat.message"]({sessionID}, {message: {}, parts: [{type: "text", text: prompt}]});
  await hooks["experimental.text.complete"]({sessionID, messageID: `a-${prompt}`, partID: "p"}, {text: reply});
  await hooks.event({event: {type: "session.idle", properties: {sessionID}}});
}

test("recalls once on the first prompt and keeps injecting that context", async () => {
  const {hooks, calls} = await startPlugin();
  await hooks["chat.message"]({sessionID: "s1"}, {message: {}, parts: [{type: "text", text: "How do I run the tests here?"}]});
  await hooks["chat.message"]({sessionID: "s1"}, {message: {}, parts: [{type: "text", text: "And how do I build the plugin?"}]});

  const searches = calls.filter((c) => c.url.includes("/search/"));
  expect(searches).toHaveLength(1);
  expect(searches[0].body).toMatchObject({top_k: 5, rerank: false, latest_only: true});
  expect(searches[0].body.filters.OR[1]).toEqual({AND: [{user_id: "alice"}, {app_id: expect.any(String)}]});

  const messages = [{info: {role: "user", sessionID: "s1"}, parts: [{type: "text", text: "How do I run the tests here?"}]}];
  await hooks["experimental.chat.messages.transform"]({}, {messages});
  await hooks["experimental.chat.messages.transform"]({}, {messages});
  expect(messages[0].parts).toHaveLength(2);
  expect(messages[0].parts[0].text).toContain("1. Tests run with bun test");
});

test("captures the conversation at checkpoints and on session end", async () => {
  const {hooks, adds} = await startPlugin();
  for (let turn = 0; turn < 6; turn++) await exchange(hooks, "s2", `question ${turn}`, `answer ${turn}`);

  expect(adds()).toHaveLength(1);
  const body = adds()[0].body;
  expect(body.messages).toHaveLength(10);
  expect(body.messages[9]).toEqual({role: "assistant", content: "answer 4"});
  expect(body).toMatchObject({user_id: "alice", run_id: "s2", infer: true, metadata: {source: "opencode", author: "alice"}});
  const repo = resolveRepoContext(process.cwd());
  expect(body).toMatchObject({agent_id: repo.projectId, app_id: repo.appId});
  expect(body.custom_categories.map((c: object) => Object.keys(c)[0])).toContain("problems_and_fixes");
  expect(body.agent_custom_instructions).toStartWith("Save concise repository facts");

  await hooks.event({event: {type: "session.deleted", properties: {info: {id: "s2"}}}});
  expect(adds()).toHaveLength(2);
  expect(adds()[1].body.messages).toEqual([
    {role: "user", content: "question 5"},
    {role: "assistant", content: "answer 5"},
  ]);
});

test("ignores subagent sessions", async () => {
  const {hooks, calls} = await startPlugin();
  await hooks.event({event: {type: "session.created", properties: {info: {id: "child", parentID: "s3"}}}});
  await exchange(hooks, "child", "How do I run the tests here?", "done");
  await hooks.event({event: {type: "session.deleted", properties: {info: {id: "child"}}}});
  expect(calls.filter((c) => c.url.includes("/memories/"))).toHaveLength(0);
});
