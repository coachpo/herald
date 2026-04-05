import { Link } from "react-router";
import { useState, useEffect } from "react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ResetPasswordForm({ token }: { token: string | null }) {
  const [resolvedToken, setResolvedToken] = useState<string | null>(token);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (resolvedToken) return;
    const t = new URLSearchParams(window.location.search).get("token");
    if (t) setResolvedToken(t);
  }, [resolvedToken]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-md px-6 py-16">
        <Card>
          <CardHeader>
            <CardTitle>Reset password</CardTitle>
            <CardDescription>Set a new password for your account.</CardDescription>
          </CardHeader>
          <CardContent>
            {!resolvedToken && (
              <div className="text-sm text-muted-foreground">Missing token.</div>
            )}

            {message && (
              <Alert className="mt-4">
                <AlertDescription>{message}</AlertDescription>
              </Alert>
            )}
            {error && (
              <Alert variant="destructive" className="mt-4">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

          {resolvedToken && (
            <form
              className="mt-5 space-y-3"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                setError(null);
                setMessage(null);
                try {
                  const res = await apiFetch("/api/auth/reset-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ token: resolvedToken, new_password: password }),
                  });
                  if (!res.ok) {
                    const err = await readApiError(res);
                    setError(err.message);
                    return;
                  }
                  setMessage("Password updated. You can log in now.");
                } catch (error) {
                  setError(readRequestError(error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <div className="space-y-2">
                <Label htmlFor="reset-password">New password</Label>
                <Input
                  id="reset-password"
                  name="new_password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </div>

              <Button disabled={busy} className="w-full" type="submit">
                {busy ? "Saving..." : "Set new password"}
              </Button>
            </form>
          )}

            <div className="mt-5">
              <Button variant="link" asChild className="px-0">
                <Link to="/login">Back to login</Link>
              </Button>
            </div>
          </CardContent>
          <CardFooter />
        </Card>
      </div>
    </div>
  );
}
