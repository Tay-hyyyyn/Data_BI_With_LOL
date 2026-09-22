/**
 * One fetch wrapper for the whole app. Every backend error response is `{"detail": string}`
 * (see `apps/backend/app/errors.py`); `ApiError` carries the status code so callers can branch
 * on it (e.g. 404 vs 422) without re-parsing the body.
 */

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function decode<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "요청을 처리하지 못했습니다." }));
    const detail =
      typeof payload?.detail === "string" ? payload.detail : "요청을 처리하지 못했습니다.";
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export function apiGet<T>(path: string): Promise<T> {
  return fetch(path).then(decode<T>);
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return fetch(path, {
    method: "POST",
    headers: JSON_HEADERS,
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(decode<T>);
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return fetch(path, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(body) }).then(
    decode<T>,
  );
}

export function apiUpload<T>(
  path: string,
  file: File,
  fields: Record<string, string> = {},
): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  return fetch(path, { method: "POST", body: form }).then(decode<T>);
}

/** Renders any thrown value as a user-facing Korean message; never leaks a raw stack trace. */
export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
