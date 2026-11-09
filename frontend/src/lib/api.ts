export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function api<T>(
  token: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: "omit",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data: { detail?: unknown; message?: string } =
        await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (typeof data.message === "string") message = data.message;
      else if (Array.isArray(data.detail)) {
        message = data.detail
          .map((item: { msg?: string }) => item.msg ?? "Invalid input")
          .join("; ");
      }
    } catch {
      /* Keep the HTTP status if an intermediary returns non-JSON. */
    }
    throw new ApiError(message, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}
