import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar, Calculator, Receipt, PiggyBank, Target, Plus, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { PageHeader, Panel, Money, EmptyState, ErrorState } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { listPlanningEvents, createPlanningEvent, updatePlanningEvent, deletePlanningEvent, type PlanningEvent, type PlanningEventInput } from "@/lib/api";

const tools = [
  { id: "calendar", label: "Calendar", icon: Calendar },
  { id: "income", label: "Income Calculator", icon: Calculator },
  { id: "tax", label: "Tax Calculator", icon: Receipt },
  { id: "retire", label: "Retirement", icon: PiggyBank },
  { id: "goals", label: "Goals", icon: Target },
] as const;

export default function Planning() {
  const [active, setActive] = useState<string>("calendar");

  return (
    <div className="space-y-6">
      <PageHeader title="Planning" subtitle="Tools to look forward." />
      <div className="flex flex-wrap gap-2">
        {tools.map((t) => (
          <Button key={t.id} variant={active === t.id ? "default" : "outline"} onClick={() => setActive(t.id)}>
            <t.icon className="h-4 w-4" /> {t.label}
          </Button>
        ))}
      </div>
      <Panel title={tools.find((t) => t.id === active)?.label}>
        {active === "calendar" && <CalendarView />}
        {active === "income" && <IncomeCalc />}
        {active === "tax" && <TaxCalc />}
        {active === "retire" && <Retirement />}
        {active === "goals" && <Goals />}
      </Panel>
    </div>
  );
}

type EventForm = { title: string; date: string; amount: string; notes: string };
const emptyEvent: EventForm = { title: "", date: "", amount: "", notes: "" };

function isValidDate(v: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return false;
  const d = new Date(v + "T00:00:00Z");
  return !isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v;
}

function EventFormFields({ value, onChange }: { value: EventForm; onChange: (v: EventForm) => void }) {
  return (
    <div className="space-y-3">
      <div><Label>Title</Label><Input value={value.title} onChange={(e) => onChange({ ...value, title: e.target.value })} /></div>
      <div><Label>Date</Label><Input type="date" value={value.date} onChange={(e) => onChange({ ...value, date: e.target.value })} /></div>
      <div><Label>Amount ($, optional)</Label><Input type="number" step="0.01" value={value.amount} onChange={(e) => onChange({ ...value, amount: e.target.value })} /></div>
      <div><Label>Notes (optional)</Label><Input value={value.notes} onChange={(e) => onChange({ ...value, notes: e.target.value })} /></div>
    </div>
  );
}

function toBody(f: EventForm): PlanningEventInput {
  const amt = f.amount.trim() === "" ? null : parseFloat(f.amount);
  return {
    title: f.title.trim(),
    date: f.date,
    amount: amt !== null && isFinite(amt) ? amt : null,
    notes: f.notes.trim() === "" ? null : f.notes.trim(),
  };
}

function CalendarView() {
  const qc = useQueryClient();
  const { data: events, isLoading, error, refetch } = useQuery({ queryKey: ["planning-events"], queryFn: listPlanningEvents });
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<PlanningEvent | null>(null);
  const [form, setForm] = useState<EventForm>(emptyEvent);

  const done = () => qc.invalidateQueries({ queryKey: ["planning-events"] });
  const add = useMutation({
    mutationFn: createPlanningEvent,
    onSuccess: () => { done(); setAddOpen(false); setForm(emptyEvent); },
  });
  const edit = useMutation({
    mutationFn: ({ id, body }: { id: string; body: PlanningEventInput }) => updatePlanningEvent(id, body),
    onSuccess: () => { done(); setEditing(null); },
  });
  const remove = useMutation({ mutationFn: deletePlanningEvent, onSuccess: done });

  const valid = form.title.trim() !== "" && isValidDate(form.date);
  const today = new Date().toISOString().slice(0, 10);
  const sorted = [...(events ?? [])].sort((a, b) => a.date.localeCompare(b.date));
  const upcoming = sorted.filter((e) => e.date >= today);
  const past = sorted.filter((e) => e.date < today).reverse();

  function openEdit(ev: PlanningEvent) {
    setForm({ title: ev.title, date: ev.date, amount: ev.amount == null ? "" : String(ev.amount), notes: ev.notes ?? "" });
    setEditing(ev);
  }

  const renderRow = (ev: PlanningEvent, muted: boolean) => (
    <li key={ev.id} className={"flex items-start gap-3 py-3 " + (muted ? "opacity-60" : "")}>
      <div className="w-24 shrink-0 text-sm text-muted-foreground">{ev.date}</div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium truncate">{ev.title}</div>
        {ev.notes && <div className="text-xs text-muted-foreground">{ev.notes}</div>}
      </div>
      {ev.amount != null && <div className="text-sm font-medium"><Money value={ev.amount} /></div>}
      <Button variant="ghost" size="icon" aria-label={`Edit ${ev.title}`} onClick={() => openEdit(ev)}><Pencil className="h-4 w-4" /></Button>
      <Button variant="ghost" size="icon" aria-label={`Delete ${ev.title}`} disabled={remove.isPending} onClick={() => remove.mutate(ev.id)}><Trash2 className="h-4 w-4" /></Button>
    </li>
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => { setForm(emptyEvent); setAddOpen(true); }}><Plus className="h-4 w-4" /> Add event</Button>
      </div>
      {isLoading && <Skeleton className="h-40 w-full" />}
      {error && <ErrorState error={error} onRetry={() => refetch()} label="Failed to load events." />}
      {remove.isError && <ErrorState error={remove.error} label="Failed to delete event." />}
      {events && events.length === 0 && (
        <EmptyState title="No events yet" hint="Add bills, deadlines or milestones you want to plan around." height={160} />
      )}
      {upcoming.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Upcoming</h3>
          <ul className="divide-y divide-border">{upcoming.map((e) => renderRow(e, false))}</ul>
        </div>
      )}
      {past.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Past</h3>
          <ul className="divide-y divide-border">{past.map((e) => renderRow(e, true))}</ul>
        </div>
      )}

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Event</DialogTitle></DialogHeader>
          <EventFormFields value={form} onChange={setForm} />
          {add.isError && <p className="text-sm text-loss">{(add.error as Error).message}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button disabled={!valid || add.isPending} onClick={() => add.mutate(toBody(form))}>
              {add.isPending ? "Saving…" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editing !== null} onOpenChange={(o) => { if (!o) setEditing(null); }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Event</DialogTitle></DialogHeader>
          <EventFormFields value={form} onChange={setForm} />
          {edit.isError && <p className="text-sm text-loss">{(edit.error as Error).message}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            <Button disabled={!valid || edit.isPending} onClick={() => editing && edit.mutate({ id: editing.id, body: toBody(form) })}>
              {edit.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function IncomeCalc() {
  const [hours, setHours] = useState(40);
  const [rate, setRate] = useState(35);
  const weekly = hours * rate;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="space-y-3">
        <div><Label>Hours / week</Label><Input type="number" value={hours} onChange={(e) => setHours(+e.target.value)} /></div>
        <div><Label>Hourly rate ($)</Label><Input type="number" value={rate} onChange={(e) => setRate(+e.target.value)} /></div>
      </div>
      <div className="space-y-2">
        <CalcRow k="Weekly" v={weekly} />
        <CalcRow k="Monthly" v={weekly * 4.33} />
        <CalcRow k="Annual" v={weekly * 52} />
      </div>
    </div>
  );
}

function TaxCalc() {
  const [income, setIncome] = useState(95000);
  const fed = income * 0.22, state = income * 0.06, fica = income * 0.0765;
  const net = income - fed - state - fica;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div><Label>Gross income</Label><Input type="number" value={income} onChange={(e) => setIncome(+e.target.value)} /></div>
      <div className="space-y-2">
        <CalcRow k="Federal (22%)" v={-fed} />
        <CalcRow k="State (6%)" v={-state} />
        <CalcRow k="FICA" v={-fica} />
        <div className="border-t border-border pt-2"><CalcRow k="Net" v={net} bold /></div>
      </div>
    </div>
  );
}

function Retirement() {
  return <p className="text-sm text-muted-foreground">Project retirement balance — currently on track to reach $1.4M by age 65 at 7% return.</p>;
}

function Goals() {
  const goals = [{ n: "Emergency fund", p: 0.86 }, { n: "Vacation 2026", p: 0.42 }, { n: "Down payment", p: 0.18 }];
  return (
    <div className="space-y-4">
      {goals.map((g) => (
        <div key={g.n}>
          <div className="flex justify-between text-sm mb-1"><span>{g.n}</span><span className="text-muted-foreground">{Math.round(g.p * 100)}%</span></div>
          <div className="h-2 rounded-full bg-muted overflow-hidden"><div className="h-full bg-primary" style={{ width: `${g.p * 100}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

function CalcRow({ k, v, bold }: { k: string; v: number; bold?: boolean }) {
  const positive = v >= 0;
  return (
    <div className={"flex justify-between " + (bold ? "text-lg font-semibold" : "text-sm")}>
      <span className="text-muted-foreground">{k}</span>
      <span className={positive ? "text-profit" : "text-loss"}>
        {positive ? "" : "−"}${Math.abs(Math.round(v)).toLocaleString()}
      </span>
    </div>
  );
}
