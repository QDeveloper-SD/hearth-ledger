import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BarChart3, PieChart as PieIcon, Plus, Pencil, Minus, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ImportDialog } from "@/components/finance/ImportDialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { PageHeader, Panel, Money, CHART_COLORS, ErrorState } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { listDebts, createDebt, updateDebt, deleteDebt, type Debt } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";

type FormState = { name: string; balance: string; rate: string; min_payment: string };
const empty: FormState = { name: "", balance: "", rate: "", min_payment: "" };

function DebtForm({ value, onChange }: { value: FormState; onChange: (v: FormState) => void }) {
  return (
    <div className="space-y-3">
      <div><Label>Account name</Label><Input value={value.name} onChange={(e) => onChange({ ...value, name: e.target.value })} /></div>
      <div><Label>Balance ($)</Label><Input type="number" step="0.01" value={value.balance} onChange={(e) => onChange({ ...value, balance: e.target.value })} /></div>
      <div><Label>Interest rate (%)</Label><Input type="number" step="0.01" value={value.rate} onChange={(e) => onChange({ ...value, rate: e.target.value })} /></div>
      <div><Label>Min. payment ($/mo)</Label><Input type="number" step="0.01" value={value.min_payment} onChange={(e) => onChange({ ...value, min_payment: e.target.value })} /></div>
    </div>
  );
}

export default function DebtPage() {
  const qc = useQueryClient();
  const [view, setView] = useState<"bar" | "pie">("bar");
  const [selected, setSelected] = useState<Debt | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState<FormState>(empty);

  const { data: debts, isLoading, error, refetch } = useQuery({ queryKey: ["debts"], queryFn: listDebts });

  const add = useMutation({
    mutationFn: createDebt,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["debts"] }); setAddOpen(false); setForm(empty); },
  });
  const edit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Omit<Debt, "id">> }) => updateDebt(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["debts"] }); setEditOpen(false); setSelected(null); },
  });
  const remove = useMutation({
    mutationFn: deleteDebt,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["debts"] }); setSelected(null); },
  });

  function openEdit() {
    if (!selected) return;
    setForm({ name: selected.name, balance: String(selected.balance), rate: String(selected.rate), min_payment: String(selected.min_payment) });
    setEditOpen(true);
  }

  const total = debts?.reduce((s, d) => s + d.balance, 0) ?? 0;
  const chartData = debts?.map((d) => ({ name: d.name, balance: d.balance })) ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Debt" subtitle={debts ? `Total outstanding:` : undefined} />
      <div className="flex flex-wrap gap-2">
        <Button variant={view === "bar" ? "default" : "outline"} onClick={() => setView("bar")}><BarChart3 className="h-4 w-4" /> Bar</Button>
        <Button variant={view === "pie" ? "default" : "outline"} onClick={() => setView("pie")}><PieIcon className="h-4 w-4" /> Pie</Button>
        <Button onClick={() => { setForm(empty); setAddOpen(true); }}><Plus className="h-4 w-4" /> Add</Button>
        <Button variant="outline" disabled={!selected} onClick={openEdit}><Pencil className="h-4 w-4" /> Edit</Button>
        <Button variant="outline" disabled={!selected} onClick={() => selected && remove.mutate(selected.id)}><Minus className="h-4 w-4" /> Remove</Button>
        <Button variant="outline" onClick={() => setImportOpen(true)}><Upload className="h-4 w-4" /> Import</Button>
      </div>

      {isLoading && <Skeleton className="h-64 w-full" />}
      {error && <ErrorState error={error} onRetry={() => refetch()} label="Failed to load debts." />}

      {debts && debts.length === 0 && (
        <Panel title="Debt Breakdown">
          <div className="py-12 text-center text-sm text-muted-foreground">
            No debt accounts yet. Click <span className="font-medium">Add</span> to create one — the chart will populate once you have entries.
          </div>
        </Panel>
      )}

      {debts && debts.length > 0 && (
        <>
          <Panel title="Debt Breakdown" action={<span className="text-lg font-semibold"><Money value={-total} signed /></span>}>
            <ResponsiveContainer width="100%" height={320}>
              {view === "bar" ? (
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.93 0.01 250)" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                  <Bar dataKey="balance" fill="oklch(0.6 0.22 25)" radius={[6, 6, 0, 0]} />
                </BarChart>
              ) : (
                <PieChart>
                  <Pie data={chartData} dataKey="balance" nameKey="name" outerRadius={120} label>
                    {chartData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                  <Legend />
                </PieChart>
              )}
            </ResponsiveContainer>
          </Panel>
          <Panel title="Debt Summary">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground uppercase text-left">
                <tr><th className="py-2">Account</th><th>Balance</th><th>Rate</th><th>Min. Payment</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {debts.map((d) => (
                  <tr
                    key={d.id}
                    className={"cursor-pointer hover:bg-brand-soft/40 " + (selected?.id === d.id ? "bg-brand-soft" : "")}
                    onClick={() => setSelected(selected?.id === d.id ? null : d)}
                  >
                    <td className="py-2.5 font-medium">{d.name}</td>
                    <td className="text-loss">−${d.balance.toLocaleString()}</td>
                    <td>{d.rate}%</td>
                    <td>${d.min_payment}/mo</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        </>
      )}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Debt Account</DialogTitle></DialogHeader>
          <DebtForm value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button disabled={add.isPending} onClick={() => add.mutate({ name: form.name, balance: parseFloat(form.balance), rate: parseFloat(form.rate), min_payment: parseFloat(form.min_payment) })}>
              {add.isPending ? "Saving…" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Debt Account</DialogTitle></DialogHeader>
          <DebtForm value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button disabled={edit.isPending} onClick={() => selected && edit.mutate({ id: selected.id, body: { name: form.name, balance: parseFloat(form.balance), rate: parseFloat(form.rate), min_payment: parseFloat(form.min_payment) } })}>
              {edit.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ImportDialog kind="debts" open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}
