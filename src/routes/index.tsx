import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Wallet } from "lucide-react";
import { login } from "@/lib/api";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const isFirstRun = false;
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(username, password);
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
              autoComplete="current-password"
            />
          </div>
          {error && <p className="text-xs text-loss">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "…" : isFirstRun ? "Create account" : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
