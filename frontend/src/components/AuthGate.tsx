import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";

import { useAuth } from "@/lib/auth";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { loading, user, refresh } = useAuth();

  useEffect(() => {
    const refreshTimer = setTimeout(() => {
      void refresh();
    }, 0);
    return () => clearTimeout(refreshTimer);
  }, [refresh]);

  useEffect(() => {
    if (!loading && !user) {
      navigate(`/login?next=${encodeURIComponent(pathname ?? "/")}`, { replace: true });
    }
  }, [loading, user, navigate, pathname]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <div className="mx-auto max-w-3xl px-6 py-16">Loading...</div>
      </div>
    );
  }
  if (!user) return null;
  return children;
}
