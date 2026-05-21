import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { PageHeader, Panel, Money, CHART_COLORS } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { getDashboard } from "@/lib/api";

function Donut({ data }: { data: { name: string; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" innerRadius={55} outerRadius={95} paddingAngle={2}>
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
        <Legend verticalAlign="bottom" height={28} iconSize={8} />
      </PieChart>
    </ResponsiveContainer>
  );
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <Money value={value} signed />
    </div>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: getDashboard });

  if (isLoading) return <div className="space-y-6"><PageHeader title="Dashboard" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !data) return <div className="space-y-6"><PageHeader title="Dashboard" /><p className="text-sm text-loss">Failed to load dashboard data.</p></div>;

  const nwTotal = data.net_worth;
  const invTotal = data.portfolio_breakdown.reduce((s, x) => s + x.value, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" subtitle="A snapshot of your household finances." />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Net Worth" action={<span className="text-lg font-semibold"><Money value={nwTotal} /></span>}>
          <Donut data={data.net_worth_breakdown} />
        </Panel>
        <Panel title="Investment Portfolio" action={<span className="text-lg font-semibold"><Money value={invTotal} /></span>}>
          <Donut data={data.portfolio_breakdown} />
        </Panel>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Panel title="Income — This Month">
          <div className="text-3xl font-semibold text-profit"><Money value={data.income_summary.total} signed /></div>
          <div className="mt-4 space-y-2 text-sm">
            {data.income_summary.sources.map((s) => <Row key={s.name} label={s.name} value={s.amount} />)}
          </div>
        </Panel>
        <Panel title="Debt — Outstanding">
          <div className="text-3xl font-semibold text-loss"><Money value={data.debt_summary.total} signed /></div>
          <div className="mt-4 space-y-2 text-sm">
            {data.debt_summary.accounts.map((a) => <Row key={a.name} label={a.name} value={a.balance} />)}
          </div>
        </Panel>
      </div>
      <Panel title="Ledger — Recent Activity" action={<Link to="/app/ledger" className="text-xs text-primary hover:underline">View all →</Link>}>
        <div className="divide-y divide-border">
          {data.recent_ledger.map((l) => (
            <div key={l.id} className="grid grid-cols-12 py-2.5 text-sm items-center">
              <div className="col-span-2 text-muted-foreground">{l.date}</div>
              <div className="col-span-6 truncate">{l.desc}</div>
              <div className="col-span-2 text-muted-foreground">{l.category}</div>
              <div className="col-span-2 text-right font-medium"><Money value={l.amount} signed /></div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
