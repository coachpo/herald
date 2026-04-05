import { useSearchParams } from "react-router";
import { useMemo } from "react";

import { LoginForm } from "@/components/LoginForm";

function sanitizeSameSiteNextPath(raw: string | null): string {
  const p = (raw || "").trim();
  if (!p) return "/";
  if (!p.startsWith("/")) return "/";
  if (p.startsWith("//")) return "/";
  return p;
}

export default function LoginPage() {
  const [sp] = useSearchParams();
  const nextPath = useMemo(() => sanitizeSameSiteNextPath(sp.get("next")), [sp]);
  return <LoginForm nextPath={nextPath} />;
}
