import { useCallback, useEffect, useMemo, useState } from "react";

import { readApiError, readJson } from "@/lib/api";
import { authedFetch } from "@/lib/authed";
import { useAuth } from "@/lib/auth";
import type { Channel } from "@/lib/types";

import { CreateChannelCard } from "./channels/CreateChannelCard";
import { ChannelListItem } from "./channels/ChannelListItem";

export default function ChannelsPage() {
  const auth = useAuth();
  const canCreate = Boolean(auth.user?.email_verified_at);

  const [items, setItems] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await authedFetch(auth, "/api/channels", { method: "GET" });
    if (!res.ok) {
      setError((await readApiError(res)).message);
      setLoading(false);
      return;
    }
    const data = await readJson<{ channels: Channel[] }>(res);
    setItems(data.channels);
    setLoading(false);
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  const sorted = useMemo(
    () => [...items].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [items],
  );

  return (
    <div className="space-y-6">
      <div>
        <div className="text-lg font-semibold tracking-tight">Channels</div>
        <div className="mt-1 text-sm text-muted-foreground">Bark, ntfy, MQTT, and Gotify.</div>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:border-destructive/30 dark:bg-destructive/10">
          {error}
        </div>
      )}

      <CreateChannelCard canCreate={canCreate} onCreated={() => void load()} />

      <div className="rounded-2xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3 text-sm font-semibold">Channels</div>
        {loading ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">Loading...</div>
        ) : sorted.length === 0 ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">No channels yet.</div>
        ) : (
          <div className="divide-y divide-border">
            {sorted.map((c) => (
              <ChannelListItem
                key={c.id}
                channel={c}
                canCreate={canCreate}
                onDeleted={(id) => {
                  void id;
                  void load();
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
