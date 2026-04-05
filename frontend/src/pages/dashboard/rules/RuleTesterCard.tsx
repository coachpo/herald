import type { IngestEndpoint } from "@/lib/types";

import type { RuleTestResult } from "./utils";

export interface RuleTesterCardProps {
  canCreate: boolean;
  endpoints: IngestEndpoint[];
  testEndpointId: string;
  setTestEndpointId: (value: string) => void;
  testPayloadJson: string;
  setTestPayloadJson: (value: string) => void;
  testLoading: boolean;
  testError: string | null;
  testResult: RuleTestResult | null;
  testPayloadValidation: { ok: boolean; error: string };
  onRun: () => void;
  onClear: () => void;
}

export function RuleTesterCard({
  canCreate,
  endpoints,
  testEndpointId,
  setTestEndpointId,
  testPayloadJson,
  setTestPayloadJson,
  testLoading,
  testError,
  testResult,
  testPayloadValidation,
  onRun,
  onClear,
}: RuleTesterCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="text-sm font-semibold">Rule tester</div>
      <div className="mt-1 text-sm text-muted-foreground">
        Provide a sample message; Herald will show which rules would trigger.
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3">
        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Ingest endpoint</div>
          <select
            id="rule-test-endpoint"
            name="ingest_endpoint_id"
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={testEndpointId}
            onChange={(e) => setTestEndpointId(e.target.value)}
            disabled={!canCreate || testLoading || endpoints.length === 0}
          >
            {endpoints.map((ep) => (
              <option key={ep.id} value={ep.id}>
                {ep.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="mt-3 block">
        <div className="text-xs font-medium text-muted-foreground">Sample payload JSON</div>
        <textarea
          id="rule-test-payload"
          name="payload_json"
          className={
            "mt-1 h-40 w-full resize-y rounded-xl border bg-card px-3 py-2 text-sm font-mono " +
            (testPayloadValidation.ok ? "border-border" : "border-destructive/40")
          }
          value={testPayloadJson}
          onChange={(e) => setTestPayloadJson(e.target.value)}
          disabled={!canCreate || testLoading}
        />
        {!testPayloadValidation.ok && (
          <div className="mt-1 text-xs text-destructive">{testPayloadValidation.error}</div>
        )}
      </label>

      <div className="mt-3 flex items-center gap-2">
        <button
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          disabled={!canCreate || !testEndpointId || testLoading || !testPayloadValidation.ok}
          onClick={onRun}
        >
          {testLoading ? "Testing..." : "Find triggered rules"}
        </button>
        <button
          className="rounded-xl border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted"
          type="button"
          onClick={onClear}
        >
          Clear
        </button>
      </div>

      {testError && (
        <div className="mt-3 rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:border-destructive/30 dark:bg-destructive/10">
          {testError}
        </div>
      )}

      {testResult && (
        <div className="mt-3 space-y-3">
          <div className="text-xs text-muted-foreground">
            Matched {testResult.matched_count} of {testResult.total_rules} enabled rule(s)
          </div>
          {testResult.matches.length === 0 ? (
            <div className="rounded-xl border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
              No rules would trigger for this sample.
            </div>
          ) : (
            <div className="space-y-2">
              {testResult.matches.map((match) => (
                <div key={match.rule.id} className="rounded-xl border border-border bg-card p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-foreground">{match.rule.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {match.channel.name} ({match.channel_type})
                    </div>
                  </div>
                  <pre className="mt-2 overflow-auto rounded-xl border border-border bg-muted p-3 text-xs">
                    {JSON.stringify(match.rendered_payload, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!canCreate && (
        <div className="mt-2 text-xs text-warning">Verify your email to run tests.</div>
      )}
    </div>
  );
}
