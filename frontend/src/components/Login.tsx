import { useState } from "react";
import { Icon } from "./Icon";
import { Feedback } from "./Feedback";

interface LoginProps {
  readonly checking: boolean;
  readonly error: string;
  readonly onConnect: (token: string) => void;
}

export function Login({ checking, error, onConnect }: LoginProps) {
  const [draft, setDraft] = useState("");
  const [visible, setVisible] = useState(false);
  return (
    <main id="main-content" className="login-page">
      <section className="login-form">
        <div className="login-context">
          <Icon name="key" />
          <span>Management connection</span>
        </div>
        <h1 tabIndex={-1}>Open your inbox</h1>
        <p className="muted">
          Use the management token from your server’s private credentials file.
        </p>
        {error && <Feedback tone="error">{error}</Feedback>}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.trim()) onConnect(draft);
          }}
          aria-busy={checking}
        >
          <label htmlFor="management-token">Management token</label>
          <div className="token-input">
            <input
              id="management-token"
              type={visible ? "text" : "password"}
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              required
              disabled={checking}
              aria-describedby="token-help"
            />
            <button
              type="button"
              className="ghost"
              onClick={() => setVisible(!visible)}
              aria-label={visible ? "Hide token" : "Show token"}
              aria-pressed={visible}
            >
              {visible ? "Hide" : "Show"}
            </button>
          </div>
          <button
            className="connect-button"
            disabled={checking || !draft.trim()}
          >
            <Icon name={checking ? "clock" : "arrow"} />
            {checking ? "Checking…" : "Connect"}
          </button>
        </form>
        <p id="token-help" className="small muted login-security">
          The token stays in this tab’s session storage. Receiving messages uses
          a separate ingest token.
        </p>
      </section>
      <div className="login-pipeline">
        <span>Receive</span>
        <Icon name="arrow" size={14} />
        <span>Store</span>
        <Icon name="arrow" size={14} />
        <span>Forward</span>
        <p>Stored before receipt. Delivered in the background.</p>
      </div>
    </main>
  );
}
