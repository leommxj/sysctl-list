export type SupportStatus = "context" | "exact" | "none";

export interface ReleaseVersion {
  releaseDate: string;
  tag: string;
}

export interface CatalogItem {
  availableVersions: string[];
  name: string;
  namespace: string;
  slug: string;
}

export interface BlobPayload {
  text: string;
}

export interface DocRef {
  blob: string;
  heading: string;
  lineEnd: number | null;
  lineStart: number | null;
  path: string;
}

export interface SourceRef {
  api: string;
  data_symbol: string;
  handler_symbol: string;
  path_segments: string[];
  source_path: string;
  table: string;
}

export interface ParamVersion {
  docRefs: DocRef[];
  hasDoc: boolean;
  hasSource: boolean;
  sourceRefs: SourceRef[];
  supportStatus: SupportStatus;
  tag: string;
}

export interface ParamPayload {
  availableVersions: string[];
  name: string;
  namespace: string;
  slug: string;
  versions: ParamVersion[];
}

export interface CatalogPayload {
  items: CatalogItem[];
}

export interface VersionsPayload {
  versions: ReleaseVersion[];
}
