import { Link, useLocation } from "react-router";

import { useAuth } from "@/lib/auth";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/messages", label: "Messages" },
  { href: "/ingest-endpoints", label: "Ingest endpoints" },
  { href: "/channels", label: "Channels" },
  { href: "/rules", label: "Rules" },
  { href: "/account", label: "Account" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-6xl px-4 py-6">
        <header className="flex items-center justify-between rounded-2xl border border-border bg-card px-5 py-4 shadow-sm">
          <div>
            <div className="text-sm font-semibold tracking-tight">Herald</div>
            <div className="text-xs text-muted-foreground">Ingest, store, forward.</div>
          </div>
          <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
            <ThemeToggle />
            <div className="min-w-0 max-w-[12rem] truncate text-xs text-muted-foreground sm:max-w-[20rem]">
              {user?.email}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void logout()}
            >
              Log out
            </Button>
          </div>
        </header>

        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-[220px_1fr]">
          <nav className="min-w-0 rounded-2xl border border-border bg-card p-3 shadow-sm">
            <ul className="flex flex-col gap-1">
              {NAV.map((item) => {
                const active = item.href === "/" ? pathname === "/" : pathname?.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Button
                      asChild
                      variant={active ? "default" : "ghost"}
                      className="w-full justify-start"
                    >
                      <Link to={item.href}>{item.label}</Link>
                    </Button>
                  </li>
                );
              })}
            </ul>
          </nav>

          <main className="min-w-0 rounded-2xl border border-border bg-card p-5 shadow-sm">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
