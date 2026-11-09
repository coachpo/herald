import { useState } from "react";
import { useSession } from "./hooks/useSession";
import { useTheme } from "./hooks/useTheme";
import { useMessages } from "./hooks/useMessages";
import { useRouting } from "./hooks/useRouting";
import { Messages } from "./Messages";
import { SendMessage } from "./SendMessage";
import { Targets } from "./Targets";
import { Connection } from "./Connection";
import { Login } from "./components/Login";
import { ThemePicker } from "./components/ThemePicker";
import { HeraldMark, Icon } from "./components/Icon";
import { Feedback } from "./components/Feedback";

type View = "messages" | "send" | "targets" | "connection";
const destinations = [
  { view: "messages", label: "Messages", icon: "inbox" },
  { view: "send", label: "Send message", icon: "send" },
  { view: "targets", label: "Targets", icon: "target" },
  { view: "connection", label: "Connection", icon: "connection" },
] as const;

interface WorkspaceProps {
  readonly session: ReturnType<typeof useSession>;
}

function Workspace({ session }: WorkspaceProps) {
  const routing = useRouting(session.token, session.report);
  const [view, setView] = useState<View>("messages");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inspectReceipt, setInspectReceipt] = useState(false);
  const history = useMessages(
    session.token,
    session.report,
    view === "messages",
  );
  const navigate = (next: View) => {
    setInspectReceipt(false);
    setView(next);
    window.scrollTo({ top: 0 });
    requestAnimationFrame(() =>
      document
        .querySelector<HTMLElement>("main h1")
        ?.focus({ preventScroll: true }),
    );
  };
  return (
    <>
      <nav className="main-navigation" aria-label="Main navigation">
        {destinations.map((item) => (
          <button
            key={item.view}
            aria-current={view === item.view ? "page" : undefined}
            onClick={() => navigate(item.view)}
          >
            <Icon name={item.icon} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="work-sheet">
        {session.resourceError && (
          <Feedback tone="error" onRetry={() => void session.reloadResources()}>
            Couldn’t load targets or connection settings.{" "}
            {session.resourceError}
          </Feedback>
        )}
        {view === "messages" ? (
          <Messages
            history={history}
            onCompose={() => navigate("send")}
            selectedId={selectedId}
            onSelect={setSelectedId}
            openSelected={inspectReceipt}
          />
        ) : view === "send" ? (
          <SendMessage
            token={session.token}
            targets={session.targets}
            loading={session.resourcesLoading}
            report={session.report}
            onTargets={() => navigate("targets")}
            onStored={(id) => {
              setSelectedId(id);
              history.latest();
            }}
            onView={(id) => {
              setSelectedId(id);
              navigate("messages");
              setInspectReceipt(true);
            }}
          />
        ) : view === "targets" ? (
          <Targets
            routing={routing}
            token={session.token}
            targets={session.targets}
            reload={session.reloadTargets}
            report={session.report}
            loading={session.resourcesLoading}
            onRefresh={() => void session.reloadResources()}
          />
        ) : (
          <Connection
            token={session.token}
            settings={session.settings}
            report={session.report}
            onCleanup={() => {
              history.latest();
            }}
            onDisconnect={session.disconnect}
          />
        )}
      </div>
    </>
  );
}

export function App() {
  const session = useSession();
  const theme = useTheme();
  return (
    <div className={session.authenticated ? "app-shell" : "auth-shell"}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="brand">
        <HeraldMark />
        <span>
          Herald<small>Notification ledger</small>
        </span>
      </div>
      <header className="workspace-topbar">
        <span className="workspace-context">
          Single-user workspace <span>/</span> Receive. Store. Forward.
        </span>
        <div className="topbar-actions">
          <ThemePicker value={theme.preference} onChange={theme.choose} />
          {session.authenticated && (
            <button
              className="ghost disconnect"
              aria-label="Disconnect"
              onClick={session.disconnect}
            >
              <Icon name="logout" />
              <span>Disconnect</span>
            </button>
          )}
        </div>
      </header>
      {session.authenticated ? (
        <Workspace session={session} />
      ) : (
        <Login
          checking={session.checking}
          error={session.error}
          onConnect={session.connect}
        />
      )}
      {session.authenticated && (
        <div className="sidebar-foot">
          <span className="small">Single-user · Durable delivery</span>
          <p>Receive. Store. Forward.</p>
        </div>
      )}
    </div>
  );
}
