import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader, Panel, CHART_COLORS, EmptyState, ErrorState } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getRisk, toggleInsurance } from "@/lib/api";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
} from "recharts";

function Stat({ label, value, tone, hint }: { label: string; value: string; tone?: "good" | "warn" | "bad"; hint?: string }) {
  const color = tone === "good" ? "text-profit" : tone === "bad" ? "text-loss" : "text-foreground";
  return (
    <Panel>
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={"text-2xl font-semibold mt-2 " + color}>{value}</p>
      {hint && <p className="text-[11px] leading-snug text-muted-foreground mt-1">{hint}</p>}
    </Panel>
  );
}

export default function Risk() {
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["risk"], queryFn: getRisk });
  const toggle = useMutation({
    mutationFn: ({ name, covered }: { name: string; covered: boolean }) => toggleInsurance(name, covered),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["risk"] }),
  });

  if (isLoading) return <div className="space-y-6"><PageHeader title="Risk" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !data) return <div className="space-y-6"><PageHeader title="Risk" /><ErrorState error={error} onRetry={() => refetch()} label="Failed to load risk data." /></div>;

  const { dti, emergency_months: em, current_ratio: cr } = data;
  const dtiTone = dti == null ? undefined : dti < 0.3 ? "good" : dti < 0.43 ? "warn" : "bad";
  const emTone = em == null ? undefined : em >= 6 ? "good" : em >= 3 ? "warn" : "bad";

  return (
    <div className="space-y-6">
      <PageHeader title="Risk" subtitle="Health checks across the household balance sheet." />
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Stat label="Net Worth" value={`$${Math.round(data.net_worth / 1000)}K`} tone={data.net_worth >= 0 ? "good" : "bad"} />
        <Stat
          label="Debt / Income"
          value={dti == null ? "—" : `${Math.round(dti * 100)}%`}
          tone={dtiTone}
          hint={dti == null ? "Add an income source to calculate." : "Monthly debt payments ÷ monthly income."}
        />
        <Stat
          label="Emergency Fund"
          value={em == null ? "—" : `${em.toFixed(1)} mo`}
          tone={emTone}
          hint={em == null ? "Needs ledger spending from the last 90 days." : "Cash accounts ÷ average monthly spending (last 90 days)."}
        />
        <Stat
          label="Current Ratio"
          value={cr == null ? "—" : cr.toFixed(1)}
          tone={cr == null ? undefined : cr >= 1.5 ? "good" : cr >= 1.0 ? "warn" : "bad"}
          hint={cr == null ? "No debts recorded." : "Liquid assets ÷ debt due in the next 12 months."}
        />
        <Panel>
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Exposure</p>
          {!data.exposure.some((e) => e.value > 0) ? (
            <EmptyState height={120} title="No holdings" hint="Add holdings to see exposure." />
          ) : (
          <ResponsiveContainer width="100%" height={120}>
            <PieChart>
              <Pie data={data.exposure} dataKey="value" innerRadius={28} outerRadius={50}>
                {data.exposure.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          )}
        </Panel>
        <Panel>
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Insurance</p>
          {data.insurance.length === 0 && <p className="text-xs text-muted-foreground">No insurance categories.</p>}
          <ul className="text-xs space-y-2">
            {data.insurance.map((item) => (
              <li key={item.name} className="flex items-center justify-between">
                <span>{item.name}</span>
                <Switch
                  checked={item.covered}
                  onCheckedChange={(checked) => toggle.mutate({ name: item.name, covered: checked })}
                  disabled={toggle.isPending}
                />
              </li>
            ))}
          </ul>
        </Panel>
      </div>
      <Panel title="Expenditure Over Time">
        {data.spend_series.length === 0 ? (
          <EmptyState height={340} hint="Spending appears here once you record expenses (negative amounts) in the ledger." />
        ) : (
        <ResponsiveContainer width="100%" height={340}>
          <AreaChart data={data.spend_series}>
            <defs>
              <linearGradient id="sp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="oklch(0.72 0.12 230)" stopOpacity={0.5} />
                <stop offset="100%" stopColor="oklch(0.72 0.12 230)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.93 0.01 250)" />
            <XAxis dataKey="m" />
            <YAxis />
            <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
            <Area type="monotone" dataKey="spend" stroke="oklch(0.72 0.12 230)" fill="url(#sp)" strokeWidth={2.5} />
          </AreaChart>
        </ResponsiveContainer>
        )}
      </Panel>
    </div>
  );
}
