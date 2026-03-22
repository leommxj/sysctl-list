import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { access } from "node:fs/promises";

const sourceDir = new URL("../../data/generated/", import.meta.url);
const targetDir = new URL("../public/data/", import.meta.url);

await rm(targetDir, { force: true, recursive: true });
await mkdir(targetDir, { recursive: true });

try {
  await access(new URL("catalog.json", sourceDir));
  await cp(sourceDir, targetDir, { recursive: true });
} catch {
  await mkdir(new URL("params/", targetDir), { recursive: true });
  await mkdir(new URL("blobs/", targetDir), { recursive: true });
  await writeFile(new URL("catalog.json", targetDir), JSON.stringify({ items: [] }, null, 2));
  await writeFile(new URL("versions.json", targetDir), JSON.stringify({ versions: [] }, null, 2));
}

