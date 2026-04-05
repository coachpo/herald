import type { Channel, IngestEndpoint } from "@/lib/types";

export interface RuleCreateCardProps {
  canCreate: boolean;
  channels: Channel[];
  endpoints: IngestEndpoint[];
  name: string;
  setName: (value: string) => void;
  enabled: boolean;
  setEnabled: (value: boolean) => void;
  channelId: string;
  setChannelId: (value: string) => void;
  endpointIds: string[];
  setEndpointIds: (value: string[] | ((prev: string[]) => string[])) => void;
  containsLines: string;
  setContainsLines: (value: string) => void;
  regex: string;
  setRegex: (value: string) => void;
  priorityMin: string;
  setPriorityMin: (value: string) => void;
  priorityMax: string;
  setPriorityMax: (value: string) => void;
  tagsCsv: string;
  setTagsCsv: (value: string) => void;
  groupExact: string;
  setGroupExact: (value: string) => void;
  payloadJson: string;
  setPayloadJson: (value: string) => void;
  payloadLabel: string;
  regexValidation: { ok: boolean; error: string };
  priorityValidation: { ok: boolean; error: string };
  onCreate: () => void;
}

export function RuleCreateCard({
  canCreate,
  channels,
  endpoints,
  name,
  setName,
  enabled,
  setEnabled,
  channelId,
  setChannelId,
  endpointIds,
  setEndpointIds,
  containsLines,
  setContainsLines,
  regex,
  setRegex,
  priorityMin,
  setPriorityMin,
  priorityMax,
  setPriorityMax,
  tagsCsv,
  setTagsCsv,
  groupExact,
  setGroupExact,
  payloadJson,
  setPayloadJson,
  payloadLabel,
  regexValidation,
  priorityValidation,
  onCreate,
}: RuleCreateCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="text-sm font-semibold">Create rule</div>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Name</div>
          <input
            id="rule-name"
            name="name"
            autoComplete="off"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!canCreate}
          />
        </label>
        <label className="flex items-end gap-2">
          <input
            id="rule-enabled"
            name="enabled"
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            disabled={!canCreate}
          />
          <span className="text-sm text-muted-foreground">Enabled</span>
        </label>

        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Channel</div>
          <select
            id="rule-channel"
            name="channel_id"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
            disabled={!canCreate}
          >
            {channels.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.type})
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Ingest endpoints (optional)</div>
          <div className="mt-1 flex flex-wrap gap-2">
            {endpoints.map((ep) => {
              const on = endpointIds.includes(ep.id);
              return (
                <button
                  key={ep.id}
                  type="button"
                  disabled={!canCreate}
                  className={
                    "rounded-full border px-3 py-1 text-xs font-medium " +
                    (on
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card text-muted-foreground hover:bg-muted")
                  }
                  onClick={() => {
                    setEndpointIds((prev) =>
                      prev.includes(ep.id)
                        ? prev.filter((x) => x !== ep.id)
                        : [...prev, ep.id],
                    );
                  }}
                >
                  {ep.name}
                </button>
              );
            })}
          </div>
        </label>

        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Payload contains (one per line)</div>
          <textarea
            id="rule-body-contains"
            name="body_contains"
            className="mt-1 h-24 w-full resize-y rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={containsLines}
            onChange={(e) => setContainsLines(e.target.value)}
            disabled={!canCreate}
          />
        </label>
        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Payload regex (optional)</div>
          <input
            id="rule-body-regex"
            name="body_regex"
            autoComplete="off"
            className={
              "mt-1 w-full rounded-xl border bg-card px-3 py-2 text-sm font-mono " +
              (regexValidation.ok ? "border-border" : "border-destructive/40")
            }
            value={regex}
            onChange={(e) => setRegex(e.target.value)}
            disabled={!canCreate}
          />
          {!regexValidation.ok && (
            <div className="mt-1 text-xs text-destructive">Invalid regex: {regexValidation.error}</div>
          )}
        </label>

        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Priority min (optional)</div>
          <select
            id="rule-priority-min"
            name="priority_min"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={priorityMin}
            onChange={(e) => setPriorityMin(e.target.value)}
            disabled={!canCreate}
          >
            <option value="">Any</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5</option>
          </select>
        </label>

        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Priority max (optional)</div>
          <select
            id="rule-priority-max"
            name="priority_max"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={priorityMax}
            onChange={(e) => setPriorityMax(e.target.value)}
            disabled={!canCreate}
          >
            <option value="">Any</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="4">4</option>
            <option value="5">5</option>
          </select>
        </label>

        <label className="block md:col-span-2">
          <div className="text-xs font-medium text-muted-foreground">Tags (comma-separated, optional)</div>
          <input
            id="rule-tags"
            name="tags"
            autoComplete="off"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={tagsCsv}
            onChange={(e) => setTagsCsv(e.target.value)}
            placeholder="deploy,production"
            disabled={!canCreate}
          />
        </label>

        <label className="block md:col-span-2">
          <div className="text-xs font-medium text-muted-foreground">Group exact match (optional)</div>
          <input
            id="rule-group"
            name="group"
            autoComplete="off"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={groupExact}
            onChange={(e) => setGroupExact(e.target.value)}
            placeholder="deploys"
            disabled={!canCreate}
          />
        </label>
      </div>

      {!priorityValidation.ok && (
        <div className="mt-2 text-xs text-destructive">{priorityValidation.error}</div>
      )}

      <div className="mt-4">
        <div className="text-xs font-medium text-muted-foreground">{payloadLabel}</div>
        <textarea
          id="rule-payload-template"
          name="payload_template"
          className="mt-1 h-48 w-full resize-y rounded-xl border border-border bg-card px-3 py-2 font-mono text-xs"
          value={payloadJson}
          onChange={(e) => setPayloadJson(e.target.value)}
          disabled={!canCreate}
        />
        <div className="mt-2 text-xs text-muted-foreground">
          Available vars: {"{{message.title}}"}, {"{{message.body}}"}, {"{{message.group}}"},
          {" {{message.priority}}"}, {"{{message.tags}}"}, {"{{message.url}}"},
          {" {{message.id}}"}, {"{{message.received_at}}"}, {"{{message.extras.<key>}}"},
          {" {{request.content_type}}"}, {"{{request.remote_ip}}"}, {"{{request.user_agent}}"},
          {" {{request.headers.<name>}}"}, {"{{request.query.<name>}}"},
          {" {{ingest_endpoint.id}}"}, {"{{ingest_endpoint.name}}"}.
        </div>
      </div>

      <div className="mt-3">
        <button
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          disabled={!canCreate || !name.trim() || !channelId || !regexValidation.ok || !priorityValidation.ok}
          onClick={onCreate}
        >
          Create
        </button>
        {!canCreate && (
          <div className="mt-2 text-xs text-warning">Verify your email to create rules.</div>
        )}
      </div>
    </div>
  );
}
