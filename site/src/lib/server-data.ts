import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import type { CatalogPayload, ParamPayload, VersionsPayload } from "./types";

const dataRoot = resolve(process.cwd(), "public", "data");

export async function loadCatalog(): Promise<CatalogPayload> {
  return readJson<CatalogPayload>(resolve(dataRoot, "catalog.json"));
}

export async function loadVersions(): Promise<VersionsPayload> {
  return readJson<VersionsPayload>(resolve(dataRoot, "versions.json"));
}

export async function loadParam(slug: string): Promise<ParamPayload> {
  return readJson<ParamPayload>(resolve(dataRoot, "params", `${slug}.json`));
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}
