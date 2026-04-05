import type { Channel, Rule } from "@/lib/types";
export { parseRequiredJsonObject as parseJsonObject } from "@/lib/json";

export interface RuleTestMatch {
  rule: Rule;
  channel: Channel;
  channel_type: string;
  rendered_payload: unknown;
}

export interface RuleTestResult {
  matched_count: number;
  total_rules: number;
  matches: RuleTestMatch[];
}
