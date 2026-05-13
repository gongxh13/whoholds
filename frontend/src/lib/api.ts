/* Thin fetch wrapper. PR 3 replaces hand-typed responses here with codegen'd
   types from openapi-typescript-codegen against /openapi.json. */

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = (await r.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // body not JSON — keep statusText
    }
    throw new ApiError(r.status, detail);
  }
  return (await r.json()) as T;
}

export interface HealthResponse {
  status: string;
  databases: Record<string, boolean>;
}
