import { Outlet } from "react-router";
import { AuthProvider } from "@/lib/auth";

export function AuthLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
}
