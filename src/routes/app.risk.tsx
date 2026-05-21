import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader, Panel, CHART_COLORS } from "@/components/finance/primitives";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getRisk, toggleInsurance } from "@/lib/api";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
} from "recharts";

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" | "bad" }) {
  const color = tone === "good" ? "text-profit" : tone === "bad" ? "text-loss" : "text-foreground";
  return (
    <Panel>
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={"text-2xl font-semibold mt-2 " + color}>{value}</p>
    </Panel>
  );
}

export default function Risk() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["risk"], queryFn: getRisk });
  const toggle = useMutation({
    mutationFn: ({ name, covered }: { name: string; covered: boolean }) => toggleInsurance(name, covered),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["risk"] }),
  });

  if (isLoading) return <div className="space-y-6"><PageHeader title="Risk" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !data) return <div className="space-y-6"><PageHeader title="Risk" /><p className="text-sm text-loss">Failed to load risk data.</p></div>;

  const dtiTone = data.dti < 0.3 ? "good" : data.dti < 0.43 ? "warn" : "bad";
  const emTone = data.emergency_months >= 6 ? "good" : data.emergency_months >= 3 ? "warn" : "bad";

  return (
    <div className="space-y-6">
      <PageHeader title="Risk" subtitle="Health checks across the household balance sheet." />
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Stat label="Net Worth" value={`$${Math.round(data.net_worth / 1000)}K`} tone="good" />
        <Stat label="Debt / Income" value={`${Math.round(data.dti * 100)}%`} tone={dtiTone} />
        <Stat label="Emergency Fund" value={`${data.emergency_months.toFixed(1)} mo`} tone={emTone} />
        <Stat label="Current Ratio" value={data.current_ratio.toFixed(1)} tone={data.current_ratio >= 1.5 ? "good" : "warn"} />
        <Panel>
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Exposure</p>
          <ResponsiveContainer width="100%" height={120}>
            <PieChart>
              <Pie data={data.exposure} dataKey="value" innerRadius={28} outerRadius={50}>
                {data.exposure.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Panel>
        <Panel>
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Insurance</p>
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
      </Panel>
    </div>
  );
}
