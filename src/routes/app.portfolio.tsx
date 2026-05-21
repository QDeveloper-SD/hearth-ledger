import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { LineChart as LineIcon, PieChart as PieIcon, RefreshCw, Plus, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { PageHeader, Panel, CHART_COLORS } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getPortfolio, syncPortfolio,
  createManualHolding, updateManualHolding, deleteManualHolding,
  createCashAccount, updateCashAccount, deleteCashAccount,
  type ManualHolding, type CashAccount,
} from "@/lib/api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";

// ---------------------------------------------------------------------------
// Manual Holdings dialog forms
// ---------------------------------------------------------------------------

type HoldingForm = { symbol: string; qty: string; cost_basis: string };
const emptyHoldingForm: HoldingForm = { symbol: "", qty: "", cost_basis: "" };

function ManualHoldingFormFields({ value, onChange }: { value: HoldingForm; onChange: (v: HoldingForm) => void }) {
  return (
    <div className="space-y-3">
      <div><Label>Symbol</Label><Input placeholder="e.g. BTC, RE-MainSt" value={value.symbol} onChange={(e) => onChange({ ...value, symbol: e.target.value })} /></div>
      <div><Label>Quantity</Label><Input type="number" step="any" value={value.qty} onChange={(e) => onChange({ ...value, qty: e.target.value })} /></div>
      <div><Label>Cost Basis ($)</Label><Input type="number" step="0.01" value={value.cost_basis} onChange={(e) => onChange({ ...value, cost_basis: e.target.value })} /></div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cash Account dialog forms
// ---------------------------------------------------------------------------

type CashForm = { name: string; balance: string };
const emptyCashForm: CashForm = { name: "", balance: "" };

function CashAccountFormFields({ value, onChange }: { value: CashForm; onChange: (v: CashForm) => void }) {
  return (
    <div className="space-y-3">
      <div><Label>Account name</Label><Input placeholder="e.g. Chase Checking" value={value.name} onChange={(e) => onChange({ ...value, name: e.target.value })} /></div>
      <div><Label>Balance ($)</Label><Input type="number" step="0.01" value={value.balance} onChange={(e) => onChange({ ...value, balance: e.target.value })} /></div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Portfolio() {
  const qc = useQueryClient();
  const [view, setView] = useState<"line" | "pie">("line");

  // Manual Holdings dialog state
  const [mhAddOpen, setMhAddOpen] = useState(false);
  const [mhEditOpen, setMhEditOpen] = useState(false);
  const [mhEditTarget, setMhEditTarget] = useState<ManualHolding | null>(null);
  const [mhForm, setMhForm] = useState<HoldingForm>(emptyHoldingForm);

  // Cash Accounts dialog state
  const [caAddOpen, setCaAddOpen] = useState(false);
  const [caEditOpen, setCaEditOpen] = useState(false);
  const [caEditTarget, setCaEditTarget] = useState<CashAccount | null>(null);
  const [caForm, setCaForm] = useState<CashForm>(emptyCashForm);

  const { data, isLoading, error } = useQuery({ queryKey: ["portfolio"], queryFn: getPortfolio });
  const sync = useMutation({ mutationFn: syncPortfolio, onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }) });

  const invalidateBoth = () => {
    qc.invalidateQueries({ queryKey: ["portfolio"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  // Manual Holdings mutations
  const mhAdd = useMutation({
    mutationFn: createManualHolding,
    onSuccess: () => { invalidateBoth(); setMhAddOpen(false); setMhForm(emptyHoldingForm); },
  });
  const mhEdit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Omit<ManualHolding, "id"> }) => updateManualHolding(id, body),
    onSuccess: () => { invalidateBoth(); setMhEditOpen(false); setMhEditTarget(null); },
  });
  const mhDelete = useMutation({
    mutationFn: deleteManualHolding,
    onSuccess: () => invalidateBoth(),
  });

  // Cash Account mutations
  const caAdd = useMutation({
    mutationFn: createCashAccount,
    onSuccess: () => { invalidateBoth(); setCaAddOpen(false); setCaForm(emptyCashForm); },
  });
  const caEdit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Omit<CashAccount, "id"> }) => updateCashAccount(id, body),
    onSuccess: () => { invalidateBoth(); setCaEditOpen(false); setCaEditTarget(null); },
  });
  const caDelete = useMutation({
    mutationFn: deleteCashAccount,
    onSuccess: () => invalidateBoth(),
  });

  function openMhEdit(h: ManualHolding) {
    setMhEditTarget(h);
    setMhForm({ symbol: h.symbol, qty: String(h.qty), cost_basis: String(h.cost_basis) });
    setMhEditOpen(true);
  }

  function openCaEdit(c: CashAccount) {
    setCaEditTarget(c);
    setCaForm({ name: c.name, balance: String(c.balance) });
    setCaEditOpen(true);
  }

  if (isLoading) return <div className="space-y-6"><PageHeader title="Portfolio" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !data) return <div className="space-y-6"><PageHeader title="Portfolio" /><p className="text-sm text-loss">Failed to load portfolio data.</p></div>;

  const manualHoldings = data.manual_holdings ?? [];
  const cashAccounts = data.cash_accounts ?? [];

  if (data.not_configured) {
    return (
      <div className="space-y-6">
        <PageHeader title="Portfolio" subtitle="Investment holdings and analytics." />
        <Panel>
          <p className="text-sm text-muted-foreground">Set your Public.com API secret in Settings to enable live portfolio sync.</p>
          <Button variant="outline" className="mt-3" onClick={() => {}}>Go to Settings</Button>
        </Panel>

        {/* Manual Holdings table is still shown in not_configured state */}
        <Panel
          title="Manual Holdings"
          action={<Button size="sm" onClick={() => { setMhForm(emptyHoldingForm); setMhAddOpen(true); }}><Plus className="h-3.5 w-3.5 mr-1" />Add</Button>}
        >
          {manualHoldings.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No manual holdings yet — click Add to enter one.</p>
          ) : (
            <ManualHoldingsTable holdings={manualHoldings} onEdit={openMhEdit} onDelete={(id) => mhDelete.mutate(id)} />
          )}
        </Panel>

        <Panel
          title="Cash Accounts"
          action={<Button size="sm" onClick={() => { setCaForm(emptyCashForm); setCaAddOpen(true); }}><Plus className="h-3.5 w-3.5 mr-1" />Add</Button>}
        >
          {cashAccounts.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No cash accounts yet — click Add to enter one.</p>
          ) : (
            <CashAccountsTable accounts={cashAccounts} onEdit={openCaEdit} onDelete={(id) => caDelete.mutate(id)} />
          )}
        </Panel>

        <ManualHoldingDialogs
          addOpen={mhAddOpen} setAddOpen={setMhAddOpen}
          editOpen={mhEditOpen} setEditOpen={setMhEditOpen}
          editTarget={mhEditTarget}
          form={mhForm} setForm={setMhForm}
          addMutation={mhAdd} editMutation={mhEdit}
        />
        <CashAccountDialogs
          addOpen={caAddOpen} setAddOpen={setCaAddOpen}
          editOpen={caEditOpen} setEditOpen={setCaEditOpen}
          editTarget={caEditTarget}
          form={caForm} setForm={setCaForm}
          addMutation={caAdd} editMutation={caEdit}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Portfolio" subtitle="Investment holdings and analytics." />
      <div className="flex gap-2">
        <Button variant={view === "line" ? "default" : "outline"} onClick={() => setView("line")}>
          <LineIcon className="h-4 w-4" /> Line
        </Button>
        <Button variant={view === "pie" ? "default" : "outline"} onClick={() => setView("pie")}>
          <PieIcon className="h-4 w-4" /> Pie
        </Button>
        <Button variant="outline" onClick={() => sync.mutate()} disabled={sync.isPending}>
          <RefreshCw className={"h-4 w-4 " + (sync.isPending ? "animate-spin" : "")} /> Sync
        </Button>
      </div>
      <Panel title={view === "line" ? "Value Over Time" : "Allocation"}>
        <ResponsiveContainer width="100%" height={320}>
          {view === "line" ? (
            <LineChart data={data.series}>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.93 0.01 250)" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
              <Line type="monotone" dataKey="value" stroke="oklch(0.72 0.12 230)" strokeWidth={2.5} dot={false} />
            </LineChart>
          ) : (
            <PieChart>
              <Pie data={data.allocation} dataKey="value" outerRadius={120} label>
                {data.allocation.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
              <Legend />
            </PieChart>
          )}
        </ResponsiveContainer>
      </Panel>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Holdings">
          <div className="max-h-[360px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-background text-xs text-muted-foreground uppercase text-left">
                <tr><th className="py-2">Symbol</th><th>Qty</th><th>Price</th><th className="text-right">Day</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.holdings.map((h) => (
                  <tr key={h.symbol}>
                    <td className="py-2.5">
                      <div className="font-medium">{h.symbol}</div>
                      {h.name && <div className="text-xs text-muted-foreground">{h.name}</div>}
                    </td>
                    <td>{h.qty}</td>
                    <td>{h.price != null ? `$${h.price.toLocaleString()}` : "—"}</td>
                    <td className={"text-right font-medium " + ((h.day_change ?? 0) >= 0 ? "text-profit" : "text-loss")}>
                      {h.day_change != null ? `${h.day_change >= 0 ? "+" : ""}${h.day_change}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <Panel title="Sharpe Ratio">
              <div className="text-4xl font-semibold">{data.sharpe_ratio.toFixed(2)}</div>
              <p className="text-xs text-muted-foreground mt-2">Risk-adjusted return</p>
            </Panel>
            <Panel title="Volatility">
              <div className="text-4xl font-semibold">{(data.volatility * 100).toFixed(1)}%</div>
              <p className="text-xs text-muted-foreground mt-2">Annualized std dev</p>
            </Panel>
          </div>
          <Panel title="Exposure">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={data.allocation} dataKey="value" innerRadius={45} outerRadius={85}>
                  {data.allocation.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                <Legend iconSize={8} />
              </PieChart>
            </ResponsiveContainer>
          </Panel>
        </div>
      </div>

      {/* Manual Holdings mini-table */}
      <Panel
        title="Manual Holdings"
        action={<Button size="sm" onClick={() => { setMhForm(emptyHoldingForm); setMhAddOpen(true); }}><Plus className="h-3.5 w-3.5 mr-1" />Add</Button>}
      >
        {manualHoldings.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">No manual holdings yet — click Add to enter one.</p>
        ) : (
          <ManualHoldingsTable holdings={manualHoldings} onEdit={openMhEdit} onDelete={(id) => mhDelete.mutate(id)} />
        )}
      </Panel>

      {/* Cash Accounts mini-table */}
      <Panel
        title="Cash Accounts"
        action={<Button size="sm" onClick={() => { setCaForm(emptyCashForm); setCaAddOpen(true); }}><Plus className="h-3.5 w-3.5 mr-1" />Add</Button>}
      >
        {cashAccounts.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">No cash accounts yet — click Add to enter one.</p>
        ) : (
          <CashAccountsTable accounts={cashAccounts} onEdit={openCaEdit} onDelete={(id) => caDelete.mutate(id)} />
        )}
      </Panel>

      <ManualHoldingDialogs
        addOpen={mhAddOpen} setAddOpen={setMhAddOpen}
        editOpen={mhEditOpen} setEditOpen={setMhEditOpen}
        editTarget={mhEditTarget}
        form={mhForm} setForm={setMhForm}
        addMutation={mhAdd} editMutation={mhEdit}
      />
      <CashAccountDialogs
        addOpen={caAddOpen} setAddOpen={setCaAddOpen}
        editOpen={caEditOpen} setEditOpen={setCaEditOpen}
        editTarget={caEditTarget}
        form={caForm} setForm={setCaForm}
        addMutation={caAdd} editMutation={caEdit}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ManualHoldingsTable({
  holdings,
  onEdit,
  onDelete,
}: {
  holdings: ManualHolding[];
  onEdit: (h: ManualHolding) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-muted-foreground uppercase text-left">
        <tr>
          <th className="py-2">Symbol</th>
          <th>Qty</th>
          <th>Cost Basis</th>
          <th className="text-right">Actions</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {holdings.map((h) => (
          <tr key={h.id}>
            <td className="py-2.5 font-medium">{h.symbol}</td>
            <td>{h.qty}</td>
            <td>${h.cost_basis.toLocaleString()}</td>
            <td className="text-right">
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEdit(h)}>
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="h-7 w-7 text-loss" onClick={() => onDelete(h.id)}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CashAccountsTable({
  accounts,
  onEdit,
  onDelete,
}: {
  accounts: CashAccount[];
  onEdit: (c: CashAccount) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-muted-foreground uppercase text-left">
        <tr>
          <th className="py-2">Name</th>
          <th>Balance</th>
          <th className="text-right">Actions</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {accounts.map((c) => (
          <tr key={c.id}>
            <td className="py-2.5 font-medium">{c.name}</td>
            <td>${c.balance.toLocaleString()}</td>
            <td className="text-right">
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEdit(c)}>
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="h-7 w-7 text-loss" onClick={() => onDelete(c.id)}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ManualHoldingDialogs({
  addOpen, setAddOpen,
  editOpen, setEditOpen,
  editTarget,
  form, setForm,
  addMutation, editMutation,
}: {
  addOpen: boolean; setAddOpen: (v: boolean) => void;
  editOpen: boolean; setEditOpen: (v: boolean) => void;
  editTarget: ManualHolding | null;
  form: HoldingForm; setForm: (v: HoldingForm) => void;
  addMutation: { mutate: (v: Omit<ManualHolding, "id">) => void; isPending: boolean };
  editMutation: { mutate: (v: { id: string; body: Omit<ManualHolding, "id"> }) => void; isPending: boolean };
}) {
  const body = (): Omit<ManualHolding, "id"> => ({
    symbol: form.symbol,
    qty: parseFloat(form.qty),
    cost_basis: parseFloat(form.cost_basis),
  });

  return (
    <>
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Manual Holding</DialogTitle></DialogHeader>
          <ManualHoldingFormFields value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button disabled={addMutation.isPending} onClick={() => addMutation.mutate(body())}>
              {addMutation.isPending ? "Saving…" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Manual Holding</DialogTitle></DialogHeader>
          <ManualHoldingFormFields value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button
              disabled={editMutation.isPending}
              onClick={() => editTarget && editMutation.mutate({ id: editTarget.id, body: body() })}
            >
              {editMutation.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function CashAccountDialogs({
  addOpen, setAddOpen,
  editOpen, setEditOpen,
  editTarget,
  form, setForm,
  addMutation, editMutation,
}: {
  addOpen: boolean; setAddOpen: (v: boolean) => void;
  editOpen: boolean; setEditOpen: (v: boolean) => void;
  editTarget: CashAccount | null;
  form: CashForm; setForm: (v: CashForm) => void;
  addMutation: { mutate: (v: Omit<CashAccount, "id">) => void; isPending: boolean };
  editMutation: { mutate: (v: { id: string; body: Omit<CashAccount, "id"> }) => void; isPending: boolean };
}) {
  const body = (): Omit<CashAccount, "id"> => ({
    name: form.name,
    balance: parseFloat(form.balance),
  });

  return (
    <>
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Cash Account</DialogTitle></DialogHeader>
          <CashAccountFormFields value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button disabled={addMutation.isPending} onClick={() => addMutation.mutate(body())}>
              {addMutation.isPending ? "Saving…" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Cash Account</DialogTitle></DialogHeader>
          <CashAccountFormFields value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button
              disabled={editMutation.isPending}
              onClick={() => editTarget && editMutation.mutate({ id: editTarget.id, body: body() })}
            >
              {editMutation.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
