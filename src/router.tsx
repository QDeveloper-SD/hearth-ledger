import { useEffect } from "react";
import { QueryClient, useQuery } from "@tanstack/react-query";
import {
  createRouter,
  createRootRoute,
  createRoute,
  Outlet,
  Link,
  useRouterState,
  Navigate,
} from "@tanstack/react-router";
import { getSettings } from "@/lib/api";
import {
  LayoutDashboard,
  BookOpen,
  PieChart,
  CreditCard,
  TrendingUp,
  ShieldAlert,
  CalendarClock,
  Settings,
  Wallet,
} from "lucide-react";
import { cn } from "@/lib/utils";
import Login from "./routes/index";
import Dashboard from "./routes/app.dashboard";
import Ledger from "./routes/app.ledger";
import Portfolio from "./routes/app.portfolio";
import Debt from "./routes/app.debt";
import Income from "./routes/app.income";
import Risk from "./routes/app.risk";
import Planning from "./routes/app.planning";
import SettingsPage from "./routes/app.settings";

export const queryClient = new QueryClient();

const nav = [
  { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/app/ledger", label: "Ledger", icon: BookOpen },
  { to: "/app/portfolio", label: "Portfolio", icon: PieChart },
  { to: "/app/debt", label: "Debt", icon: CreditCard },
  { to: "/app/income", label: "Income", icon: TrendingUp },
  { to: "/app/risk", label: "Risk", icon: ShieldAlert },
  { to: "/app/planning", label: "Planning", icon: CalendarClock },
  { to: "/app/settings", label: "Settings", icon: Settings },
] as const;

function AppShell() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", settings?.theme === "dark");
  }, [settings?.theme]);
  return (
    <div className="min-h-screen flex bg-muted/30">
      <aside className="w-56 shrink-0 bg-background border-r border-border flex flex-col">
        <div className="h-16 flex items-center gap-2 px-4 border-b border-border">
          <div className="h-8 w-8 rounded-lg bg-primary text-primary-foreground grid place-items-center">
            <Wallet className="h-4 w-4" />
          </div>
          <span className="font-semibold">Hearth</span>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {nav.map((n) => {
            const active = pathname.startsWith(n.to);
            return (
              <Link
                key={n.to}
                to={n.to}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground hover:bg-brand-soft",
                )}
              >
                <n.icon className="h-4 w-4" />
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 text-xs text-muted-foreground border-t border-border">
          <Link to="/" className="hover:text-foreground">Sign out</Link>
        </div>
      </aside>
      <main className="flex-1 min-w-0 p-8 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}

function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

const rootRoute = createRootRoute({ component: Outlet, notFoundComponent: NotFound });

const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: Login });

const appRoute = createRoute({ getParentRoute: () => rootRoute, path: "/app", component: AppShell });
const appIndexRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  component: () => <Navigate to="/app/dashboard" />,
});
const dashboardRoute = createRoute({ getParentRoute: () => appRoute, path: "/dashboard", component: Dashboard });
const ledgerRoute = createRoute({ getParentRoute: () => appRoute, path: "/ledger", component: Ledger });
const portfolioRoute = createRoute({ getParentRoute: () => appRoute, path: "/portfolio", component: Portfolio });
const debtRoute = createRoute({ getParentRoute: () => appRoute, path: "/debt", component: Debt });
const incomeRoute = createRoute({ getParentRoute: () => appRoute, path: "/income", component: Income });
const riskRoute = createRoute({ getParentRoute: () => appRoute, path: "/risk", component: Risk });
const planningRoute = createRoute({ getParentRoute: () => appRoute, path: "/planning", component: Planning });
const settingsRoute = createRoute({ getParentRoute: () => appRoute, path: "/settings", component: SettingsPage });

const routeTree = rootRoute.addChildren([
  indexRoute,
  appRoute.addChildren([
    appIndexRoute,
    dashboardRoute,
    ledgerRoute,
    portfolioRoute,
    debtRoute,
    incomeRoute,
    riskRoute,
    planningRoute,
    settingsRoute,
  ]),
]);

export const router = createRouter({ routeTree, scrollRestoration: true });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
