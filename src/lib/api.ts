export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  const json = await res.json();
  if (!res.ok) {
    throw new ApiError(res.status, json?.error ?? res.statusText);
  }
  return json.data as T;
}

export type LedgerEntry = {
  id: string;
  date: string;
  desc: string;
  category: string;
  amount: number;
};

export type Debt = {
  id: string;
  name: string;
  balance: number;
  rate: number;
  min_payment: number;
};

export type IncomeSource = {
  id: string;
  name: string;
  amount: number;
  cadence: string;
};

export type Holding = {
  symbol: string;
  name?: string;
  qty: number;
  price: number | null;
  day_change: number | null;
};

export type ManualHolding = { id: string; symbol: string; qty: number; cost_basis: number };
export type CashAccount   = { id: string; name: string; balance: number };

export type DashboardData = {
  net_worth: number;
  net_worth_breakdown: { name: string; value: number }[];
  portfolio_breakdown: { name: string; value: number }[];
  income_summary: { total: number; sources: { name: string; amount: number }[] };
  debt_summary: { total: number; accounts: { name: string; balance: number }[] };
  recent_ledger: LedgerEntry[];
};

export type PortfolioData = {
  holdings: Holding[];
  allocation: { name: string; value: number }[];
  series: { month: string; value: number }[];
  sharpe_ratio: number;
  volatility: number;
  not_configured?: boolean;
  manual_holdings: ManualHolding[];
  cash_accounts: CashAccount[];
};

export type RiskData = {
  net_worth: number;
  dti: number;
  emergency_months: number;
  current_ratio: number;
  exposure: { name: string; value: number }[];
  insurance: { name: string; covered: boolean }[];
  spend_series: { m: string; spend: number }[];
};

export type PlanningEvent = {
  id: string;
  title: string;
  date: string;
  type: string;
};

export type Settings = {
  live_sync: boolean;
  theme: string;
  data_dir: string | null;
  username: string;
};

export const getDashboard = () => api<DashboardData>("/dashboard");
type LedgerListResponse = { entries: LedgerEntry[]; total: number; page: number; page_size: number };
export const listLedger = async (): Promise<LedgerEntry[]> => {
  const r = await api<LedgerListResponse>("/ledger");
  return r.entries;
};
export const createLedger = (body: Omit<LedgerEntry, "id">) =>
  api<LedgerEntry>("/ledger", { method: "POST", body: JSON.stringify(body) });
export const updateLedger = (id: string, body: Partial<Omit<LedgerEntry, "id">>) =>
  api<LedgerEntry>(`/ledger/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteLedger = (id: string) =>
  api<void>(`/ledger/${id}`, { method: "DELETE" });

export const getPortfolio = () => api<PortfolioData>("/portfolio");
export const syncPortfolio = () => api<PortfolioData>("/portfolio/sync", { method: "POST" });

export const createManualHolding = (body: Omit<ManualHolding, "id">) =>
  api<ManualHolding>("/portfolio/manual", { method: "POST", body: JSON.stringify(body) });
export const updateManualHolding = (id: string, body: Omit<ManualHolding, "id">) =>
  api<ManualHolding>(`/portfolio/manual/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteManualHolding = (id: string) =>
  api<null>(`/portfolio/manual/${id}`, { method: "DELETE" });

export const createCashAccount = (body: Omit<CashAccount, "id">) =>
  api<CashAccount>("/portfolio/cash", { method: "POST", body: JSON.stringify(body) });
export const updateCashAccount = (id: string, body: Omit<CashAccount, "id">) =>
  api<CashAccount>(`/portfolio/cash/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteCashAccount = (id: string) =>
  api<null>(`/portfolio/cash/${id}`, { method: "DELETE" });

export const listDebts = () => api<Debt[]>("/debts");
export const createDebt = (body: Omit<Debt, "id">) =>
  api<Debt>("/debts", { method: "POST", body: JSON.stringify(body) });
export const updateDebt = (id: string, body: Partial<Omit<Debt, "id">>) =>
  api<Debt>(`/debts/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteDebt = (id: string) =>
  api<void>(`/debts/${id}`, { method: "DELETE" });

export const listIncome = () => api<IncomeSource[]>("/income");
export const createIncome = (body: Omit<IncomeSource, "id">) =>
  api<IncomeSource>("/income", { method: "POST", body: JSON.stringify(body) });
export const updateIncome = (id: string, body: Partial<Omit<IncomeSource, "id">>) =>
  api<IncomeSource>(`/income/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteIncome = (id: string) =>
  api<void>(`/income/${id}`, { method: "DELETE" });

export const getRisk = () => api<RiskData>("/risk");
export const toggleInsurance = (name: string, covered: boolean) =>
  api<RiskData["insurance"]>(`/risk/insurance/${encodeURIComponent(name)}`, {
    method: "PATCH",
    body: JSON.stringify({ covered }),
  });
export const listPlanningEvents = () => api<PlanningEvent[]>("/planning/events");

export const getSettings = () => api<Settings>("/settings");
export const updateSettings = (body: Partial<Settings>) =>
  api<Settings>("/settings", { method: "PATCH", body: JSON.stringify(body) });
export const setApiKey = (key: string) =>
  api<void>("/settings/api-key", { method: "POST", body: JSON.stringify({ key }) });

export const login = (username: string, password: string) =>
  fetch("/api/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  }).then((r) => r.json());

export const logout = () =>
  fetch("/api/auth/logout", { method: "POST", credentials: "include" });

export const exportPdf = (sections: string[]) =>
  fetch("/api/export/pdf", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sections }),
  });
