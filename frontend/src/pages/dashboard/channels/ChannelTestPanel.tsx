import type { Channel } from "@/lib/types";

export interface ChannelTestResp {
  ok: boolean;
  channel_id: string;
  channel_type: Channel["type"];
  provider_response: unknown;
}

export interface ChannelTestPanelProps {
  channelId: string;
  testTitle: string;
  setTestTitle: (val: string) => void;
  testBody: string;
  setTestBody: (val: string) => void;
  testLoading: boolean;
  testError: string | null;
  testResult: ChannelTestResp | null;
  onSend: (id: string) => void;
  onClose: () => void;
}

export function ChannelTestPanel({
  channelId,
  testTitle,
  setTestTitle,
  testBody,
  setTestBody,
  testLoading,
  testError,
  testResult,
  onSend,
  onClose,
}: ChannelTestPanelProps) {
  return (
    <div
      className="mt-3 rounded-xl border border-border bg-muted/40 p-3"
      data-testid={`channel-send-test-panel-${channelId}`}
    >
      <div className="text-xs font-semibold text-foreground">Send test notification</div>
      <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
        <label className="block">
          <div className="text-xs font-medium text-muted-foreground">Title (optional)</div>
          <input
            className="mt-1 w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={testTitle}
            onChange={(e) => setTestTitle(e.target.value)}
            disabled={testLoading}
          />
        </label>
        <label className="block md:col-span-2">
          <div className="text-xs font-medium text-muted-foreground">Body</div>
          <textarea
            className="mt-1 h-20 w-full resize-y rounded-xl border border-border bg-card px-3 py-2 text-sm"
            value={testBody}
            onChange={(e) => setTestBody(e.target.value)}
            disabled={testLoading}
          />
        </label>
      </div>

      {testError && (
        <div className="mt-2 rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:border-destructive/30 dark:bg-destructive/10">
          {testError}
        </div>
      )}

      {testResult && (
        <div className="mt-2 rounded-xl border border-border bg-card px-3 py-2">
          <div className="text-xs font-semibold text-foreground">
            Result:{" "}
            <span className={testResult.ok ? "text-success" : "text-destructive"}>
              {testResult.ok ? "sent" : "failed"}
            </span>
          </div>
          <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-muted px-3 py-2 text-xs text-foreground">
            {JSON.stringify(testResult.provider_response, null, 2)}
          </pre>
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          disabled={testLoading}
          onClick={() => onSend(channelId)}
          data-testid={`channel-send-test-send-${channelId}`}
        >
          {testLoading ? "Sending..." : "Send"}
        </button>
        <button
          type="button"
          className="rounded-xl border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
          disabled={testLoading}
          onClick={onClose}
          data-testid={`channel-send-test-close-${channelId}`}
        >
          Close
        </button>
      </div>
    </div>
  );
}
