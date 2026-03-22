import type { BlobPayload, CatalogPayload, ParamPayload, VersionsPayload } from "./types";

const cache = new Map<string, Promise<unknown>>();
const base = import.meta.env.BASE_URL;

function dataUrl(path: string): string {
  return `${base}data/${path}`;
}

export function upstreamPathHref(tag: string, path: string, lineStart?: number | null, lineEnd?: number | null): string {
  const encodedPath = path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  const anchor =
    lineStart && lineEnd && lineEnd > lineStart
      ? `#L${lineStart}-L${lineEnd}`
      : lineStart
        ? `#L${lineStart}`
        : "";
  return `https://github.com/torvalds/linux/blob/${encodeURIComponent(tag)}/${encodedPath}${anchor}`;
}

export function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function loadCatalog(): Promise<CatalogPayload> {
  return fetchJson<CatalogPayload>("catalog.json");
}

export function loadVersions(): Promise<VersionsPayload> {
  return fetchJson<VersionsPayload>("versions.json");
}

export function loadParam(slug: string): Promise<ParamPayload> {
  return fetchJson<ParamPayload>(`params/${slug}.json`);
}

export function loadBlob(id: string): Promise<BlobPayload> {
  return fetchJson<BlobPayload>(`blobs/${id}.json`);
}

function fetchJson<T>(path: string): Promise<T> {
  const url = dataUrl(path);
  const existing = cache.get(url);
  if (existing) {
    return existing as Promise<T>;
  }
  const request = fetch(url).then(async (response) => {
    if (!response.ok) {
      throw new Error(`Failed to load ${url}`);
    }
    return (await response.json()) as T;
  });
  cache.set(url, request);
  return request;
}
