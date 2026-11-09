import { useCallback, useEffect, useState } from "react";
import { ApiError, errorText, getRouting, putRouting } from "../lib/api";
import type { RoutingConfig, RoutingRule } from "../lib/types";

export function useRouting(token: string, report: (error: unknown) => void) {
  const [saved, setSaved] = useState<RoutingConfig | null>(null);
  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [conflict, setConflict] = useState(false);
  const dirty =
    saved !== null && JSON.stringify(saved.rules) !== JSON.stringify(rules);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError("");
      setNotice("");
      try {
        const result = await getRouting(token, signal);
        if (signal?.aborted) return;
        setSaved(result);
        setRules(result.rules);
        setConflict(false);
      } catch (failure) {
        if (signal?.aborted) return;
        report(failure);
        setError(
          `Couldn’t load routing rules. ${errorText(failure)} Your existing draft has been kept.`,
        );
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [token, report],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (!dirty) return;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [dirty]);

  const changeRules = (next: RoutingRule[]) => {
    setRules(next);
    setNotice("");
  };

  const save = async () => {
    if (!saved || loading || saving || conflict || !dirty) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const result = await putRouting(token, { revision: saved.revision, rules });
      setSaved(result);
      setRules(result.rules);
      setNotice(
        `Routing rules saved. Revision ${result.revision}. New messages use this configuration.`,
      );
    } catch (failure) {
      report(failure);
      if (
        failure instanceof ApiError &&
        failure.status === 409 &&
        failure.message === "routing_changed"
      ) {
        setConflict(true);
        setError(
          "Routing rules changed in another session. Your draft is kept here. Reload the latest configuration before saving; reloading requires discarding this draft.",
        );
      } else {
        setError(
          `Couldn’t save routing rules. ${errorText(failure)} Your draft has been kept.`,
        );
      }
    } finally {
      setSaving(false);
    }
  };

  return {
    saved,
    rules,
    changeRules,
    dirty,
    loading,
    saving,
    error,
    notice,
    conflict,
    load,
    save,
  };
}

export type RoutingManager = ReturnType<typeof useRouting>;
