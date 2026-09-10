import { copyFile, mkdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

export async function packageHandoff(output = "dist") {
  const files = JSON.parse(await readFile(new URL("./handoff-runtime.json", import.meta.url), "utf8"));
  await mkdir(output, { recursive: true });
  for (const name of files) {
    await copyFile(new URL(`../python/${name}`, import.meta.url), resolve(output, name));
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await packageHandoff(process.argv[2]);
}
