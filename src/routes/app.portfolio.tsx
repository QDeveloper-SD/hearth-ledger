import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { LineChart as LineIcon, PieChart as PieIcon, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader, Panel, Money, EmptyState, ErrorState, CHART_COLORS } from "@/components/finance/primitives";
import {
  HoldingsSection, usd, num, optNum, optStr,
  type ColumnDef, type FieldDef, type FormValues,
} from "@/components/finance/HoldingsSection";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getPortfolio, syncPortfolio, syncIbkr,
  createManualHolding, updateManualHolding, deleteManualHolding,
  createCashAccount, updateCashAccount, deleteCashAccount,
  createRealEstate, updateRealEstate, deleteRealEstate,
  createBusiness, updateBusiness, deleteBusiness,
  createFixedIncome, updateFixedIncome, deleteFixedIncome,
  type ManualHolding, type CashAccount, type RealEstate, type Business, type FixedIncome,
  type BrokerAccount, type PortfolioTotals,
} from "@/lib/api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";

function fmtDate(d: string): string {
  const dt = new Date(d + "T00:00:00");
  return isNaN(dt.getTime()) ? d : dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
function fmtAxis(v: number): string {
  return Math.abs(v) >= 1000 ? `$${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}k` : `$${v}`;
}

// ---------------------------------------------------------------------------
// Section configs (column + field definitions)
// ---------------------------------------------------------------------------

const dash = <span className="text-muted-foreground">—</span>;
const holdingValue = (h: ManualHolding) => h.current_value ?? h.cost_basis;

function positionColumns(withBroker: boolean): ColumnDef<ManualHolding>[] {
  return [
    { header: "Symbol", cell: (h) => <span className="font-medium">{h.symbol}</span> },
    ...(withBroker ? [{ header: "Broker", cell: (h: ManualHolding) => h.broker ?? dash }] : []),
    { header: "Qty", align: "right" as const, cell: (h) => h.qty },
    { header: "Cost basis", align: "right" as const, cell: (h) => usd(h.cost_basis) },
    { header: "Value", align: "right" as const, cell: (h) => usd(holdingValue(h)) },
    {
      header: "Gain / loss", align: "right" as const,
      cell: (h) => {
        if (h.current_value == null) return dash;
        const g = h.current_value - h.cost_basis;
        const pct = h.cost_basis > 0 ? ` (${g >= 0 ? "+" : "−"}${Math.abs((g / h.cost_basis) * 100).toFixed(1)}%)` : "";
        return <span><Money value={g} signed />{pct}</span>;
      },
    },
  ];
}

function positionFields(withBroker: boolean): FieldDef[] {
  return [
    { key: "symbol", label: "Symbol", type: "text", required: true, placeholder: "e.g. VTI, BTC" },
    ...(withBroker ? [{ key: "broker", label: "Broker", type: "text" as const, required: true, placeholder: "e.g. Fidelity" }] : []),
    { key: "qty", label: "Quantity", type: "number", required: true, min: 0 },
    { key: "cost_basis", label: "Cost basis ($)", type: "number", required: true, min: 0, hint: "Total paid for the position, not per share." },
    { key: "current_value", label: "Current value ($)", type: "number", min: 0, hint: "Optional. Leave blank to use cost basis." },
  ];
}

const positionToForm = (r?: ManualHolding): FormValues => ({
  symbol: r?.symbol ?? "", broker: r?.broker ?? "", qty: r ? String(r.qty) : "",
  cost_basis: r ? String(r.cost_basis) : "", current_value: r?.current_value != null ? String(r.current_value) : "",
});
const positionToBody = (account: BrokerAccount) => (f: FormValues): Omit<ManualHolding, "id"> => ({
  symbol: f.symbol.trim(), qty: num(f.qty), cost_basis: num(f.cost_basis),
  current_value: optNum(f.current_value), account, broker: account === "other" ? f.broker.trim() : null,
});

const cashColumns: ColumnDef<CashAccount>[] = [
  { header: "Account", cell: (c) => <span className="font-medium">{c.name}</span> },
  { header: "Balance", align: "right", cell: (c) => usd(c.balance) },
];
const cashFields: FieldDef[] = [
  { key: "name", label: "Account name", type: "text", required: true, placeholder: "e.g. Chase Checking" },
  { key: "balance", label: "Balance ($)", type: "number", required: true, min: 0 },
];

const reColumns: ColumnDef<RealEstate>[] = [
  { header: "Property", cell: (r) => <div><div className="font-medium">{r.name}</div>{r.address && <div className="text-xs text-muted-foreground">{r.address}</div>}</div> },
  { header: "Purchase price", align: "right", cell: (r) => (r.purchase_price != null ? usd(r.purchase_price) : dash) },
  { header: "Current value", align: "right", cell: (r) => usd(r.current_value) },
  {
    header: "Gain / loss", align: "right",
    cell: (r) => (r.purchase_price != null ? <Money value={r.current_value - r.purchase_price} signed /> : dash),
  },
];
const reFields: FieldDef[] = [
  { key: "name", label: "Name", type: "text", required: true, placeholder: "e.g. Primary home" },
  { key: "address", label: "Address", type: "text" },
  { key: "current_value", label: "Current value ($)", type: "number", required: true, min: 0 },
  { key: "purchase_price", label: "Purchase price ($)", type: "number", min: 0 },
  { key: "notes", label: "Notes", type: "text" },
];

const stake = (b: Business) => (b.valuation * b.ownership_pct) / 100;
const bizColumns: ColumnDef<Business>[] = [
  { header: "Business", cell: (b) => <div><div className="font-medium">{b.name}</div>{b.notes && <div className="text-xs text-muted-foreground">{b.notes}</div>}</div> },
  { header: "Valuation", align: "right", cell: (b) => usd(b.valuation) },
  { header: "Ownership", align: "right", cell: (b) => `${b.ownership_pct}%` },
  { header: "Your stake", align: "right", cell: (b) => usd(stake(b)) },
];
const bizFields: FieldDef[] = [
  { key: "name", label: "Name", type: "text", required: true },
  { key: "valuation", label: "Valuation of whole business ($)", type: "number", required: true, min: 0 },
  { key: "ownership_pct", label: "Ownership (%)", type: "number", required: true, min: 0, max: 100, hint: "Your stake = valuation × ownership." },
  { key: "notes", label: "Notes", type: "text" },
];

const fiValue = (f: FixedIncome) => f.current_value ?? f.face_value;
const fiColumns: ColumnDef<FixedIncome>[] = [
  { header: "Security", cell: (f) => <div><div className="font-medium">{f.name}</div>{f.issuer && <div className="text-xs text-muted-foreground">{f.issuer}</div>}</div> },
  { header: "Face value", align: "right", cell: (f) => usd(f.face_value) },
  { header: "Coupon", align: "right", cell: (f) => (f.coupon_rate != null ? `${f.coupon_rate}%` : dash) },
  { header: "Maturity", cell: (f) => f.maturity_date ?? dash },
  { header: "Current value", align: "right", cell: (f) => usd(fiValue(f)) },
];
const fiFields: FieldDef[] = [
  { key: "name", label: "Name", type: "text", required: true, placeholder: "e.g. 10-yr Treasury" },
  { key: "issuer", label: "Issuer", type: "text" },
  { key: "face_value", label: "Face value ($)", type: "number", required: true, min: 0 },
  { key: "coupon_rate", label: "Coupon rate (%)", type: "number", min: 0 },
  { key: "maturity_date", label: "Maturity date", type: "date" },
  { key: "current_value", label: "Current value ($)", type: "number", min: 0, hint: "Optional. Defaults to face value." },
];

const s = (v: unknown) => (v == null ? "" : String(v));

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const SUMMARY: { key: keyof PortfolioTotals; label: string; anchor: string }[] = [
  { key: "public", label: "Public.com", anchor: "sec-public" },
  { key: "manual", label: "Other investments", anchor: "sec-manual" },
  { key: "ibkr", label: "IBKR", anchor: "sec-ibkr" },
  { key: "other_brokers", label: "Other brokers", anchor: "sec-other" },
  { key: "real_estate", label: "Real estate", anchor: "sec-real-estate" },
  { key: "businesses", label: "Businesses", anchor: "sec-businesses" },
  { key: "fixed_income", label: "Fixed income", anchor: "sec-fixed-income" },
  { key: "cash", label: "Cash", anchor: "sec-cash" },
];

export default function Portfolio() {
  const qc = useQueryClient();
  const [view, setView] = useState<"line" | "pie">("line");
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["portfolio"], queryFn: getPortfolio });
  const sync = useMutation({
    mutationFn: syncPortfolio,
    onSuccess: () => { for (const k of ["portfolio", "dashboard", "risk"]) qc.invalidateQueries({ queryKey: [k] }); },
  });

  const ibkrSync = useMutation({
    mutationFn: syncIbkr,
    onSuccess: () => { for (const k of ["portfolio", "dashboard", "risk"]) qc.invalidateQueries({ queryKey: [k] }); },
  });

  if (isLoading) return <div className="space-y-6"><PageHeader title="Portfolio" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !data) {
    return (
      <div className="space-y-6">
        <PageHeader title="Portfolio" />
        <ErrorState error={error} onRetry={() => refetch()} label="Failed to load portfolio data." />
      </div>
    );
  }

  const t = data.totals;
  const positions = data.manual_holdings ?? [];
  const ibkr = data.ibkr ?? { configured: false, fetched_at: null, cash: null, holdings: [] };
  const ibkrManual = positions.filter((h) => h.account === "ibkr");
  const ibkrSynced = t.ibkr - ibkrManual.reduce((sum, h) => sum + holdingValue(h), 0);
  const ibkrEmpty = ibkr.holdings.length === 0 && ibkr.cash == null;
  const byAccount = (a: BrokerAccount) => positions.filter((h) => (h.account ?? "manual") === a);
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="space-y-6">
      <PageHeader title="Portfolio" subtitle="Investments, property, businesses and cash in one place." />

      <div className="flex gap-2">
        <Button variant={view === "line" ? "default" : "outline"} onClick={() => setView("line")}>
          <LineIcon className="h-4 w-4" /> Line
        </Button>
        <Button variant={view === "pie" ? "default" : "outline"} onClick={() => setView("pie")}>
          <PieIcon className="h-4 w-4" /> Pie
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Panel title={view === "line" ? "Investable Value Over Time" : "Allocation by Holding"}>
            {(view === "line" ? data.series.length < 2 : data.allocation.length === 0) ? (
              <EmptyState
                height={300}
                title={view === "line" ? "Performance history builds automatically" : "No holdings yet"}
                hint={view === "line" ? "Check back after a few days. Real estate and businesses are excluded." : "Add positions below to see allocation."}
              />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                {view === "line" ? (
                  <LineChart data={data.series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.93 0.01 250)" />
                    <XAxis dataKey="date" tickFormatter={fmtDate} minTickGap={32} />
                    <YAxis domain={["auto", "auto"]} tickFormatter={fmtAxis} width={64} />
                    <Tooltip labelFormatter={fmtDate} formatter={(v: number) => usd(v)} />
                    <Line type="monotone" dataKey="value" stroke="oklch(0.72 0.12 230)" strokeWidth={2.5} dot={false} />
                  </LineChart>
                ) : (
                  <PieChart>
                    <Pie data={data.allocation} dataKey="value" outerRadius={110} label>
                      {data.allocation.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v: number) => usd(v)} />
                    <Legend />
                  </PieChart>
                )}
              </ResponsiveContainer>
            )}
          </Panel>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-1 gap-6">
          <Panel title="Sharpe Ratio">
            <div className="text-3xl font-semibold">{data.sharpe_ratio != null ? data.sharpe_ratio.toFixed(2) : "—"}</div>
            <p className="text-xs text-muted-foreground mt-2">{data.sharpe_ratio != null ? "Risk-adjusted return" : "Needs a few more days of history"}</p>
          </Panel>
          <Panel title="Volatility">
            <div className="text-3xl font-semibold">{data.volatility != null ? `${(data.volatility * 100).toFixed(1)}%` : "—"}</div>
            <p className="text-xs text-muted-foreground mt-2">{data.volatility != null ? "Annualized std dev" : "Needs a few more days of history"}</p>
          </Panel>
        </div>
      </div>

      <Panel title="Total Assets">
        <div className="text-3xl font-semibold tabular-nums">{usd(t.total)}</div>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {SUMMARY.map((x) => (
            <button
              key={x.key}
              type="button"
              onClick={() => scrollTo(x.anchor)}
              className="rounded-md border border-border px-3 py-2 text-left hover:bg-muted transition-colors"
            >
              <div className="text-xs text-muted-foreground">{x.label}</div>
              <div className="text-sm font-semibold tabular-nums">{usd(t[x.key])}</div>
            </button>
          ))}
        </div>
      </Panel>

      {/* 1. Public.com (read-only, synced) */}
      <div id="sec-public" className="scroll-mt-4">
        <Panel
          title="Public.com"
          action={
            <div className="flex items-center gap-3">
              <span className="text-sm font-semibold tabular-nums">{usd(t.public)}</span>
              <Button size="sm" variant="outline" onClick={() => sync.mutate()} disabled={sync.isPending}>
                <RefreshCw className={"h-3.5 w-3.5 mr-1 " + (sync.isPending ? "animate-spin" : "")} /> Sync
              </Button>
            </div>
          }
        >
          {data.holdings.length === 0 ? (
            <EmptyState
              height={110}
              title={data.not_configured ? "Public.com is not connected" : "No synced holdings yet"}
              hint={data.not_configured ? "Add your API secret in Settings to sync live holdings." : "Press Sync to pull your latest positions."}
              action={data.not_configured ? <Button size="sm" variant="outline" asChild><Link to="/app/settings">Go to Settings</Link></Button> : undefined}
            />
          ) : (
            <div className="max-h-[360px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-background text-xs text-muted-foreground uppercase text-left">
                  <tr><th className="py-2 font-medium">Symbol</th><th className="text-right font-medium">Qty</th><th className="text-right font-medium">Price</th><th className="text-right font-medium">Value</th><th className="text-right font-medium">Day</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.holdings.map((h) => (
                    <tr key={h.symbol}>
                      <td className="py-2.5">
                        <div className="font-medium">{h.symbol}</div>
                        {h.name && <div className="text-xs text-muted-foreground">{h.name}</div>}
                      </td>
                      <td className="text-right tabular-nums">{h.qty}</td>
                      <td className="text-right tabular-nums">{h.price != null ? usd(h.price) : "—"}</td>
                      <td className="text-right tabular-nums">{h.current_value != null ? usd(h.current_value) : "—"}</td>
                      <td className={"text-right font-medium " + ((h.day_change ?? 0) >= 0 ? "text-profit" : "text-loss")}>
                        {h.day_change != null ? `${h.day_change >= 0 ? "+" : ""}${h.day_change}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      {/* 2-4. Manually entered brokerage positions (one collection, filtered by account) */}
      <HoldingsSection<ManualHolding>
        anchor="sec-manual" title="Investments not on Public" itemLabel="holding"
        subtotal={t.manual} rows={byAccount("manual")} columns={positionColumns(false)} fields={positionFields(false)}
        emptyTitle="No other investments" emptyHint="Crypto, private holdings or anything not held at Public.com."
        toForm={positionToForm} toBody={positionToBody("manual")} rowLabel={(h) => h.symbol}
        onCreate={createManualHolding} onUpdate={updateManualHolding} onDelete={deleteManualHolding}
      />
      {/* IBKR (read-only, synced through the Flex Web Service) */}
      <div id="sec-ibkr" className="scroll-mt-4">
        <Panel
          title="IBKR"
          action={
            <div className="flex items-center gap-3">
              <span className="text-sm font-semibold tabular-nums">{usd(ibkrSynced)}</span>
              <Button size="sm" variant="outline" onClick={() => ibkrSync.mutate()} disabled={ibkrSync.isPending || !ibkr.configured}>
                <RefreshCw className={"h-3.5 w-3.5 mr-1 " + (ibkrSync.isPending ? "animate-spin" : "")} /> {ibkrSync.isPending ? "Syncing…" : "Sync"}
              </Button>
            </div>
          }
        >
          {ibkrSync.isError && (
            <p className="text-xs text-loss mb-2" role="alert">{ibkrSync.error instanceof Error ? ibkrSync.error.message : "IBKR sync failed."}</p>
          )}
          {ibkrEmpty ? (
            <EmptyState
              height={110}
              title={ibkr.configured ? "No synced positions yet" : "Interactive Brokers is not connected"}
              hint={ibkr.configured ? "Press Sync to pull your positions. IBKR can take up to a minute to prepare the report." : "Add your read-only Flex token and Query ID in Settings."}
              action={ibkr.configured ? undefined : <Button size="sm" variant="outline" asChild><Link to="/app/settings">Go to Settings</Link></Button>}
            />
          ) : (
            <div className="max-h-[360px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-background text-xs text-muted-foreground uppercase text-left">
                  <tr><th className="py-2 font-medium">Symbol</th><th className="text-right font-medium">Qty</th><th className="text-right font-medium">Cost basis</th><th className="text-right font-medium">Value</th><th className="text-right font-medium">Gain / loss</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {ibkr.holdings.map((h) => (
                    <tr key={h.symbol + (h.currency ?? "")}>
                      <td className="py-2.5">
                        <div className="font-medium">{h.symbol}</div>
                        {h.name && <div className="text-xs text-muted-foreground">{h.name}</div>}
                      </td>
                      <td className="text-right tabular-nums">{h.qty}</td>
                      <td className="text-right tabular-nums">{h.cost_basis_total != null ? usd(h.cost_basis_total) : "—"}</td>
                      <td className="text-right tabular-nums">{h.current_value != null ? usd(h.current_value) : "—"}</td>
                      <td className="text-right tabular-nums">{h.gain_value != null ? <Money value={h.gain_value} signed /> : "—"}</td>
                    </tr>
                  ))}
                  {ibkr.cash != null && (
                    <tr>
                      <td className="py-2.5 font-medium">Cash</td><td /><td />
                      <td className="text-right tabular-nums">{usd(ibkr.cash)}</td><td />
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
          {ibkr.fetched_at && (
            <p className="text-xs text-muted-foreground mt-2">Last synced {new Date(ibkr.fetched_at).toLocaleString()}. Read-only: Hearth cannot trade in this account.</p>
          )}
        </Panel>
      </div>
      {/* Positions typed in by hand before the IBKR connection existed stay editable. */}
      {ibkrManual.length > 0 && (
        <HoldingsSection<ManualHolding>
          anchor="sec-ibkr-manual" title="IBKR — entered manually" note="Remove these once synced, or they count twice" itemLabel="position"
          subtotal={t.ibkr - ibkrSynced} rows={ibkrManual} columns={positionColumns(false)} fields={positionFields(false)}
          emptyTitle="No IBKR positions" emptyHint="Add positions held at Interactive Brokers."
          toForm={positionToForm} toBody={positionToBody("ibkr")} rowLabel={(h) => h.symbol}
          onCreate={createManualHolding} onUpdate={updateManualHolding} onDelete={deleteManualHolding}
        />
      )}
      <HoldingsSection<ManualHolding>
        anchor="sec-other" title="Other brokers" itemLabel="position"
        subtotal={t.other_brokers} rows={byAccount("other")} columns={positionColumns(true)} fields={positionFields(true)}
        emptyTitle="No positions at other brokers" emptyHint="Add positions held at Fidelity, Schwab or any other broker."
        toForm={positionToForm} toBody={positionToBody("other")} rowLabel={(h) => h.symbol}
        onCreate={createManualHolding} onUpdate={updateManualHolding} onDelete={deleteManualHolding}
      />

      <HoldingsSection<RealEstate>
        anchor="sec-real-estate" title="Real estate" itemLabel="property"
        subtotal={t.real_estate} rows={data.real_estate ?? []} columns={reColumns} fields={reFields}
        emptyTitle="No properties" emptyHint="Add your home, rentals or land."
        toForm={(r) => ({ name: s(r?.name), address: s(r?.address), current_value: s(r?.current_value), purchase_price: s(r?.purchase_price), notes: s(r?.notes) })}
        toBody={(f) => ({ name: f.name.trim(), address: optStr(f.address), current_value: num(f.current_value), purchase_price: optNum(f.purchase_price), notes: optStr(f.notes) })}
        rowLabel={(r) => r.name}
        onCreate={createRealEstate} onUpdate={updateRealEstate} onDelete={deleteRealEstate}
      />
      <HoldingsSection<Business>
        anchor="sec-businesses" title="Businesses" itemLabel="business"
        subtotal={t.businesses} rows={data.businesses ?? []} columns={bizColumns} fields={bizFields}
        emptyTitle="No businesses" emptyHint="Add a business you own a stake in."
        toForm={(b) => ({ name: s(b?.name), valuation: s(b?.valuation), ownership_pct: b ? String(b.ownership_pct) : "100", notes: s(b?.notes) })}
        toBody={(f) => ({ name: f.name.trim(), valuation: num(f.valuation), ownership_pct: num(f.ownership_pct), notes: optStr(f.notes) })}
        rowLabel={(b) => b.name}
        onCreate={createBusiness} onUpdate={updateBusiness} onDelete={deleteBusiness}
      />
      <HoldingsSection<FixedIncome>
        anchor="sec-fixed-income" title="Fixed-income securities" itemLabel="security"
        subtotal={t.fixed_income} rows={data.fixed_income ?? []} columns={fiColumns} fields={fiFields}
        emptyTitle="No fixed-income securities" emptyHint="Add bonds, CDs or treasuries."
        toForm={(f) => ({ name: s(f?.name), issuer: s(f?.issuer), face_value: s(f?.face_value), coupon_rate: s(f?.coupon_rate), maturity_date: s(f?.maturity_date), current_value: s(f?.current_value) })}
        toBody={(f) => ({ name: f.name.trim(), issuer: optStr(f.issuer), face_value: num(f.face_value), coupon_rate: optNum(f.coupon_rate), maturity_date: optStr(f.maturity_date), current_value: optNum(f.current_value) })}
        rowLabel={(f) => f.name}
        onCreate={createFixedIncome} onUpdate={updateFixedIncome} onDelete={deleteFixedIncome}
      />
      <HoldingsSection<CashAccount>
        anchor="sec-cash" title="Cash accounts" itemLabel="account"
        subtotal={t.cash} rows={data.cash_accounts ?? []} columns={cashColumns} fields={cashFields}
        emptyTitle="No cash accounts" emptyHint="Add checking, savings or money-market balances."
        toForm={(c) => ({ name: s(c?.name), balance: s(c?.balance) })}
        toBody={(f) => ({ name: f.name.trim(), balance: num(f.balance) })}
        rowLabel={(c) => c.name}
        onCreate={createCashAccount} onUpdate={updateCashAccount} onDelete={deleteCashAccount}
      />
    </div>
  );
}
