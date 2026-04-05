import type { ApiError } from "@/lib/types";

import { buildPublicApiUrl } from "@/lib/public-api";

export async function readJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export async function readApiError(res: Response): Promise<ApiError> {
  try {
    const data = await readJson<ApiError>(res);
    if (data && typeof data.code === "string" && typeof data.message === "string") {
      return data;
    }
  } catch {
  }
  return { code: "http_error", message: `HTTP ${res.status}` };
}

export function readRequestError(error: unknown): ApiError {
  if (error instanceof Error) {
    const message = error.message.trim();
    if (message && message !== "Failed to fetch") {
      return { code: "request_failed", message };
    }
  }

  return {
    code: "request_failed",
    message: "Request failed. Check the server and try again.",
  };
}

export async function apiFetch(
  path: string,
  init: RequestInit & { accessToken?: string | null } = {},
) {
  const { accessToken, headers, ...rest } = init;
  const h = new Headers(headers);
  if (accessToken) {
    h.set("Authorization", `Bearer ${accessToken}`);
  }
  h.set("Accept", "application/json");

  const url = buildPublicApiUrl(path);
  return fetch(url, {
    ...rest,
    headers: h,
    credentials: "omit",
  });
}
