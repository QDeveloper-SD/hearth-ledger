import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PageHeader, Panel } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { Printer, FolderOpen } from "lucide-react";
import { getSettings, updateSettings, setApiKey, deleteApiKey, setIbkr, deleteIbkr, changePassword, changeUsername, exportPdf } from "@/lib/api";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["settings"], queryFn: getSettings });

  const [live, setLive] = useState(true);
  const [dark, setDark] = useState(false);
  const [apiKey, setApiKeyValue] = useState("");
  const [ibkrToken, setIbkrToken] = useState("");
  const [ibkrQuery, setIbkrQuery] = useState("");
  const [ibkrMsg, setIbkrMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [pdfBalance, setPdfBalance] = useState(true);
  const [pdfLedger, setPdfLedger] = useState(true);
  const [pdfPortfolio, setPdfPortfolio] = useState(false);
  const [pdfIncome, setPdfIncome] = useState(true);

  useEffect(() => {
    if (data) {
      setLive(data.live_sync);
      setDark(data.theme === "dark");
      setNewUsername(data.username ?? "");
      setIbkrQuery(data.ibkr_query_id ?? "");
    }
  }, [data]);

  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [unMsg, setUnMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [keyMsg, setKeyMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pdfMsg, setPdfMsg] = useState<string>("");
  const [pdfBusy, setPdfBusy] = useState(false);
  const [dirMsg, setDirMsg] = useState<string>("");

  const hearth = typeof window !== "undefined" ? window.hearth : undefined;
  const isDesktop = !!hearth?.isDesktop;

  const errText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

  const saveSettings = useMutation({
    mutationFn: (body: Parameters<typeof updateSettings>[0]) => updateSettings(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      setMsg({ ok: true, text: "Saved." });
      setTimeout(() => setMsg(null), 2000);
    },
    onError: (e) => setMsg({ ok: false, text: errText(e) }),
  });

  const saveKey = useMutation({
    mutationFn: () => setApiKey(apiKey.trim()),
    onSuccess: () => {
      setApiKeyValue("");
      setKeyMsg({ ok: true, text: "API secret saved." });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => setKeyMsg({ ok: false, text: errText(e) }),
  });

  const removeKey = useMutation({
    mutationFn: deleteApiKey,
    onSuccess: () => {
      setKeyMsg({ ok: true, text: "API secret removed." });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => setKeyMsg({ ok: false, text: errText(e) }),
  });

  const saveIbkr = useMutation({
    mutationFn: () => setIbkr(ibkrToken.trim(), ibkrQuery.trim()),
    onSuccess: () => {
      setIbkrToken("");
      setIbkrMsg({ ok: true, text: "IBKR connection saved. Press Sync in Portfolio → IBKR." });
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
    onError: (e) => setIbkrMsg({ ok: false, text: errText(e) }),
  });

  const removeIbkr = useMutation({
    mutationFn: deleteIbkr,
    onSuccess: () => {
      setIbkrToken("");
      setIbkrQuery("");
      setIbkrMsg({ ok: true, text: "IBKR disconnected and synced positions removed." });
      for (const k of ["settings", "portfolio", "dashboard", "risk"]) qc.invalidateQueries({ queryKey: [k] });
    },
    onError: (e) => setIbkrMsg({ ok: false, text: errText(e) }),
  });

  function submitIbkr() {
    if (!ibkrToken.trim()) return setIbkrMsg({ ok: false, text: "Paste your Flex Web Service token." });
    if (!/^\d+$/.test(ibkrQuery.trim())) return setIbkrMsg({ ok: false, text: "The Flex Query ID is a number, shown next to your query in IBKR." });
    setIbkrMsg(null);
    saveIbkr.mutate();
  }

  const savePassword = useMutation({
    mutationFn: () => changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPwMsg({ ok: true, text: "Password updated." });
    },
    onError: (e) => setPwMsg({ ok: false, text: errText(e) }),
  });

  function submitPassword() {
    if (!currentPassword) return setPwMsg({ ok: false, text: "Enter your current password." });
    if (newPassword.length < 8) return setPwMsg({ ok: false, text: "New password must be at least 8 characters." });
    if (newPassword !== confirmPassword) return setPwMsg({ ok: false, text: "New passwords do not match." });
    setPwMsg(null);
    savePassword.mutate();
  }

  const saveUsername = useMutation({
    mutationFn: () => changeUsername(newUsername.trim()),
    onSuccess: (r) => {
      setNewUsername(r.username);
      setUnMsg({ ok: true, text: "Username updated." });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => setUnMsg({ ok: false, text: errText(e) }),
  });

  async function browse() {
    setDirMsg("");
    try {
      const r = await hearth?.chooseDataDir();
      if (r?.path) setDirMsg(`Data moved to ${r.path}.`);
    } catch (e) {
      setDirMsg(errText(e));
    }
  }

  async function handlePdf() {
    const sections: string[] = [];
    if (pdfBalance) sections.push("balance");
    if (pdfIncome) sections.push("income");
    if (pdfLedger) sections.push("ledger");
    if (pdfPortfolio) sections.push("portfolio");
    setPdfMsg("");
    setPdfBusy(true);
    try {
      const res = await exportPdf(sections);
      if (!res.ok) {
        let detail = "";
        try {
          const j = await res.json();
          detail = typeof j?.error === "string" ? j.error : typeof j?.detail === "string" ? j.detail : "";
        } catch { /* ignore */ }
        setPdfMsg(`PDF export failed (${res.status})${detail ? `: ${detail}` : "."}`);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "hearth-report.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setPdfMsg(`PDF export failed: ${errText(e)}`);
    } finally {
      setPdfBusy(false);
    }
  }

  const Msg = ({ m }: { m: { ok: boolean; text: string } | null }) =>
    m ? <p className={`text-xs mt-2 ${m.ok ? "text-profit" : "text-loss"}`} role={m.ok ? "status" : "alert"}>{m.text}</p> : null;

  if (isLoading) return <div className="space-y-6"><PageHeader title="Settings" /><Skeleton className="h-64 w-full" /></div>;
  if (error) return <div className="space-y-6"><PageHeader title="Settings" /><p className="text-sm text-loss">Failed to load settings.</p></div>;

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Preferences and account configuration." />
      {msg && <p className={`text-sm ${msg.ok ? "text-profit" : "text-loss"}`} role="alert">{msg.text}</p>}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Public.com API Secret">
          <Label htmlFor="api">Secret</Label>
          <Input id="api" type="password" placeholder="paste your Public.com secret" value={apiKey} onChange={(e) => setApiKeyValue(e.target.value)} />
          <p className="text-xs text-muted-foreground mt-2">Generated from your Public.com account settings. Exchanged for short-lived access tokens automatically.</p>
          <p className="text-xs mt-2">
            Status: {data?.has_api_key ? <span className="text-profit">secret saved</span> : <span className="text-muted-foreground">no secret saved</span>}
          </p>
          <div className="flex gap-2 mt-3">
            <Button size="sm" disabled={saveKey.isPending || !apiKey.trim()} onClick={() => { setKeyMsg(null); saveKey.mutate(); }}>
              {saveKey.isPending ? "Saving…" : "Save secret"}
            </Button>
            {data?.has_api_key && (
              <Button size="sm" variant="outline" disabled={removeKey.isPending} onClick={() => { setKeyMsg(null); removeKey.mutate(); }}>
                Remove secret
              </Button>
            )}
          </div>
          <Msg m={keyMsg} />
        </Panel>

        <Panel title="Interactive Brokers (read-only)">
          <div className="space-y-2">
            <div>
              <Label htmlFor="ibkr-token">Flex Web Service token</Label>
              <Input id="ibkr-token" type="password" autoComplete="off" placeholder={data?.has_ibkr ? "saved — paste a new token to replace" : "paste your Flex token"} value={ibkrToken} onChange={(e) => setIbkrToken(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="ibkr-query">Flex Query ID</Label>
              <Input id="ibkr-query" inputMode="numeric" placeholder="e.g. 123456" value={ibkrQuery} onChange={(e) => setIbkrQuery(e.target.value)} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Uses IBKR's Flex Web Service, which can only deliver reports: it cannot place trades or move money.
            In IBKR Client Portal open Performance &amp; Reports → Flex Queries. Create an Activity Flex Query that
            includes Open Positions and Cash Report (its Query ID appears beside it), then enable Flex Web Service
            Configuration to generate a token.
          </p>
          <p className="text-xs mt-2">
            Status: {data?.has_ibkr ? <span className="text-profit">connected</span> : <span className="text-muted-foreground">not connected</span>}
          </p>
          <div className="flex gap-2 mt-3">
            <Button size="sm" disabled={saveIbkr.isPending} onClick={submitIbkr}>
              {saveIbkr.isPending ? "Saving…" : "Save connection"}
            </Button>
            {data?.has_ibkr && (
              <Button size="sm" variant="outline" disabled={removeIbkr.isPending} onClick={() => { setIbkrMsg(null); removeIbkr.mutate(); }}>
                Disconnect
              </Button>
            )}
          </div>
          <Msg m={ibkrMsg} />
        </Panel>

        <Panel title="Data Location">
          <Label>Local data folder</Label>
          <div className="flex gap-2">
            <Input readOnly value={data?.data_dir ?? ""} />
            <Button variant="outline" disabled={!isDesktop} onClick={browse}><FolderOpen className="h-4 w-4" /> Browse</Button>
            {isDesktop && hearth?.openDataDir && (
              <Button variant="outline" size="sm" onClick={() => hearth.openDataDir?.().catch((e) => setDirMsg(errText(e)))}>Open folder</Button>
            )}
          </div>
          {!isDesktop && (
            <p className="text-xs text-muted-foreground mt-2">Folder selection is available in the desktop app. In server mode set HEARTH_DATA_DIR.</p>
          )}
          {dirMsg && <p className="text-xs mt-2 text-muted-foreground">{dirMsg}</p>}
        </Panel>

        <Panel title="Live Sync">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{live ? "Live" : "Offline"}</p>
              <p className="text-xs text-muted-foreground">Pulls quotes &amp; balances in real time.</p>
            </div>
            <Switch checked={live} onCheckedChange={(v) => { setLive(v); saveSettings.mutate({ live_sync: v }); }} />
          </div>
        </Panel>

        <Panel title="Theme">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{dark ? "Dark" : "Light"}</p>
              <p className="text-xs text-muted-foreground">Switch the interface appearance.</p>
            </div>
            <Switch checked={dark} onCheckedChange={(v) => {
              setDark(v);
              document.documentElement.classList.toggle("dark", v);
              saveSettings.mutate({ theme: v ? "dark" : "light" });
            }} />
          </div>
        </Panel>

        <Panel title="Change Password">
          <div className="space-y-2">
            <Input type="password" placeholder="Current password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
            <Input type="password" placeholder="New password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
            <Input type="password" placeholder="Confirm new password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
            <Button size="sm" disabled={savePassword.isPending} onClick={submitPassword}>Update password</Button>
            <Msg m={pwMsg} />
          </div>
        </Panel>

        <Panel title="Change Username">
          <div className="space-y-2">
            <Input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} />
            <Button size="sm" disabled={saveUsername.isPending || !newUsername.trim() || newUsername.trim() === data?.username} onClick={() => { setUnMsg(null); saveUsername.mutate(); }}>Update username</Button>
            <Msg m={unMsg} />
          </div>
        </Panel>

        <Panel title="Print PDF" className="lg:col-span-2">
          <p className="text-sm text-muted-foreground mb-3">Select sections to include in the printed report.</p>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <label className="flex items-center gap-2"><input type="checkbox" checked={pdfBalance} onChange={(e) => setPdfBalance(e.target.checked)} /> Balance sheet</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={pdfIncome} onChange={(e) => setPdfIncome(e.target.checked)} /> Income sources</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={pdfLedger} onChange={(e) => setPdfLedger(e.target.checked)} /> Ledger history</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={pdfPortfolio} onChange={(e) => setPdfPortfolio(e.target.checked)} /> Portfolio detail</label>
          </div>
          <Button className="mt-4" disabled={pdfBusy} onClick={handlePdf}><Printer className="h-4 w-4" /> {pdfBusy ? "Generating…" : "Print PDF"}</Button>
          {pdfMsg && <p className="text-xs mt-2 text-loss" role="alert">{pdfMsg}</p>}
        </Panel>
      </div>
    </div>
  );
}
