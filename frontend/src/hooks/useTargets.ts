import { useState } from "react";
import { api, errorText } from "../lib/api";
import type { Config, Target, TargetInput } from "../lib/types";

interface UseTargetsOptions {
  readonly token: string;
  readonly reload: () => Promise<void>;
  readonly report: (error: unknown) => void;
}

function targetPayload(input: TargetInput): TargetInput {
  const config: Config = { ...input.config };
  for (const key of ["device_key", "access_token", "app_token", "password"]) {
    if (config[key] === "") delete config[key];
  }
  if (input.kind === "mqtt") {
    config.broker_port = Number(config.broker_port ?? 1883);
    config.qos = Number(config.qos ?? 1);
  }
  return { ...input, config };
}

export function useTargets({ token, reload, report }: UseTargetsOptions) {
  const [editor, setEditor] = useState<{ target: Target | null } | null>(null);
  const [deleting, setDeleting] = useState<Target | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [listError, setListError] = useState("");
  const [formError, setFormError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [needsRefresh, setNeedsRefresh] = useState(false);

  const refreshAfterMutation = async () => {
    setNeedsRefresh(true);
    try {
      await reload();
      setNeedsRefresh(false);
      setListError("");
    } catch (error) {
      report(error);
      setListError(
        "Your change was saved, but the target list could not be refreshed. Refresh the list before making another change.",
      );
    }
  };

  const refresh = async () => {
    if (busy) return;
    setBusy("refresh");
    setListError("");
    try {
      await reload();
      setNeedsRefresh(false);
    } catch (error) {
      report(error);
      setListError(errorText(error));
    } finally {
      setBusy(null);
    }
  };

  const create = () => {
    if (busy || needsRefresh) return;
    setFormError("");
    setNotice("");
    setEditor({ target: null });
  };
  const edit = (target: Target) => {
    if (busy || needsRefresh) return;
    setFormError("");
    setNotice("");
    setEditor({ target });
  };
  const closeEditor = () => {
    if (busy === "save") return;
    setEditor(null);
    setFormError("");
  };

  const save = async (input: TargetInput) => {
    if (busy || !editor || needsRefresh) return;
    setBusy("save");
    setFormError("");
    try {
      await api<Target>(
        token,
        editor.target ? `/targets/${editor.target.id}` : "/targets",
        {
          method: editor.target ? "PUT" : "POST",
          body: JSON.stringify(targetPayload(input)),
        },
      );
    } catch (error) {
      report(error);
      setFormError(errorText(error));
      setBusy(null);
      return;
    }
    // A saved mutation must not remain a resubmittable create form if refresh fails.
    setNotice(editor.target ? "Target updated." : "Target created.");
    setEditor(null);
    await refreshAfterMutation();
    setBusy(null);
  };

  const toggle = async (target: Target) => {
    if (busy || needsRefresh) return;
    setBusy(`toggle:${target.id}`);
    setListError("");
    setNotice("");
    try {
      await api<Target>(token, `/targets/${target.id}`, {
        method: "PUT",
        body: JSON.stringify(
          targetPayload({
            name: target.name,
            kind: target.kind,
            config: target.config,
            is_default: target.is_default,
            enabled: !target.enabled,
          }),
        ),
      });
    } catch (error) {
      report(error);
      setListError(errorText(error));
      setBusy(null);
      return;
    }
    setNotice(
      target.enabled
        ? "Target disabled for new messages. Already queued deliveries are unchanged."
        : "Target enabled for new messages.",
    );
    await refreshAfterMutation();
    setBusy(null);
  };

  const confirmDelete = (target: Target) => {
    if (busy || needsRefresh) return;
    setDeleteError("");
    setDeleting(target);
    setNotice("");
  };
  const closeDelete = () => {
    if (busy === "delete") return;
    setDeleting(null);
    setDeleteError("");
  };

  const remove = async () => {
    if (busy || !deleting || needsRefresh) return;
    setBusy("delete");
    setDeleteError("");
    try {
      await api<void>(token, `/targets/${deleting.id}`, { method: "DELETE" });
    } catch (error) {
      report(error);
      setDeleteError(errorText(error));
      setBusy(null);
      return;
    }
    setDeleting(null);
    setNotice("Target deleted. Successful delivery history is kept.");
    await refreshAfterMutation();
    setBusy(null);
  };

  return {
    editor,
    deleting,
    busy,
    notice,
    listError,
    formError,
    deleteError,
    needsRefresh,
    create,
    edit,
    closeEditor,
    save,
    toggle,
    confirmDelete,
    closeDelete,
    remove,
    refresh,
  };
}
