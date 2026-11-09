import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText } from "../lib/api";
import type { MessagePage } from "../lib/types";

export function useMessages(
  token: string,
  report: (error: unknown) => void,
  active: boolean,
) {
  const [page, setPage] = useState<MessagePage>({ messages: [] });
  const [before, setBefore] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [notice, setNotice] = useState("");
  const [retrying, setRetrying] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setRefreshing(true);
    const query = new URLSearchParams({ limit: "50" });
    if (before) query.set("before", before);
    try {
      const result = await api<MessagePage>(token, `/messages?${query}`, {
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setPage(result);
      setError("");
      setUpdatedAt(new Date());
    } catch (failure) {
      if (controller.signal.aborted) return;
      setError(errorText(failure));
      report(failure);
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
        setRefreshing(false);
        request.current = null;
      }
    }
  }, [token, before, report]);

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    void load();
    const interval = window.setInterval(() => {
      if (!request.current) void load();
    }, 4000);
    return () => {
      window.clearInterval(interval);
      request.current?.abort();
      request.current = null;
    };
  }, [active, load]);

  const latest = useCallback(() => {
    setBefore(undefined);
    if (!before) void load();
  }, [before, load]);
  const retry = async (id: string) => {
    if (retrying) return;
    setRetrying(id);
    setNotice("");
    try {
      await api(token, `/deliveries/${id}/retry`, { method: "POST" });
      setNotice(
        "Failed delivery queued for another attempt. This is not yet a successful delivery.",
      );
      await load();
    } catch (failure) {
      setError(errorText(failure));
      report(failure);
    } finally {
      setRetrying(null);
    }
  };
  return {
    page,
    before,
    loading,
    refreshing,
    error,
    updatedAt,
    notice,
    retrying,
    load,
    latest,
    older: () => setBefore(page.next_cursor ?? undefined),
    retry,
  };
}

export type MessageHistory = ReturnType<typeof useMessages>;
