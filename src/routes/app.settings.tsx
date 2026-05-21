import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { PageHeader, Panel } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { Printer, FolderOpen } from "lucide-react";
import { getSettings, updateSettings, setApiKey, exportPdf } from "@/lib/api";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["settings"], queryFn: getSettings });

  const [live, setLive] = useState(true);
  const [dark, setDark] = useState(false);
  const [apiKey, setApiKeyValue] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [pdfBalance, setPdfBalance] = useState(true);
  const [pdfLedger, setPdfLedger] = useState(true);
  const [pdfPortfolio, setPdfPortfolio] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  useEffect(() => {
    if (data) {
      setLive(data.live_sync);
      setDark(data.theme === "dark");
      setNewUsername(data.username ?? "");
    }
  }, [data]);

  const saveSettings = useMutation({
    mutationFn: (body: Parameters<typeof updateSettings>[0]) => updateSettings(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      setSaveMsg("Saved.");
      setTimeout(() => setSaveMsg(""), 2000);
    },
  });

  const saveKey = useMutation({
    mutationFn: () => setApiKey(apiKey),
    onSuccess: () => { setSaveMsg("API key saved."); setTimeout(() => setSaveMsg(""), 2000); },
  });

  async function handlePdf() {
    const sections: string[] = [];
    if (pdfBalance) sections.push("balance");
    if (pdfLedger) sections.push("ledger");
    if (pdfPortfolio) sections.push("portfolio");
    const res = await exportPdf(sections);
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "hearth-report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (isLoading) return <div className="space-y-6"><PageHeader title="Settings" /><Skeleton className="h-64 w-full" /></div>;
  if (error) return <div className="space-y-6"><PageHeader title="Settings" /><p className="text-sm text-loss">Failed to load settings.</p></div>;

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Preferences and account configuration." />
      {saveMsg && <p className="text-sm text-profit">{saveMsg}</p>}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Public.com API Secret">
          <Label htmlFor="api">Secret</Label>
          <Input id="api" type="password" placeholder="paste your Public.com secret" value={apiKey} onChange={(e) => setApiKeyValue(e.target.value)} />
          <p className="text-xs text-muted-foreground mt-2">Generated from your Public.com account settings. Exchanged for short-lived access tokens automatically.</p>
          <Button className="mt-3" size="sm" disabled={saveKey.isPending} onClick={() => saveKey.mutate()}>
            {saveKey.isPending ? "Saving…" : "Save secret"}
          </Button>
        </Panel>

        <Panel title="Data Location">
          <Label>Local data folder</Label>
          <div className="flex gap-2">
            <Input readOnly value={data?.data_dir ?? "/data/hearth.json"} />
            <Button variant="outline"><FolderOpen className="h-4 w-4" /> Browse</Button>
          </div>
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
            <Button size="sm" disabled={saveSettings.isPending} onClick={() => saveSettings.mutate({ current_password: currentPassword, new_password: newPassword } as Parameters<typeof updateSettings>[0])}>Update password</Button>
          </div>
        </Panel>

        <Panel title="Change Username">
          <div className="space-y-2">
            <Input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} />
            <Button size="sm" disabled={saveSettings.isPending} onClick={() => saveSettings.mutate({ username: newUsername })}>Update username</Button>
          </div>
        </Panel>

        <Panel title="Print PDF" className="lg:col-span-2">
          <p className="text-sm text-muted-foreground mb-3">Select sections to include in the printed report.</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="flex items-center gap-2"><input type="checkbox" checked={pdfBalance} onChange={(e) => setPdfBalance(e.target.checked)} /> Balance sheet</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={pdfLedger} onChange={(e) => setPdfLedger(e.target.checked)} /> Ledger history</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={pdfPortfolio} onChange={(e) => setPdfPortfolio(e.target.checked)} /> Portfolio detail</label>
          </div>
          <Button className="mt-4" onClick={handlePdf}><Printer className="h-4 w-4" /> Print PDF</Button>
        </Panel>
      </div>
    </div>
  );
}
