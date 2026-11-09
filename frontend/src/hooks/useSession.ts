import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, errorText } from "../lib/api";
import type { Settings, Target } from "../lib/types";

const TOKEN_KEY = "herald_admin_token";

export function useSession() {
  const epochRef = useRef(0);
  const [epoch, setEpoch] = useState(0);
  const isCurrent = useCallback(() => epochRef.current === epoch, [epoch]);
  const [token, setToken] = useState(
    () => sessionStorage.getItem(TOKEN_KEY) ?? "",
  );
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(Boolean(token));
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState("");
  const [targets, setTargets] = useState<Target[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [resourceError, setResourceError] = useState("");

  const disconnect = useCallback(() => {
    epochRef.current += 1;
    setEpoch(epochRef.current);
    sessionStorage.removeItem(TOKEN_KEY);
    setToken("");
    setAuthenticated(false);
    setChecking(false);
    setTargets([]);
    setSettings(null);
    setError("");
    setResourceError("");
  }, []);
  const report = useCallback(
    (failure: unknown) => {
      if (!isCurrent()) return;
      if (failure instanceof ApiError && failure.status === 401) {
        disconnect();
        setError(
          "Your connection is no longer authorized. Connect with your management token again.",
        );
      }
    },
    [disconnect, isCurrent],
  );

  const reloadTargets = useCallback(async () => {
    if (!isCurrent()) return;
    const result = await api<{ targets: Target[] }>(token, "/targets");
    if (isCurrent()) setTargets(result.targets);
  }, [token, isCurrent]);

  const reloadResources = useCallback(
    async (signal?: AbortSignal) => {
      if (!isCurrent()) return;
      setResourcesLoading(true);
      setResourceError("");
      try {
        const [targetResult, settingsResult] = await Promise.all([
          api<{ targets: Target[] }>(token, "/targets", { signal }),
          api<Settings>(token, "/settings", { signal }),
        ]);
        if (signal?.aborted || !isCurrent()) return;
        setTargets(targetResult.targets);
        setSettings(settingsResult);
      } catch (failure) {
        if (signal?.aborted || !isCurrent()) return;
        report(failure);
        setResourceError(errorText(failure));
      } finally {
        if (!signal?.aborted && isCurrent()) setResourcesLoading(false);
      }
    },
    [token, report, isCurrent],
  );

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setChecking(true);
    void api<{ authenticated: boolean }>(token, "/session", {
      signal: controller.signal,
    })
      .then(async () => {
        if (controller.signal.aborted) return;
        sessionStorage.setItem(TOKEN_KEY, token);
        setAuthenticated(true);
        setChecking(false);
        setError("");
        await reloadResources(controller.signal);
      })
      .catch((failure) => {
        if (controller.signal.aborted) return;
        if (failure instanceof ApiError && failure.status === 401) disconnect();
        setError(errorText(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false);
      });
    return () => controller.abort();
  }, [token, attempt, disconnect, reloadResources]);

  const connect = (value: string) => {
    if (!value.trim()) return;
    epochRef.current += 1;
    setEpoch(epochRef.current);
    setError("");
    setChecking(true);
    setToken(value.trim());
    setAttempt((previous) => previous + 1);
  };
  return {
    token,
    authenticated,
    checking,
    error,
    connect,
    disconnect,
    report,
    targets,
    settings,
    reloadTargets,
    reloadResources,
    resourcesLoading,
    resourceError,
  };
}
