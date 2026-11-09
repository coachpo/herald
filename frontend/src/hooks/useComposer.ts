import { useState, type FormEvent } from "react";
import { api, errorText } from "../lib/api";
import type { Target } from "../lib/types";

export function useComposer(
  token: string,
  targets: Target[],
  onStored: (id: string) => void,
  report: (error: unknown) => void,
) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState(3);
  const [explicit, setExplicit] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<{
    id: string;
    duplicate: boolean;
  } | null>(null);
  const enabled = targets.filter((target) => target.enabled);
  const destinations = enabled.filter((target) => selected.includes(target.id));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !body.trim() || (explicit && !destinations.length)) return;
    setBusy(true);
    setError("");
    setReceipt(null);
    try {
      const result = await api<{ message_id: string; duplicate: boolean }>(
        token,
        "/messages",
        {
          method: "POST",
          body: JSON.stringify({
            title,
            body,
            priority,
            ...(explicit
              ? { target_ids: destinations.map((target) => target.id) }
              : {}),
          }),
        },
      );
      setReceipt({ id: result.message_id, duplicate: result.duplicate });
      setBody("");
      setTitle("");
      onStored(result.message_id);
    } catch (failure) {
      setError(errorText(failure));
      report(failure);
    } finally {
      setBusy(false);
    }
  };
  return {
    title,
    setTitle,
    body,
    setBody,
    priority,
    setPriority,
    explicit,
    setExplicit,
    selected,
    setSelected,
    busy,
    error,
    receipt,
    enabled,
    destinations,
    submit,
  };
}
