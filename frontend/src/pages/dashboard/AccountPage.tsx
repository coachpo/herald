
import { useState } from "react";

import { readApiError, readJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { authedFetch } from "@/lib/authed";

export default function AccountPage() {
  const auth = useAuth();
  const user = auth.user;
  const verified = Boolean(user?.email_verified_at);

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [newEmail, setNewEmail] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const [deletePassword, setDeletePassword] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);

  async function callNoBody(path: string) {
    setError(null);
    setMessage(null);
    const res = await authedFetch(auth, path, { method: "POST" });
    if (!res.ok) {
      const err = await readApiError(res);
      setError(err.message);
      return false;
    }
    return true;
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="text-lg font-semibold tracking-tight">Account</div>
        <div className="mt-1 text-sm text-muted-foreground">Profile and security settings.</div>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive dark:border-destructive/30 dark:bg-destructive/10">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-xl border border-success/20 bg-success/10 px-3 py-2 text-sm text-success dark:border-success/30 dark:bg-success/10">
          {message}
        </div>
      )}

      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="text-sm font-semibold">Profile</div>
        <div className="mt-2 text-sm text-muted-foreground">Email: {user?.email}</div>
        <div className="mt-1 text-sm text-muted-foreground">
          Status:{" "}
          {verified ? (
            <span className="font-semibold text-success">verified</span>
          ) : (
            <span className="font-semibold text-warning">unverified</span>
          )}
        </div>
        {!verified && (
          <button
            className="mt-3 rounded-xl border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted"
            onClick={async () => {
              const ok = await callNoBody("/api/auth/resend-verification");
              if (ok) setMessage("Verification email sent (if allowed). Check your inbox.");
            }}
          >
            Resend verification email
          </button>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="text-sm font-semibold">Change email</div>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            type="email"
            placeholder="new email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
          />
          <button
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            disabled={!newEmail.trim()}
            onClick={async () => {
              setError(null);
              setMessage(null);
              const res = await authedFetch(auth, "/api/auth/change-email", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ new_email: newEmail }),
              });
              if (!res.ok) {
                setError((await readApiError(res)).message);
                return;
              }
              const data = await readJson<{ user: { email: string } }>(res);
              setMessage(`Email updated to ${data.user.email}. Verification required again.`);
              setNewEmail("");
              await auth.refresh();
            }}
          >
            Change
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="text-sm font-semibold">Change password</div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <input
            className="rounded-xl border border-border bg-card px-3 py-2 text-sm"
            type="password"
            placeholder="old password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
          />
          <input
            className="rounded-xl border border-border bg-card px-3 py-2 text-sm"
            type="password"
            placeholder="new password (min 8)"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            minLength={8}
          />
        </div>
        <button
          className="mt-3 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          disabled={!oldPassword || newPassword.length < 8}
          onClick={async () => {
            setError(null);
            setMessage(null);
            const res = await authedFetch(auth, "/api/auth/change-password", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
            });
            if (!res.ok) {
              setError((await readApiError(res)).message);
              return;
            }
            setOldPassword("");
            setNewPassword("");
            setMessage("Password updated.");
          }}
        >
          Change password
        </button>
      </div>

      <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-4 dark:border-destructive/30 dark:bg-destructive/10">
        <div className="text-sm font-semibold text-destructive">Delete account</div>
        <div className="mt-1 text-sm text-destructive/80">
          Irreversible. Deletes your account and all messages, endpoints, channels, rules, and deliveries.
        </div>

        <div className="mt-3">
          <input
            className="rounded-xl border border-destructive/20 bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
            type="password"
            placeholder="password"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
            disabled={deleteBusy}
          />
        </div>

        <button
          className="mt-3 rounded-xl bg-destructive px-4 py-2 text-sm font-semibold text-white hover:bg-destructive/90 disabled:opacity-50"
          disabled={deleteBusy || !deletePassword}
          onClick={async () => {
            if (!confirm("Delete your account? This cannot be undone.")) return;
            setError(null);
            setMessage(null);
            setDeleteBusy(true);
            try {
              const res = await authedFetch(auth, "/api/auth/delete-account", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ password: deletePassword }),
              });
              if (!res.ok) {
                setError((await readApiError(res)).message);
                return;
              }
              setMessage("Account deleted.");
              await auth.logout();
              window.location.href = "/signup";
            } finally {
              setDeleteBusy(false);
            }
          }}
        >
          Delete account
        </button>
      </div>
    </div>
  );
}
