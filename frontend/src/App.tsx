import { useCallback, useEffect, useState } from "react";
import { api, ApiError, errorText } from "./lib/api";
import type { Target, Settings } from "./lib/types";
import { Messages } from "./Messages";
import { Targets } from "./Targets";

const TOKEN_KEY = "herald_admin_token";

export function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem(TOKEN_KEY) ?? "",
  );
  const [draft, setDraft] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(Boolean(token));
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState("");
  const [view, setView] = useState<"messages" | "targets">("messages");
  const [targets, setTargets] = useState<Target[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);

  const disconnect = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken("");
    setDraft("");
    setAuthenticated(false);
    setChecking(false);
    setTargets([]);
    setSettings(null);
  }, []);

  const report = useCallback(
    (failure: unknown) => {
      if (failure instanceof ApiError && failure.status === 401) disconnect();
      setError(errorText(failure));
    },
    [disconnect],
  );

  const loadTargets = useCallback(async () => {
    const result = await api<{ targets: Target[] }>(token, "/targets");
    setTargets(result.targets);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setChecking(true);
    void api<{ authenticated: boolean }>(token, "/session")
      .then(async () => {
        if (cancelled) return;
        sessionStorage.setItem(TOKEN_KEY, token);
        setAuthenticated(true);
        setDraft("");
        const [targetResult, settingsResult] = await Promise.all([
          api<{ targets: Target[] }>(token, "/targets"),
          api<Settings>(token, "/settings"),
        ]);
        if (!cancelled) {
          setTargets(targetResult.targets);
          setSettings(settingsResult);
        }
      })
      .catch((failure) => {
        if (!cancelled) report(failure);
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, report, attempt]);

  if (!authenticated)
    return (
      <main className="login panel">
        <p className="eyebrow">Herald</p>
        <h1>Open your inbox</h1>
        <p>
          Use the management token from your server’s private credentials file.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setError("");
            setToken(draft.trim());
            setAttempt((value) => value + 1);
          }}
        >
          <label>
            Management token
            <input
              type="password"
              autoComplete="off"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              required
            />
          </label>
          <button disabled={checking}>
            {checking ? "Checking…" : "Connect"}
          </button>
        </form>
        <small>
          The token stays in this tab’s session storage. Receiving messages uses
          a separate ingest token.
        </small>
      </main>
    );

  return (
    <div className="app">
      <header>
        <div>
          <p className="eyebrow">Herald</p>
          <h1>Receive. Store. Forward.</h1>
        </div>
        <button className="secondary" onClick={disconnect}>
          Disconnect
        </button>
      </header>
      <nav aria-label="Main navigation">
        <button
          aria-current={view === "messages" ? "page" : undefined}
          onClick={() => setView("messages")}
        >
          Messages
        </button>
        <button
          aria-current={view === "targets" ? "page" : undefined}
          onClick={() => setView("targets")}
        >
          Targets
        </button>
      </nav>
      {error && (
        <div className="error notice" role="alert">
          {error}
          <button className="secondary" onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      )}
      {view === "messages" ? (
        <Messages
          token={token}
          targets={targets}
          settings={settings}
          report={report}
        />
      ) : (
        <Targets
          token={token}
          targets={targets}
          reload={loadTargets}
          report={report}
        />
      )}
    </div>
  );
}
