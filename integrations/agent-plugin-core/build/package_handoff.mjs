import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

export async function packageHandoff(output = "dist") {
  const manifest = JSON.parse(await readFile(new URL("./handoff-runtime.json", import.meta.url), "utf8"));
  await mkdir(output, { recursive: true });
  for (const [name, digest] of Object.entries(manifest.files)) {
    const bytes = await readFile(new URL(`../python/${name}`, import.meta.url));
    if (createHash("sha256").update(bytes).digest("hex") !== digest) throw new Error(`Update the shared handoff runtime pin after changing ${name}`);
  }
  for (const name of Object.keys(manifest.files)) await rm(resolve(output, name), { force: true });
  for (const name of manifest.artifacts) {
    const source = name.endsWith(".py") ? `../python/${name}` : `./${name}`;
    await copyFile(new URL(source, import.meta.url), resolve(output, name));
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await packageHandoff(process.argv[2]);
}
