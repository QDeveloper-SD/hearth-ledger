import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { PageHeader, Panel, Money, CHART_COLORS, EmptyState, ErrorState } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { getDashboard } from "@/lib/api";

function Donut({ data, hint, to, linkLabel }: { data: { name: string; value: number }[]; hint: string; to: string; linkLabel: string }) {
  if (!data.some((d) => d.value > 0)) {
    return (
      <EmptyState
        height={260}
        hint={hint}
        action={<Link to={to} className="text-primary hover:underline">{linkLabel} →</Link>}
      />
    );
  }
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
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["dashboard"], queryFn: getDashboard });

  if (isLoading) return <div className="space-y-6"><PageHeader title="Dashboard" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !data) return <div className="space-y-6"><PageHeader title="Dashboard" /><ErrorState error={error} onRetry={() => refetch()} label="Failed to load dashboard data." /></div>;

  const nwTotal = data.net_worth;
  const invTotal = (data.portfolio_breakdown ?? []).reduce((s, x) => s + x.value, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" subtitle="A snapshot of your household finances." />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Net Worth" action={<span className="text-lg font-semibold"><Money value={nwTotal} /></span>}>
          <Donut data={data.net_worth_breakdown ?? []} hint="Add holdings or cash accounts to see your asset mix." to="/app/portfolio" linkLabel="Go to Portfolio" />
        </Panel>
        <Panel title="Investment Portfolio" action={<span className="text-lg font-semibold"><Money value={invTotal} /></span>}>
          <Donut data={data.portfolio_breakdown ?? []} hint="Add or sync holdings to see your allocation." to="/app/portfolio" linkLabel="Go to Portfolio" />
        </Panel>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Panel title="Income">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Month to date</p>
              <p className="text-2xl font-semibold text-profit"><Money value={data.income_summary.mtd} signed /></p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Year to date</p>
              <p className="text-2xl font-semibold text-profit"><Money value={data.income_summary.ytd} signed /></p>
            </div>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Ledger entries with the category “Income”.</p>
          <div className="mt-4 pt-3 border-t border-border space-y-2 text-sm">
            <p className="text-xs text-muted-foreground uppercase tracking-wide">Per paycheck</p>
            {data.income_summary.sources.length === 0 && (
              <p className="text-muted-foreground">No income sources yet. <Link to="/app/income" className="text-primary hover:underline">Add one →</Link></p>
            )}
            {data.income_summary.sources.map((s, i) => (
              <div key={s.name + i} className="flex justify-between gap-3">
                <span className="text-muted-foreground truncate">{s.name}</span>
                <span className="shrink-0">
                  <Money value={s.amount} />
                  {s.cadence && <span className="text-muted-foreground"> · {s.cadence}</span>}
                </span>
              </div>
            ))}
            {data.income_summary.sources.length > 0 && (
              <div className="flex justify-between gap-3 pt-2 border-t border-border">
                <span className="text-muted-foreground">Expected per month</span>
                <Money value={data.income_summary.expected_monthly} />
              </div>
            )}
          </div>
        </Panel>
        <Panel title="Debt — Outstanding">
          <div className="text-3xl font-semibold text-loss"><Money value={data.debt_summary.total} signed /></div>
          <div className="mt-4 space-y-2 text-sm">
            {data.debt_summary.accounts.length === 0 && (
              <p className="text-muted-foreground">No debt accounts. <Link to="/app/debt" className="text-primary hover:underline">Add one →</Link></p>
            )}
            {data.debt_summary.accounts.map((a, i) => <Row key={a.name + i} label={a.name} value={a.balance} />)}
          </div>
        </Panel>
      </div>
      <Panel title="Ledger — Recent Activity" action={<Link to="/app/ledger" className="text-xs text-primary hover:underline">View all →</Link>}>
        <div className="divide-y divide-border">
          {data.recent_ledger.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">No transactions yet. Add your first entry in the ledger.</p>
          )}
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
