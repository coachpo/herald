import { useState } from "react";
import type { RoutingManager } from "../hooks/useRouting";
import type { RoutingCondition, RoutingRule, Target } from "../lib/types";
import { Feedback } from "./Feedback";
import { Modal } from "./Modal";

interface ConditionEditorProps {
  readonly condition: RoutingCondition;
  readonly canRemove: boolean;
  readonly onChange: (condition: RoutingCondition) => void;
  readonly onRemove: () => void;
}

function ConditionEditor({
  condition,
  canRemove,
  onChange,
  onRemove,
}: ConditionEditorProps) {
  return (
    <div className="routing-condition">
      <label className="field">
        Field
        <select
          value={condition.field}
          onChange={(event) => {
            const field = event.target.value;
            if (field === "priority") onChange({ field, op: "eq", value: 3 });
            else if (field === "title" || field === "body")
              onChange({ field, op: "eq", value: "" });
          }}
        >
          <option value="priority">Priority</option>
          <option value="title">Title</option>
          <option value="body">Body</option>
        </select>
      </label>
      <label className="field">
        Operator
        <select
          value={condition.op}
          onChange={(event) => {
            const op = event.target.value;
            if (
              condition.field === "priority" &&
              (op === "eq" || op === "gte" || op === "lte")
            ) onChange({ ...condition, op });
            else if (
              condition.field !== "priority" &&
              (op === "eq" || op === "prefix" || op === "contains")
            ) onChange({ ...condition, op });
          }}
        >
          <option value="eq">Equals</option>
          {condition.field === "priority" ? (
            <>
              <option value="gte">At least</option>
              <option value="lte">At most</option>
            </>
          ) : (
            <>
              <option value="prefix">Starts with</option>
              <option value="contains">Contains</option>
            </>
          )}
        </select>
      </label>
      <label className="field">
        Value
        {condition.field === "priority" ? (
          <input
            type="number"
            min={1}
            max={5}
            step={1}
            required
            value={Number.isNaN(condition.value) ? "" : condition.value}
            onChange={(event) => onChange({
              ...condition,
              value: event.target.value === ""
                ? Number.NaN
                : Number(event.target.value),
            })}
          />
        ) : (
          <input
            value={condition.value}
            onChange={(event) => onChange({
              ...condition,
              value: event.target.value,
            })}
          />
        )}
      </label>
      <button
        type="button"
        className="ghost danger"
        disabled={!canRemove}
        onClick={onRemove}
      >
        Remove condition
      </button>
    </div>
  );
}

interface RoutingRulesProps {
  readonly manager: RoutingManager;
  readonly targets: readonly Target[];
  readonly targetsLoading: boolean;
}

export function RoutingRules({
  manager,
  targets,
  targetsLoading,
}: RoutingRulesProps) {
  const [confirmReload, setConfirmReload] = useState(false);
  const busy = manager.loading || manager.saving;
  const updateRule = (index: number, change: Partial<RoutingRule>) => {
    manager.changeRules(manager.rules.map((rule, position) =>
      position === index ? { ...rule, ...change } : rule,
    ));
  };
  const reload = () => {
    if (manager.dirty) setConfirmReload(true);
    else void manager.load();
  };
  const addRule = () => manager.changeRules([
    ...manager.rules,
    {
      id: `rule-${crypto.randomUUID()}`,
      enabled: true,
      all: [{ field: "priority", op: "gte", value: 4 }],
      target_ids: [],
    },
  ]);

  return (
    <section
      className="routing-rules stack"
      aria-labelledby="routing-rules-heading"
      aria-busy={busy}
    >
      <div className="section-heading">
        <h2 id="routing-rules-heading">Automatic routing</h2>
        <button
          type="button"
          className="secondary"
          disabled={busy}
          onClick={reload}
        >
          {manager.loading ? "Loading rules…" : "Reload rules"}
        </button>
      </div>
      <p className="muted">
        Each enabled rule matches when all its conditions match. All matching
        rules contribute targets; only zero matches falls back to enabled
        default targets. Explicit target selection bypasses these rules.
      </p>
      <p className="small muted">
        Text matching is case-sensitive and preserves spaces. Rule order records
        matches and does not set delivery priority. Changes affect new receipts
        only; queued deliveries and earlier routing decisions stay unchanged.
      </p>
      {manager.error && <Feedback tone="error">{manager.error}</Feedback>}
      {manager.notice && <Feedback tone="success">{manager.notice}</Feedback>}
      {manager.saved && (
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void manager.save();
          }}
        >
          <p className="small muted" role="status">
            Loaded revision {manager.saved.revision}
            {manager.dirty ? " · Unsaved changes" : " · No unsaved changes"}
          </p>
          <fieldset className="form-fields" disabled={busy}>
            {manager.rules.length === 0 && (
              <p className="panel muted">
                No routing rules. Automatic selection falls back to enabled
                default targets.
              </p>
            )}
            {manager.rules.map((rule, ruleIndex) => (
              <section
                className="panel routing-rule stack"
                key={rule.id}
                aria-label={`Rule ${ruleIndex + 1}`}
              >
                <div className="section-heading">
                  <div>
                    <h3>Rule {ruleIndex + 1}</h3>
                    <code className="identifier">{rule.id}</code>
                  </div>
                  <button
                    type="button"
                    className="ghost danger"
                    aria-label={`Remove rule ${ruleIndex + 1}`}
                    onClick={() => manager.changeRules(
                      manager.rules.filter((_, index) => index !== ruleIndex),
                    )}
                  >
                    Remove rule
                  </button>
                </div>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={rule.enabled}
                    onChange={(event) => updateRule(ruleIndex, {
                      enabled: event.target.checked,
                    })}
                  />
                  Rule enabled
                </label>
                <fieldset className="form-section">
                  <legend>Match all conditions</legend>
                  {rule.all.map((condition, conditionIndex) => (
                    <ConditionEditor
                      key={conditionIndex}
                      condition={condition}
                      canRemove={rule.all.length > 1}
                      onChange={(next) => updateRule(ruleIndex, {
                        all: rule.all.map((item, index) =>
                          index === conditionIndex ? next : item,
                        ),
                      })}
                      onRemove={() => updateRule(ruleIndex, {
                        all: rule.all.filter((_, index) =>
                          index !== conditionIndex,
                        ),
                      })}
                    />
                  ))}
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => updateRule(ruleIndex, {
                      all: [...rule.all, { field: "priority", op: "eq", value: 3 }],
                    })}
                  >
                    Add condition
                  </button>
                </fieldset>
                <fieldset className="form-section" disabled={targetsLoading}>
                  <legend>Delivery targets · select at least one</legend>
                  {targets.length === 0 && (
                    <p className="muted">
                      Add a delivery target above before saving a rule.
                    </p>
                  )}
                  {targets.map((target) => (
                    <label className="checkbox-row" key={target.id}>
                      <input
                        type="checkbox"
                        checked={rule.target_ids.includes(target.id)}
                        onChange={(event) => updateRule(ruleIndex, {
                          target_ids: event.target.checked
                            ? [...rule.target_ids, target.id]
                            : rule.target_ids.filter((id) => id !== target.id),
                        })}
                      />
                      {target.name}{!target.enabled ? " · Disabled" : ""}
                    </label>
                  ))}
                  {rule.target_ids
                    .filter((id) => !targets.some((target) => target.id === id))
                    .map((id) => (
                      <label className="checkbox-row" key={id}>
                        <input
                          type="checkbox"
                          checked
                          onChange={() => updateRule(ruleIndex, {
                            target_ids: rule.target_ids.filter((selected) =>
                              selected !== id,
                            ),
                          })}
                        />
                        Unavailable target: {id}
                      </label>
                    ))}
                  {rule.target_ids.length === 0 && (
                    <p className="field-help">
                      Choose at least one target to save this rule.
                    </p>
                  )}
                  <p className="field-help">
                    A matched rule selecting any disabled target rejects the
                    message. Even disabled rules must release their references
                    before a target can be deleted.
                  </p>
                </fieldset>
              </section>
            ))}
            <button type="button" className="secondary" onClick={addRule}>
              Add rule
            </button>
          </fieldset>
          <div className="form-actions">
            <button
              type="submit"
              disabled={
                busy || manager.conflict || !manager.dirty || targetsLoading ||
                manager.rules.some((rule) => rule.target_ids.length === 0)
              }
            >
              {manager.saving ? "Saving rules…" : "Save all rules"}
            </button>
            <span className="small muted">
              Saving replaces the complete rule list. Removing every rule clears
              routing rules.
            </span>
          </div>
        </form>
      )}
      {confirmReload && (
        <Modal
          title="Discard draft and reload rules?"
          onClose={() => setConfirmReload(false)}
        >
          <p>
            Your unsaved rule edits will be replaced only after the latest
            configuration loads successfully.
          </p>
          <div className="form-actions">
            <button
              type="button"
              className="secondary"
              onClick={() => setConfirmReload(false)}
            >
              Keep editing
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirmReload(false);
                void manager.load();
              }}
            >
              Discard draft and reload
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
