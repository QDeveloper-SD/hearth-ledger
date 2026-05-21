import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Minus, Pencil, FileBarChart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { PageHeader, Panel, Money } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { listLedger, createLedger, updateLedger, deleteLedger, type LedgerEntry } from "@/lib/api";

type FormState = { date: string; desc: string; category: string; amount: string };
const empty: FormState = { date: "", desc: "", category: "", amount: "" };

function EntryForm({ value, onChange }: { value: FormState; onChange: (v: FormState) => void }) {
  return (
    <div className="space-y-3">
      <div><Label>Date</Label><Input type="date" value={value.date} onChange={(e) => onChange({ ...value, date: e.target.value })} /></div>
      <div><Label>Description</Label><Input value={value.desc} onChange={(e) => onChange({ ...value, desc: e.target.value })} /></div>
      <div><Label>Category</Label><Input value={value.category} onChange={(e) => onChange({ ...value, category: e.target.value })} /></div>
      <div><Label>Amount (negative for expenses)</Label><Input type="number" step="0.01" value={value.amount} onChange={(e) => onChange({ ...value, amount: e.target.value })} /></div>
    </div>
  );
}

export default function Ledger() {
  const qc = useQueryClient();
  const { data: entries, isLoading, error } = useQuery({ queryKey: ["ledger"], queryFn: listLedger });
  const [selected, setSelected] = useState<LedgerEntry | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState<FormState>(empty);

  const add = useMutation({
    mutationFn: createLedger,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ledger"] }); setAddOpen(false); setForm(empty); },
  });
  const edit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Omit<LedgerEntry, "id">> }) => updateLedger(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ledger"] }); setEditOpen(false); setSelected(null); },
  });
  const remove = useMutation({
    mutationFn: deleteLedger,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ledger"] }); setSelected(null); },
  });

  function openAdd() { setForm(empty); setAddOpen(true); }
  function openEdit() {
    if (!selected) return;
    setForm({ date: selected.date, desc: selected.desc, category: selected.category, amount: String(selected.amount) });
    setEditOpen(true);
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Ledger" subtitle="Every transaction across the household." />
      <div className="flex flex-wrap gap-2">
        <Button onClick={openAdd}><Plus className="h-4 w-4" /> Add</Button>
        <Button variant="outline" disabled={!selected} onClick={() => selected && remove.mutate(selected.id)}><Minus className="h-4 w-4" /> Remove</Button>
        <Button variant="outline" disabled={!selected} onClick={openEdit}><Pencil className="h-4 w-4" /> Edit</Button>
        <Button variant="outline"><FileBarChart className="h-4 w-4" /> View Summary</Button>
      </div>
      <p className="text-xs text-muted-foreground -mt-3">
        {selected ? `Selected: ${selected.desc}` : "Click a row to select it, then use Edit or Remove."}
      </p>

      <Panel title="Ledger History">
        {isLoading && <Skeleton className="h-48 w-full" />}
        {error && <p className="text-sm text-loss">Failed to load ledger.</p>}
        {entries && (
          <div className="max-h-[560px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-background">
                <tr className="text-left text-xs text-muted-foreground uppercase">
                  <th className="py-2 pr-4">Date</th>
                  <th className="py-2 pr-4">Description</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entries.map((e) => (
                  <tr
                    key={e.id}
                    className={"hover:bg-brand-soft/40 cursor-pointer " + (selected?.id === e.id ? "bg-brand-soft" : "")}
                    onClick={() => setSelected(selected?.id === e.id ? null : e)}
                  >
                    <td className="py-2.5 pr-4 text-muted-foreground">{e.date}</td>
                    <td className="py-2.5 pr-4">{e.desc}</td>
                    <td className="py-2.5 pr-4 text-muted-foreground">{e.category}</td>
                    <td className="py-2.5 text-right font-medium"><Money value={e.amount} signed /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Entry</DialogTitle></DialogHeader>
          <EntryForm value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button
              disabled={add.isPending}
              onClick={() => add.mutate({ date: form.date, desc: form.desc, category: form.category, amount: parseFloat(form.amount) })}
            >
              {add.isPending ? "Saving…" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Entry</DialogTitle></DialogHeader>
          <EntryForm value={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button
              disabled={edit.isPending}
              onClick={() => selected && edit.mutate({ id: selected.id, body: { date: form.date, desc: form.desc, category: form.category, amount: parseFloat(form.amount) } })}
            >
              {edit.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
