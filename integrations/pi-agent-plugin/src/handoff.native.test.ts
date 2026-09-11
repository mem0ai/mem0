import {expect, it} from "vitest";

const [major, minor] = process.versions.node.split(".").map(Number);
// The real Pi 0.79 SDK declares Node >=22.19; Node 20 tests cover startup and the explicit guard.
it.skipIf(major < 22 || (major === 22 && minor < 19))("native Pi resolves the selected leaf and readable compaction context", async () => {
  const {buildSessionContext, convertToLlm} = await import("@earendil-works/pi-coding-agent");
  const entries = [
    {type: "message", id: "old", parentId: null, message: {role: "user", content: "old context"}},
    {type: "message", id: "keep", parentId: "old", message: {role: "user", content: "retained tail"}},
    {type: "compaction", id: "compact", parentId: "keep", summary: "Native summary", firstKeptEntryId: "keep", tokensBefore: 100},
    {type: "message", id: "new", parentId: "compact", message: {role: "user", content: "Continue this task"}},
    {type: "message", id: "other", parentId: "old", message: {role: "user", content: "abandoned branch"}},
  ];
  const context = buildSessionContext(entries as Parameters<typeof buildSessionContext>[0], "new");
  const messages = JSON.stringify(convertToLlm(context.messages));
  expect(messages).toContain("Native summary");
  expect(messages).toContain("retained tail");
  expect(messages).toContain("Continue this task");
  expect(messages).not.toContain("old context");
  expect(messages).not.toContain("abandoned branch");
});
