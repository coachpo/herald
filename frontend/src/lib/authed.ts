import { apiFetch } from "@/lib/api";

export type AuthLike = {
  accessToken: string | null;
  refresh: () => Promise<string | null>;
};

export async function authedFetch(
  auth: AuthLike,
  path: string,
  init: RequestInit = {},
) {
  const res1 = await apiFetch(path, { ...init, accessToken: auth.accessToken });
  if (res1.status !== 401) return res1;
  const tok = await auth.refresh();
  if (!tok) return res1;
  return apiFetch(path, { ...init, accessToken: tok });
}
