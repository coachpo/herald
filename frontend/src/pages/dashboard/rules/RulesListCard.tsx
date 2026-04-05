import type { Rule } from "@/lib/types";

export interface RulesListCardProps {
  loading: boolean;
  rules: Rule[];
  canCreate: boolean;
  channelNameById: Map<string, string>;
  onDelete: (id: string) => void;
}

export function RulesListCard({
  loading,
  rules,
  canCreate,
  channelNameById,
  onDelete,
}: RulesListCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card">
      <div className="border-b border-border px-4 py-3 text-sm font-semibold">Rules</div>
      {loading ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">Loading...</div>
      ) : rules.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">No rules yet.</div>
      ) : (
        <div className="divide-y divide-border">
          {rules.map((rule) => (
            <div key={rule.id} className="px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-foreground">{rule.name}</div>
                <div className="flex items-center gap-3">
                  <div className={"text-xs font-medium " + (rule.enabled ? "text-success" : "text-muted-foreground")}>
                    {rule.enabled ? "enabled" : "disabled"}
                  </div>
                  <button
                    className="rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
                    disabled={!canCreate}
                    onClick={() => onDelete(rule.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                Channel: {channelNameById.get(rule.channel_id) ?? rule.channel_id}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
