import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BarChart3, PieChart as PieIcon, Plus, Pencil, Minus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { PageHeader, Panel, CHART_COLORS } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { listIncome, createIncome, updateIncome, deleteIncome, type IncomeSource } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";

type FormState = { name: string; amount: string; cadence: string };
const empty: FormState = { name: "", amount: "", cadence: "monthly" };

function IncomeForm({ value, onChange }: { value: FormState; onChange: (v: FormState) => void }) {
  return (
    <div className="space-y-3">
      <div><Label>Source name</Label><Input value={value.name} onChange={(e) => onChange({ ...value, name: e.target.value })} /></div>
      <div><Label>Amount ($)</Label><Input type="number" step="0.01" value={value.amount} onChange={(e) => onChange({ ...value, amount: e.target.value })} /></div>
      <div><Label>Cadence</Label>
        <Input value={value.cadence} onChange={(e) => onChange({ ...value, cadence: e.target.value })} placeholder="monthly / biweekly / weekly" />
      </div>
    </div>
  );
}

export default function Income() {
  const qc = useQueryClient();
  const [view, setView] = useState<"bar" | "pie">("bar");
  const [selected, setSelected] = useState<IncomeSource | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState<FormState>(empty);

  const { data: sources, isLoading, error } = useQuery({ queryKey: ["income"], queryFn: listIncome });

  const add = useMutation({
    mutationFn: createIncome,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["income"] }); setAddOpen(false); setForm(empty); },
  });
  const edit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Omit<IncomeSource, "id">> }) => updateIncome(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["income"] }); setEditOpen(false); setSelected(null); },
  });
  const remove = useMutation({
    mutationFn: deleteIncome,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["income"] }); setSelected(null); },
  });

  function openEdit() {
    if (!selected) return;
    setForm({ name: selected.name, amount: String(selected.amount), cadence: selected.cadence });
    setEditOpen(true);
  }

  const total = sources?.reduce((s, x) => s + x.amount, 0) ?? 0;
  const chartData = sources?.map((s) => ({ name: s.name, amount: s.amount })) ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Income" subtitle={sources ? `Monthly inflow: $${total.toLocaleString()}` : undefined} />
      <div className="flex flex-wrap gap-2">
        <Button variant={view === "bar" ? "default" : "outline"} onClick={() => setView("bar")}><BarChart3 className="h-4 w-4" /> Bar</Button>
        <Button variant={view === "pie" ? "default" : "outline"} onClick={() => setView("pie")}><PieIcon className="h-4 w-4" /> Pie</Button>
        <Button onClick={() => { setForm(empty); setAddOpen(true); }}><Plus className="h-4 w-4" /> Add</Button>
        <Button variant="outline" disabled={!selected} onClick={openEdit}><Pencil className="h-4 w-4" /> Edit</Button>
        <Button variant="outline" disabled={!selected} onClick={() => selected && remove.mutate(selected.id)}><Minus className="h-4 w-4" /> Remove</Button>
      </div>

      {isLoading && <Skeleton className="h-64 w-full" />}
      {error && <p className="text-sm text-loss">Failed to load income sources.</p>}

      {sources && sources.length === 0 && (
        <Panel title="Income Breakdown">
          <div className="py-12 text-center text-sm text-muted-foreground">
            No income sources yet. Click <span className="font-medium">Add</span> to create one — the chart will populate once you have entries.
          </div>
        </Panel>
      )}

      {sources && sources.length > 0 && (
        <>
          <Panel title="Income Breakdown">
            <ResponsiveContainer width="100%" height={320}>
              {view === "bar" ? (
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.93 0.01 250)" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                  <Bar dataKey="amount" fill="oklch(0.62 0.18 145)" radius={[6, 6, 0, 0]} />
                </BarChart>
              ) : (
                <PieChart>
                  <Pie data={chartData} dataKey="amount" nameKey="name" outerRadius={120} label>
                    {chartData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                  <Legend />
                </PieChart>
              )}
            </ResponsiveContainer>
          </Panel>
          <Panel title="Income Summary">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground uppercase text-left">
                <tr><th className="py-2">Source</th><th>Cadence</th><th>Amount</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sources.map((s) => (
                  <tr
                    key={s.id}
                    className={"cursor-pointer hover:bg-brand-soft/40 " + (selected?.id === s.id ? "bg-brand-soft" : "")}
                    onClick={() => setSelected(selected?.id === s.id ? null : s)}
                  >
                    <td className="py-2.5 font-medium">{s.name}</td>
                    <td className="text-muted-foreground">{s.cadence}</td>
                    <td className="text-profit">+${s.amount.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        </>
      )}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Income Source</DialogTitle></DialogHeader>
          <IncomeForm value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button disabled={add.isPending} onClick={() => add.mutate({ name: form.name, amount: parseFloat(form.amount), cadence: form.cadence })}>
              {add.isPending ? "Saving…" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Income Source</DialogTitle></DialogHeader>
          <IncomeForm value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button disabled={edit.isPending} onClick={() => selected && edit.mutate({ id: selected.id, body: { name: form.name, amount: parseFloat(form.amount), cadence: form.cadence } })}>
              {edit.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
