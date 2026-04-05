import { Link } from "react-router";
import { useEffect, useState } from "react";

import { apiFetch, readApiError, readRequestError } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function VerifyEmailClient({ token }: { token: string | null }) {
  const [resolvedToken, setResolvedToken] = useState<string | null>(token);
  const [status, setStatus] = useState<"idle" | "ok" | "err">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (resolvedToken) return;
    const t = new URLSearchParams(window.location.search).get("token");
    if (t) setResolvedToken(t);
  }, [resolvedToken]);

  useEffect(() => {
    if (!resolvedToken) return;
    (async () => {
      try {
        const res = await apiFetch("/api/auth/verify-email", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: resolvedToken }),
        });
        if (!res.ok) {
          const err = await readApiError(res);
          setStatus("err");
          setError(err.message);
          return;
        }
        setStatus("ok");
      } catch (error) {
        setStatus("err");
        setError(readRequestError(error).message);
      }
    })();
  }, [resolvedToken]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-md px-6 py-16">
        <Card>
          <CardHeader>
            <CardTitle>Verify email</CardTitle>
            <CardDescription>Confirm your email address to unlock all features.</CardDescription>
          </CardHeader>
          <CardContent>
            {!resolvedToken && (
              <div className="text-sm text-muted-foreground">Missing token.</div>
            )}
            {resolvedToken && status === "idle" && (
              <div className="text-sm text-muted-foreground">Verifying...</div>
            )}
            {status === "ok" && (
              <Alert className="mt-4">
                <AlertDescription>Email verified.</AlertDescription>
              </Alert>
            )}
            {status === "err" && (
              <Alert variant="destructive" className="mt-4">
                <AlertDescription>{error ?? "Verification failed."}</AlertDescription>
              </Alert>
            )}
          </CardContent>
          <CardFooter>
            <Button variant="link" asChild className="px-0">
              <Link to="/login">Go to login</Link>
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
