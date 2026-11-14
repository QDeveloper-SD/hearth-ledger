import { useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Wallet } from "lucide-react";
import { login, setupAccount, getAuthStatus } from "@/lib/api";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");
  // null while we ask the server whether a login exists yet
  const [isFirstRun, setIsFirstRun] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    getAuthStatus()
      .then((s) => { if (alive) setIsFirstRun(s.needs_setup); })
      .catch(() => { if (alive) { setIsFirstRun(false); setError("Could not connect to server."); } });
    return () => { alive = false; };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (isFirstRun) {
      if (!username.trim()) return setError("Choose a username.");
      if (password.length < 8) return setError("Password must be at least 8 characters.");
      if (password !== confirm) return setError("Passwords do not match.");
    }
    setLoading(true);
    try {
      const res = isFirstRun ? await setupAccount(username.trim(), password) : await login(username, password);
      if (res.error) {
        setError(res.error);
      } else {
        navigate({ to: "/app/dashboard" });
      }
    } catch {
      setError("Could not connect to server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-soft via-background to-background p-6">
      <Card className="w-full max-w-md p-8 shadow-xl">
        <div className="flex items-center gap-3 mb-8">
          <div className="h-11 w-11 rounded-xl bg-primary text-primary-foreground grid place-items-center">
            <Wallet className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Hearth Ledger</h1>
            <p className="text-xs text-muted-foreground">Family accounting, simplified.</p>
          </div>
        </div>
        {isFirstRun && (
          <div className="mb-5">
            <h2 className="font-medium">Welcome. Create your login</h2>
            <p className="text-xs text-muted-foreground mt-1">
              One login is shared by the household. It is stored only on this computer, so there is no reset link: keep the password somewhere safe.
            </p>
          </div>
        )}
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="username">{isFirstRun ? "Choose username" : "Username"}</Label>
            <Input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pw">{isFirstRun ? "Choose password" : "Password"}</Label>
            <Input
              id="pw"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isFirstRun ? "new-password" : "current-password"}
            />
            {isFirstRun && <p className="text-xs text-muted-foreground">At least 8 characters.</p>}
          </div>
          {isFirstRun && (
            <div className="space-y-2">
              <Label htmlFor="pw2">Confirm password</Label>
              <Input id="pw2" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
            </div>
          )}
          {error && <p className="text-xs text-loss" role="alert">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading || isFirstRun === null}>
            {loading ? "…" : isFirstRun ? "Create account" : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
