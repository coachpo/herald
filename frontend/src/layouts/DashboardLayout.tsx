import { Outlet } from "react-router";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth";

export function DashboardLayout() {
  return (
    <AuthProvider>
      <AuthGate>
        <AppShell>
          <Outlet />
        </AppShell>
      </AuthGate>
    </AuthProvider>
  );
}
