import { useState } from "react";

import { readApiError, readJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { authedFetch } from "@/lib/authed";
import type { Channel } from "@/lib/types";
import { ChannelTestPanel, type ChannelTestResp } from "./ChannelTestPanel";

export interface ChannelListItemProps {
  channel: Channel;
  canCreate: boolean;
  onDeleted: (id: string) => void;
}

export function ChannelListItem({
  channel,
  canCreate,
  onDeleted,
}: ChannelListItemProps) {
  const auth = useAuth();
  const [testOpen, setTestOpen] = useState(false);
  const [testTitle, setTestTitle] = useState("Herald test");
  const [testBody, setTestBody] = useState("Test notification from Herald");
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ChannelTestResp | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  return (
    <div className="px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground">{channel.name}</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {channel.type} · Created: {new Date(channel.created_at).toLocaleString()}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            className="whitespace-nowrap rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
            disabled={!canCreate || deleting}
            data-testid={`channel-send-test-toggle-${channel.id}`}
            onClick={() => {
              setActionError(null);
              setTestError(null);
              setTestResult(null);
              setTestOpen((prev) => !prev);
            }}
          >
            Send test
          </button>
          <button
            type="button"
            className="whitespace-nowrap rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
            disabled={!canCreate || deleting || testLoading}
            onClick={async () => {
              if (!confirm("Delete this channel?")) return;
              setActionError(null);
              setDeleting(true);
              try {
                const res = await authedFetch(auth, `/api/channels/${channel.id}`, {
                  method: "DELETE",
                });
                if (!res.ok) {
                  setActionError((await readApiError(res)).message);
                  return;
                }
                onDeleted(channel.id);
              } finally {
                setDeleting(false);
              }
            }}
          >
            Delete
          </button>
        </div>
      </div>

      {actionError && (
        <div className="mt-3 rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:border-destructive/30 dark:bg-destructive/10">
          {actionError}
        </div>
      )}

      {testOpen && (
        <ChannelTestPanel
          channelId={channel.id}
          testTitle={testTitle}
          setTestTitle={setTestTitle}
          testBody={testBody}
          setTestBody={setTestBody}
          testLoading={testLoading}
          testError={testError}
          testResult={testResult}
          onSend={async (id) => {
            setActionError(null);
            setTestError(null);
            setTestLoading(true);
            try {
              const res = await authedFetch(auth, `/api/channels/${id}/test`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: testTitle.trim() || null, body: testBody.trim() || null }),
              });
              if (!res.ok) {
                setTestError((await readApiError(res)).message);
                setTestResult(null);
                return;
              }
              try {
                const data = await readJson<ChannelTestResp>(res);
                setTestResult(data);
              } catch {
                setTestError("Invalid response from server.");
                setTestResult(null);
              }
            } finally {
              setTestLoading(false);
            }
          }}
          onClose={() => setTestOpen(false)}
        />
      )}
    </div>
  );
}
