import { useCallback, useEffect, useMemo, useState } from "react";

import { readApiError, readJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { authedFetch } from "@/lib/authed";
import type { Channel, IngestEndpoint, Rule } from "@/lib/types";

import { RuleCreateCard } from "./rules/RuleCreateCard";
import { RulesListCard } from "./rules/RulesListCard";
import { RuleTesterCard } from "./rules/RuleTesterCard";
import { parseJsonObject, type RuleTestResult } from "./rules/utils";

export default function RulesPage() {
  const auth = useAuth();
  const canCreate = Boolean(auth.user?.email_verified_at);

  const [rules, setRules] = useState<Rule[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [endpoints, setEndpoints] = useState<IngestEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [channelId, setChannelId] = useState("");
  const [endpointIds, setEndpointIds] = useState<string[]>([]);
  const [containsLines, setContainsLines] = useState("");
  const [regex, setRegex] = useState("");
  const [priorityMin, setPriorityMin] = useState("");
  const [priorityMax, setPriorityMax] = useState("");
  const [tagsCsv, setTagsCsv] = useState("");
  const [groupExact, setGroupExact] = useState("");
  const [payloadJson, setPayloadJson] = useState('{\n  "title": "Ingest {{ingest_endpoint.name}}",\n  "body": "{{message.body}}"\n}');

  const [testEndpointId, setTestEndpointId] = useState("");
  const [testPayloadJson, setTestPayloadJson] = useState('{\n  "title": "Rule test",\n  "body": "Hello from rule test",\n  "group": "deploys",\n  "priority": 3,\n  "tags": ["test"],\n  "url": "https://example.com",\n  "extras": {\n    "source": "ui"\n  }\n}');
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<RuleTestResult | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [rRes, cRes, eRes] = await Promise.all([
      authedFetch(auth, "/api/rules", { method: "GET" }),
      authedFetch(auth, "/api/channels", { method: "GET" }),
      authedFetch(auth, "/api/ingest-endpoints", { method: "GET" }),
    ]);
    if (!rRes.ok) {
      setError((await readApiError(rRes)).message);
      setLoading(false);
      return;
    }
    if (!cRes.ok) {
      setError((await readApiError(cRes)).message);
      setLoading(false);
      return;
    }
    if (!eRes.ok) {
      setError((await readApiError(eRes)).message);
      setLoading(false);
      return;
    }
    const rData = await readJson<{ rules: Rule[] }>(rRes);
    const cData = await readJson<{ channels: Channel[] }>(cRes);
    const eData = await readJson<{ endpoints: IngestEndpoint[] }>(eRes);
    setRules(rData.rules);
    setChannels(cData.channels);
    setEndpoints(eData.endpoints);
    setLoading(false);
  }, [auth]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!channelId && channels.length) {
      setChannelId(channels[0].id);
    }
  }, [channels, channelId]);

  useEffect(() => {
    if (!testEndpointId && endpoints.length) {
      setTestEndpointId(endpoints[0].id);
    }
  }, [endpoints, testEndpointId]);

  const sortedRules = useMemo(
    () => [...rules].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [rules],
  );

  const channelNameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of channels) m.set(c.id, c.name);
    return m;
  }, [channels]);

  const channelTypeById = useMemo(() => {
    const m = new Map<string, Channel["type"]>();
    for (const c of channels) m.set(c.id, c.type);
    return m;
  }, [channels]);

  const selectedChannelType = channelTypeById.get(channelId) ?? null;
  const payloadLabel =
    selectedChannelType === "bark"
      ? "Bark payload template (JSON)"
      : selectedChannelType === "ntfy"
        ? "ntfy payload template (JSON)"
        : selectedChannelType === "mqtt"
           ? "MQTT payload template (JSON)"
           : "Payload template (JSON)";

  const regexValidation = useMemo(() => {
    const raw = regex.trim();
    if (!raw) return { ok: true as const, error: "" };
    try {
      new RegExp(raw, "i");
      return { ok: true as const, error: "" };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return { ok: false as const, error: msg || "Invalid regex" };
    }
  }, [regex]);

  const priorityValidation = useMemo(() => {
    const min = priorityMin.trim();
    const max = priorityMax.trim();
    const minNum = min ? Number(min) : null;
    const maxNum = max ? Number(max) : null;

    if (minNum !== null && (!Number.isInteger(minNum) || minNum < 1 || minNum > 5)) {
      return { ok: false as const, error: "Min priority must be 1-5." };
    }
    if (maxNum !== null && (!Number.isInteger(maxNum) || maxNum < 1 || maxNum > 5)) {
      return { ok: false as const, error: "Max priority must be 1-5." };
    }
    if (minNum !== null && maxNum !== null && minNum > maxNum) {
      return { ok: false as const, error: "Min priority cannot be greater than max priority." };
    }
    return { ok: true as const, error: "" };
  }, [priorityMax, priorityMin]);

  const testPayloadValidation = useMemo(() => {
    const parsed = parseJsonObject(testPayloadJson);
    if (!parsed.ok) {
      return { ok: false as const, error: parsed.error, payload: null as Record<string, unknown> | null };
    }
    const body = parsed.value.body;
    if (typeof body !== "string" || !body.trim()) {
      return {
        ok: false as const,
        error: "Sample payload must include non-empty string field 'body'.",
        payload: null as Record<string, unknown> | null,
      };
    }
    return { ok: true as const, error: "", payload: parsed.value };
  }, [testPayloadJson]);

  const createRule = useCallback(async () => {
    setError(null);

    if (!regexValidation.ok) {
      setError(`Payload regex is invalid: ${regexValidation.error}`);
      return;
    }

    if (!priorityValidation.ok) {
      setError(priorityValidation.error);
      return;
    }

    const parsedPayload = parseJsonObject(payloadJson);
    if (!parsedPayload.ok) {
      setError(`Payload template: ${parsedPayload.error}`);
      return;
    }
    const payload = parsedPayload.value;
    const contains = containsLines
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const filter: Record<string, unknown> = {};
    if (endpointIds.length) filter.ingest_endpoint_ids = endpointIds;
    if (contains.length || regex.trim()) {
      filter.body = {
        contains: contains.length ? contains : undefined,
        regex: regex.trim() || undefined,
      };
    }

    const minPriority = priorityMin.trim() ? Number(priorityMin) : null;
    const maxPriority = priorityMax.trim() ? Number(priorityMax) : null;
    if (minPriority !== null || maxPriority !== null) {
      filter.priority = {
        min: minPriority ?? undefined,
        max: maxPriority ?? undefined,
      };
    }

    const tags = tagsCsv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (tags.length) {
      filter.tags = tags;
    }

    if (groupExact.trim()) {
      filter.group = groupExact.trim();
    }

    const res = await authedFetch(auth, "/api/rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        enabled,
        channel_id: channelId,
        filter,
        payload_template: payload,
      }),
    });
    if (!res.ok) {
      const err = await readApiError(res);
      setError(err.message);
      return;
    }
    setName("");
    setEndpointIds([]);
    setContainsLines("");
    setRegex("");
    setPriorityMin("");
    setPriorityMax("");
    setTagsCsv("");
    setGroupExact("");
    void load();
  }, [
    auth,
    channelId,
    containsLines,
    enabled,
    endpointIds,
    groupExact,
    load,
    name,
    payloadJson,
    priorityMax,
    priorityMin,
    priorityValidation,
    regex,
    regexValidation,
    tagsCsv,
  ]);

  const runRuleTest = useCallback(async () => {
    setTestError(null);
    setTestResult(null);
    setTestLoading(true);
    try {
      if (!testPayloadValidation.ok || !testPayloadValidation.payload) {
        setTestError(testPayloadValidation.error);
        return;
      }
      const res = await authedFetch(auth, "/api/rules/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ingest_endpoint_id: testEndpointId,
          payload: testPayloadValidation.payload,
        }),
      });
      if (!res.ok) {
        setTestError((await readApiError(res)).message);
        return;
      }
      const data = await readJson<RuleTestResult>(res);
      setTestResult(data);
    } finally {
      setTestLoading(false);
    }
  }, [auth, testEndpointId, testPayloadValidation]);

  const deleteRule = useCallback(
    async (id: string) => {
      if (!confirm("Delete this rule?")) return;
      const res = await authedFetch(auth, `/api/rules/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        setError((await readApiError(res)).message);
        return;
      }
      void load();
    },
    [auth, load],
  );

  return (
    <div className="space-y-6">
      <div>
        <div className="text-lg font-semibold tracking-tight">Rules</div>
        <div className="mt-1 text-sm text-muted-foreground">Match ingested messages and forward to a channel.</div>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:border-destructive/30 dark:bg-destructive/10">
          {error}
        </div>
      )}

      <RuleCreateCard
        canCreate={canCreate}
        channels={channels}
        endpoints={endpoints}
        name={name}
        setName={setName}
        enabled={enabled}
        setEnabled={setEnabled}
        channelId={channelId}
        setChannelId={setChannelId}
        endpointIds={endpointIds}
        setEndpointIds={setEndpointIds}
        containsLines={containsLines}
        setContainsLines={setContainsLines}
        regex={regex}
        setRegex={setRegex}
        priorityMin={priorityMin}
        setPriorityMin={setPriorityMin}
        priorityMax={priorityMax}
        setPriorityMax={setPriorityMax}
        tagsCsv={tagsCsv}
        setTagsCsv={setTagsCsv}
        groupExact={groupExact}
        setGroupExact={setGroupExact}
        payloadJson={payloadJson}
        setPayloadJson={setPayloadJson}
        payloadLabel={payloadLabel}
        regexValidation={regexValidation}
        priorityValidation={priorityValidation}
        onCreate={() => void createRule()}
      />

      <RuleTesterCard
        canCreate={canCreate}
        endpoints={endpoints}
        testEndpointId={testEndpointId}
        setTestEndpointId={setTestEndpointId}
        testPayloadJson={testPayloadJson}
        setTestPayloadJson={setTestPayloadJson}
        testLoading={testLoading}
        testError={testError}
        testResult={testResult}
        testPayloadValidation={testPayloadValidation}
        onRun={() => void runRuleTest()}
        onClear={() => {
          setTestError(null);
          setTestResult(null);
        }}
      />

      <RulesListCard
        loading={loading}
        rules={sortedRules}
        canCreate={canCreate}
        channelNameById={channelNameById}
        onDelete={(id) => void deleteRule(id)}
      />
    </div>
  );
}
