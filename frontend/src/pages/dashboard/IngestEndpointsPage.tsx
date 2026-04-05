import { useCallback, useEffect, useMemo, useState } from "react";

import { readApiError, readJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { authedFetch } from "@/lib/authed";
import { buildIngestUrl } from "@/lib/public-api";
import type { IngestEndpoint } from "@/lib/types";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CreateEndpointCard } from "./ingest-endpoints/CreateEndpointCard";
import { CreatedEndpointCard } from "./ingest-endpoints/CreatedEndpointCard";
import { EndpointListCard } from "./ingest-endpoints/EndpointListCard";
import { copyToClipboard, type CreateResp } from "./ingest-endpoints/utils";

export default function IngestEndpointsPage() {
  const auth = useAuth();
  const [items, setItems] = useState<IngestEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreateResp | null>(null);
  const [createdCopiedField, setCreatedCopiedField] = useState<"key" | "url" | "curl" | null>(null);
  const [copiedEndpointId, setCopiedEndpointId] = useState<string | null>(null);

  const canCreate = Boolean(auth.user?.email_verified_at);

  const sorted = useMemo(
    () => [...items].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [items],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await authedFetch(auth, "/api/ingest-endpoints", {
      method: "GET",
    });
    if (!res.ok) {
      const err = await readApiError(res);
      setError(err.message);
      setLoading(false);
      return;
    }
    const data = await readJson<{ endpoints: IngestEndpoint[] }>(res);
    setItems(data.endpoints);
    setLoading(false);
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-lg font-semibold tracking-tight">Ingest endpoints</div>
          <div className="mt-1 text-sm text-muted-foreground">
            URL identifies the endpoint; the ingest key is sent in a header.
          </div>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {created && (
        <CreatedEndpointCard
          created={created}
          copiedField={createdCopiedField}
          onCopy={async (field, text) => {
            const ok = await copyToClipboard(text);
            if (!ok) {
              setError("Copy failed.");
              return;
            }
            setCreatedCopiedField(field);
            window.setTimeout(() => {
              setCreatedCopiedField((prev) => (prev === field ? null : prev));
            }, 1200);
          }}
          onDismiss={() => {
            setCreated(null);
            setCreatedCopiedField(null);
          }}
        />
      )}

      <CreateEndpointCard
        canCreate={canCreate}
        name={name}
        setName={setName}
        onCreate={async () => {
          setError(null);
          const res = await authedFetch(auth, "/api/ingest-endpoints", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
          });
          if (!res.ok) {
            const err = await readApiError(res);
            setError(err.message);
            return;
          }
          const data = await readJson<CreateResp>(res);
          setCreatedCopiedField(null);
          setCreated({
            ...data,
            ingest_url: buildIngestUrl(data.endpoint.id),
          });
          setName("");
          void load();
        }}
      />

      <EndpointListCard
        loading={loading}
        endpoints={sorted}
        canCreate={canCreate}
        copiedEndpointId={copiedEndpointId}
        onCopyUrl={async (endpointId, url) => {
          const ok = await copyToClipboard(url);
          if (!ok) {
            setError("Copy failed.");
            return;
          }
          setCopiedEndpointId(endpointId);
          window.setTimeout(() => {
            setCopiedEndpointId((prev) => (prev === endpointId ? null : prev));
          }, 1200);
        }}
        onRevoke={async (endpointId) => {
          if (!confirm("Revoke this ingest endpoint?")) return;
          setError(null);
          const res = await authedFetch(auth, `/api/ingest-endpoints/${endpointId}/revoke`, {
            method: "POST",
          });
          if (!res.ok) {
            const err = await readApiError(res);
            setError(err.message);
            return;
          }
          void load();
        }}
        onArchive={async (endpointId) => {
          if (!confirm("Archive this ingest endpoint? It will be hidden and will stop ingest.")) {
            return;
          }
          setError(null);
          const res = await authedFetch(auth, `/api/ingest-endpoints/${endpointId}`, {
            method: "DELETE",
          });
          if (!res.ok) {
            const err = await readApiError(res);
            setError(err.message);
            return;
          }
          void load();
        }}
        buildUrl={buildIngestUrl}
      />
    </div>
  );
}
