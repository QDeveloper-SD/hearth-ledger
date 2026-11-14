export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let unauthorizedHandler: (() => void) | null = null;
/** Registered by the router: called whenever the server says the session is missing/expired. */
export function setUnauthorizedHandler(fn: () => void) {
  unauthorizedHandler = fn;
}

async function readJson(res: Response): Promise<any> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function errorMessage(json: any, res: Response): string {
  const detail = json?.error ?? json?.detail;
  if (typeof detail === "string" && detail) return detail;
  return res.statusText || `Request failed (${res.status})`;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      credentials: "include",
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Could not reach the Hearth server.");
  }
  const json = await readJson(res);
  if (!res.ok) {
    if (res.status === 401) unauthorizedHandler?.();
    throw new ApiError(res.status, errorMessage(json, res));
  }
  return json?.data as T;
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
  current_value?: number | null;
};

export type BrokerAccount = "manual" | "ibkr" | "other";
export type ManualHolding = {
  id: string;
  symbol: string;
  qty: number;
  /** TOTAL value paid for the position (not per share). */
  cost_basis: number;
  current_value?: number | null;
  account?: BrokerAccount;
  broker?: string | null;
};
export type RealEstate = {
  id: string; name: string; address?: string | null; current_value: number;
  purchase_price?: number | null; notes?: string | null;
};
export type Business = {
  id: string; name: string; valuation: number; ownership_pct: number; notes?: string | null;
};
export type FixedIncome = {
  id: string; name: string; issuer?: string | null; face_value: number;
  coupon_rate?: number | null; maturity_date?: string | null; current_value?: number | null;
};
export type PortfolioTotals = {
  public: number; manual: number; ibkr: number; other_brokers: number;
  real_estate: number; businesses: number; fixed_income: number; cash: number;
  /** All assets (before debts). */
  total: number;
  /** Market-valued holdings only (no real estate / businesses); what the history chart tracks. */
  investable: number;
};
export type CashAccount   = { id: string; name: string; balance: number };

export type DashboardData = {
  net_worth: number;
  net_worth_breakdown: { name: string; value: number }[];
  portfolio_breakdown: { name: string; value: number }[];
  income_summary: {
    /** Expected income per month from the configured sources (cadence-normalised). */
    expected_monthly: number;
    /** Income actually received this calendar month / year (positive ledger entries). */
    mtd: number;
    ytd: number;
    /** Per-paycheck amount with the cadence as entered by the user. */
    sources: { name: string; amount: number; cadence: string }[];
  };
  debt_summary: { total: number; accounts: { name: string; balance: number }[] };
  recent_ledger: LedgerEntry[];
};

export type IbkrHolding = {
  symbol: string; name?: string | null; qty: number; price: number | null;
  /** Values are in the IBKR account's base currency. */
  current_value: number | null; cost_basis_total: number | null; gain_value: number | null;
  currency?: string | null;
};
/** Interactive Brokers account pulled through the report-only Flex Web Service. */
export type IbkrSync = {
  configured: boolean; fetched_at: string | null; cash: number | null; holdings: IbkrHolding[];
};

export type PortfolioData = {
  holdings: Holding[];
  ibkr: IbkrSync;
  allocation: { name: string; value: number }[];
  series: { date: string; value: number }[];
  sharpe_ratio: number | null;
  volatility: number | null;
  not_configured?: boolean;
  manual_holdings: ManualHolding[];
  cash_accounts: CashAccount[];
  real_estate: RealEstate[];
  businesses: Business[];
  fixed_income: FixedIncome[];
  totals: PortfolioTotals;
};

export type RiskData = {
  net_worth: number;
  dti: number | null;
  emergency_months: number | null;
  current_ratio: number | null;
  exposure: { name: string; value: number }[];
  insurance: { name: string; covered: boolean }[];
  spend_series: { m: string; spend: number }[];
};

export type PlanningEvent = {
  id: string;
  title: string;
  date: string;
  amount: number | null;
  notes: string | null;
};
export type PlanningEventInput = Omit<PlanningEvent, "id">;

export type Settings = {
  live_sync: boolean;
  theme: string;
  data_dir: string | null;
  username: string;
  has_api_key: boolean;
  has_ibkr: boolean;
  ibkr_query_id: string;
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
export const syncIbkr = () => api<PortfolioData>("/portfolio/ibkr/sync", { method: "POST" });

export const createManualHolding = (body: Omit<ManualHolding, "id">) =>
  api<ManualHolding>("/portfolio/manual", { method: "POST", body: JSON.stringify(body) });
export const updateManualHolding = (id: string, body: Omit<ManualHolding, "id">) =>
  api<ManualHolding>(`/portfolio/manual/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteManualHolding = (id: string) =>
  api<null>(`/portfolio/manual/${id}`, { method: "DELETE" });

export type NewItem<T> = Omit<T, "id">;
export const createRealEstate = (body: NewItem<RealEstate>) =>
  api<RealEstate>("/portfolio/real-estate", { method: "POST", body: JSON.stringify(body) });
export const updateRealEstate = (id: string, body: NewItem<RealEstate>) =>
  api<RealEstate>(`/portfolio/real-estate/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteRealEstate = (id: string) =>
  api<null>(`/portfolio/real-estate/${id}`, { method: "DELETE" });
export const createBusiness = (body: NewItem<Business>) =>
  api<Business>("/portfolio/businesses", { method: "POST", body: JSON.stringify(body) });
export const updateBusiness = (id: string, body: NewItem<Business>) =>
  api<Business>(`/portfolio/businesses/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteBusiness = (id: string) =>
  api<null>(`/portfolio/businesses/${id}`, { method: "DELETE" });
export const createFixedIncome = (body: NewItem<FixedIncome>) =>
  api<FixedIncome>("/portfolio/fixed-income", { method: "POST", body: JSON.stringify(body) });
export const updateFixedIncome = (id: string, body: NewItem<FixedIncome>) =>
  api<FixedIncome>(`/portfolio/fixed-income/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteFixedIncome = (id: string) =>
  api<null>(`/portfolio/fixed-income/${id}`, { method: "DELETE" });

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
export const createPlanningEvent = (body: PlanningEventInput) =>
  api<PlanningEvent>("/planning/events", { method: "POST", body: JSON.stringify(body) });
export const updatePlanningEvent = (id: string, body: Partial<PlanningEventInput>) =>
  api<PlanningEvent>(`/planning/events/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deletePlanningEvent = (id: string) =>
  api<void>(`/planning/events/${id}`, { method: "DELETE" });

export const getSettings = () => api<Settings>("/settings");
export const updateSettings = (body: Partial<Pick<Settings, "live_sync" | "theme">>) =>
  api<Settings>("/settings", { method: "PATCH", body: JSON.stringify(body) });
export const setApiKey = (key: string) =>
  api<{ has_api_key: boolean }>("/settings/api-key", { method: "POST", body: JSON.stringify({ api_key: key }) });
export const deleteApiKey = () =>
  api<{ has_api_key: boolean }>("/settings/api-key", { method: "DELETE" });
export const setIbkr = (token: string, queryId: string) =>
  api<{ has_ibkr: boolean }>("/settings/ibkr", { method: "POST", body: JSON.stringify({ token, query_id: queryId }) });
export const deleteIbkr = () =>
  api<{ has_ibkr: boolean }>("/settings/ibkr", { method: "DELETE" });
export const changePassword = (current_password: string, new_password: string) =>
  api<{ changed: boolean }>("/auth/password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password }),
  });
export const changeUsername = (username: string) =>
  api<{ username: string }>("/auth/username", { method: "POST", body: JSON.stringify({ username }) });

export const login = async (
  username: string,
  password: string,
): Promise<{ error: string | null }> => {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (res.ok) return { error: null };
  const json = await readJson(res);
  if (res.status === 401) return { error: "Incorrect username or password." };
  return { error: errorMessage(json, res) };
};

/** Public: true when no household login exists yet (fresh install). */
export const getAuthStatus = async (): Promise<{ needs_setup: boolean }> => {
  const res = await fetch("/api/auth/status", { credentials: "include" });
  const json = await readJson(res);
  if (!res.ok) throw new ApiError(res.status, errorMessage(json, res));
  return json.data;
};

/** First run: create the household login and sign in. */
export const setupAccount = async (username: string, password: string): Promise<{ error: string | null }> => {
  const res = await fetch("/api/auth/setup", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (res.ok) return { error: null };
  return { error: errorMessage(await readJson(res), res) };
};

export const logout = () =>
  fetch("/api/auth/logout", { method: "POST", credentials: "include" });

export const exportPdf = (sections: string[]) =>
  fetch("/api/export/pdf", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sections }),
  });

export type ImportKind = "ledger" | "debts" | "income";
export type ImportResult = {
  kind: ImportKind;
  dry_run: boolean;
  total_rows: number;
  valid_count: number;
  duplicate_count: number;
  error_count: number;
  imported_count: number;
  preview: Record<string, string | number>[];
  errors: { row: number; message: string }[];
  errors_truncated: boolean;
  columns_found: string[];
};

/** Multipart upload (no manual Content-Type so the browser sets the boundary). */
export async function importFile(kind: ImportKind, file: File, dryRun: boolean): Promise<ImportResult> {
  const body = new FormData();
  body.append("file", file);
  let res: Response;
  try {
    res = await fetch(`/api/import/${kind}?dry_run=${dryRun}`, { method: "POST", credentials: "include", body });
  } catch {
    throw new ApiError(0, "Could not reach the Hearth server.");
  }
  const json = await readJson(res);
  if (!res.ok) {
    if (res.status === 401) unauthorizedHandler?.();
    throw new ApiError(res.status, errorMessage(json, res));
  }
  return json?.data as ImportResult;
}
