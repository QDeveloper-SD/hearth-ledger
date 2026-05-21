import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar, Calculator, Receipt, PiggyBank, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader, Panel } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { listPlanningEvents } from "@/lib/api";

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

function CalendarView() {
  const { data: events, isLoading } = useQuery({ queryKey: ["planning-events"], queryFn: listPlanningEvents });
  const days = Array.from({ length: 35 }, (_, i) => i - 3);

  const eventMap: Record<number, string> = {};
  if (events) {
    events.forEach((ev) => {
      const day = parseInt(ev.date.split("-")[2], 10);
      if (!isNaN(day)) eventMap[day] = ev.title;
    });
  }

  return (
    <div>
      {isLoading && <Skeleton className="h-40 w-full" />}
      <div className="grid grid-cols-7 gap-1 text-xs text-muted-foreground mb-2">
        {["S","M","T","W","T","F","S"].map((d, i) => <div key={i} className="text-center py-1">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((d) => (
          <div key={d} className={"aspect-square rounded-md border border-border p-1.5 text-xs " + (d < 1 || d > 31 ? "opacity-30" : "")}>
            <div className="font-medium">{d > 0 && d <= 31 ? d : ""}</div>
            {eventMap[d] && <div className="mt-1 text-[10px] px-1 py-0.5 rounded bg-brand-soft text-foreground truncate">{eventMap[d]}</div>}
          </div>
        ))}
      </div>
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
