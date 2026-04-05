import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { apiFetch, readApiError, readJson, readRequestError } from "@/lib/api";
import type { ApiError, User } from "@/lib/types";

type AuthState = {
  loading: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
};

type AuthContextValue = AuthState & {
  refresh: () => Promise<string | null>;
  login: (email: string, password: string) => Promise<ApiError | null>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const REFRESH_TOKEN_STORAGE_KEY = "herald_refresh_token";

function readStoredRefreshToken(): string | null {
  try {
    return sessionStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredRefreshToken(tok: string | null) {
  try {
    if (tok) sessionStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, tok);
    else sessionStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
  } catch {
  }
}

function parseJwtExpMs(jwtToken: string): number | null {
  const parts = jwtToken.split(".");
  if (parts.length !== 3) return null;
  try {
    const payloadJson = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    const payload = JSON.parse(payloadJson) as { exp?: unknown };
    const exp = typeof payload.exp === "number" ? payload.exp : null;
    return exp ? exp * 1000 : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(() => ({
    loading: true,
    accessToken: null,
    refreshToken: readStoredRefreshToken(),
    user: null,
  }));

  const refreshTokenRef = useRef<string | null>(state.refreshToken);
  const refreshInFlightRef = useRef<Promise<string | null> | null>(null);
  const refreshTimerRef = useRef<number | null>(null);

  const setTokens = useCallback((args: { accessToken: string | null; refreshToken: string | null; user: User | null }) => {
    refreshTokenRef.current = args.refreshToken;
    writeStoredRefreshToken(args.refreshToken);
    setState((s) => ({
      ...s,
      loading: false,
      accessToken: args.accessToken,
      refreshToken: args.refreshToken,
      user: args.user,
    }));
  }, []);

  const refresh = useCallback(async () => {
    if (refreshInFlightRef.current) return refreshInFlightRef.current;

    const p = (async () => {
      const currentRefresh = refreshTokenRef.current;
      if (!currentRefresh) {
        setTokens({ accessToken: null, refreshToken: null, user: null });
        return null;
      }

      setState((s) =>
        s.accessToken === null && s.user === null ? { ...s, loading: true } : s,
      );

      try {
        const res = await apiFetch("/api/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: currentRefresh }),
        });
        if (!res.ok) {
          if (res.status === 401) {
            setTokens({ accessToken: null, refreshToken: null, user: null });
          } else {
            setState((s) => ({ ...s, loading: false }));
          }
          return null;
        }

        const data = await readJson<{ access_token: string; refresh_token: string; user: User }>(res);
        setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token, user: data.user });
        return data.access_token;
      } catch {
        setState((s) => ({ ...s, loading: false }));
        return null;
      }
    })();

    refreshInFlightRef.current = p;
    try {
      return await p;
    } finally {
      refreshInFlightRef.current = null;
    }
  }, [setTokens]);

  const login = useCallback(async (email: string, password: string) => {
    try {
      const res = await apiFetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        return await readApiError(res);
      }
      const data = await readJson<{ access_token: string; refresh_token: string; user: User }>(res);
      setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token, user: data.user });
      return null;
    } catch (error) {
      return readRequestError(error);
    }
  }, [setTokens]);

  const logout = useCallback(async () => {
    const refreshToken = refreshTokenRef.current;
    try {
      if (refreshToken) {
        await apiFetch("/api/auth/logout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    } finally {
      setTokens({ accessToken: null, refreshToken: null, user: null });
    }
  }, [setTokens]);

  useEffect(() => {
    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    if (!state.accessToken || !state.refreshToken) return;

    const expMs = parseJwtExpMs(state.accessToken);
    if (!expMs) return;

    const now = Date.now();
    const skewMs = 60_000;
    const delayMs = Math.max(0, expMs - now - skewMs);
    refreshTimerRef.current = window.setTimeout(() => {
      void refresh();
    }, delayMs);

    return () => {
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [state.accessToken, state.refreshToken, refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, refresh, login, logout }),
    [state, refresh, login, logout],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider missing");
  return ctx;
}
