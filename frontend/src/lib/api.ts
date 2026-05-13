/* Typed API client.
   Backend's FastAPI generates /openapi.json → `openapi.json` → `api-types.ts`
   (via `pnpm gen:api`). This file is the *only* place fetches happen — every
   page goes through these strongly-typed helpers, so renaming a backend field
   shows up as a TS error in the page that consumed it. */
import type { components, paths } from "@/lib/api-types";

// Inline Literal[...] types in Pydantic don't get named aliases in OpenAPI;
// re-state them here so pages can reference them by stable names.
export type ConfidenceLevel = "high" | "mid" | "low" | "single";
export type AnnotationOp = "merge" | "split" | "bind_qid" | "is_person";
export type DataSource = "entity" | "raw_name" | "annotated";

export type Schemas = components["schemas"] & {
  ConfidenceLevel: ConfidenceLevel;
  AnnotationOp: AnnotationOp;
  DataSource: DataSource;
};
export type HealthResponse = Schemas["HealthResponse"];
export type SearchResponse = Schemas["SearchResponse"];
export type PersonDetail = Schemas["PersonDetail"];
export type DisambiguateResponse = Schemas["DisambiguateResponse"];
export type CompanyDetail = Schemas["CompanyDetail"];
export type Top10Row = Schemas["Top10Row"];
export type StackSeriesPoint = Schemas["StackSeriesPoint"];
export type NetworkResponse = Schemas["NetworkResponse"];
export type CrossHolder = Schemas["CrossHolder"];
export type CoholderPair = Schemas["CoholderPair"];
export type CoholderSummary = Schemas["CoholderSummary"];
export type CompanyHolding = Schemas["CompanyHolding"];
export type BucketMeta = Schemas["BucketMeta"];
export type BucketSummary = Schemas["BucketSummary"];
export type WikidataProfile = Schemas["WikidataProfile"];
export type AnnotationRequest = Schemas["AnnotationRequest"];
export type AnnotationResponse = Schemas["AnnotationResponse"];

type Paths = paths;

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = (await r.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(r.status, detail);
  }
  return (await r.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

type GetOp<P extends keyof Paths> = Paths[P] extends { get: infer G } ? G : never;
type ResponseOf<O> = O extends {
  responses: { 200: { content: { "application/json": infer R } } };
}
  ? R
  : never;
type QueryOf<O> = O extends { parameters: { query?: infer Q } } ? Q : never;

function withQuery(path: string, query?: Record<string, unknown>): string {
  if (!query) return path;
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    usp.set(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `${path}?${qs}` : path;
}

export function getHealth() {
  return apiGet<HealthResponse>("/api/health");
}

export function getSearch(q: string) {
  return apiGet<SearchResponse>(withQuery("/api/search", { q }));
}

export function getCompany(code: string, date?: string) {
  return apiGet<CompanyDetail>(withQuery(`/api/company/${encodeURIComponent(code)}`, { date }));
}

export function getPerson(name: string, bucket?: number) {
  return apiGet<PersonDetail>(withQuery(`/api/person/${encodeURIComponent(name)}`, { bucket }));
}

export function getDisambiguate(name: string) {
  return apiGet<DisambiguateResponse>(`/api/person/${encodeURIComponent(name)}/disambiguate`);
}

export function getNetwork(focus: string, hops = 1, minPct = 0) {
  return apiGet<NetworkResponse>(withQuery("/api/network", { focus, hops, min_pct: minPct }));
}

export function getTopCrossHolders(limit = 20) {
  return apiGet<CrossHolder[]>(withQuery("/api/discover/top-cross-holders", { limit }));
}

export function getTopCoholderPairs(limit = 50, minCo = 3) {
  return apiGet<CoholderPair[]>(
    withQuery("/api/discover/top-coholder-pairs", { limit, min_co: minCo }),
  );
}

export function postAnnotation(req: AnnotationRequest) {
  return apiPost<AnnotationResponse>("/api/annotation", req);
}

export function getAnnotations(limit = 50) {
  return apiGet<AnnotationResponse[]>(withQuery("/api/annotation", { limit }));
}

// Re-export operation-type helpers so pages can write
// `type R = ResponseOf<GetOp<"/api/person/{name}">>` if they ever need to.
export type { GetOp, QueryOf, ResponseOf };
