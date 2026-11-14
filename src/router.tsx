import { useEffect, useRef } from "react";
import { QueryClient, useQuery } from "@tanstack/react-query";
import { ApiError, logout, setUnauthorizedHandler } from "@/lib/api";
import {
  createRouter,
  createRootRoute,
  createRoute,
  Outlet,
  Link,
  useRouterState,
  Navigate,
  lazyRouteComponent,
  redirect,
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
const Dashboard = lazyRouteComponent(() => import("./routes/app.dashboard"));
const Ledger = lazyRouteComponent(() => import("./routes/app.ledger"));
const Portfolio = lazyRouteComponent(() => import("./routes/app.portfolio"));
const Debt = lazyRouteComponent(() => import("./routes/app.debt"));
const Income = lazyRouteComponent(() => import("./routes/app.income"));
const Risk = lazyRouteComponent(() => import("./routes/app.risk"));
const Planning = lazyRouteComponent(() => import("./routes/app.planning"));
const SettingsPage = lazyRouteComponent(() => import("./routes/app.settings"));

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Auth and "not found" failures won't fix themselves; only retry transient errors.
      retry: (count, err) =>
        !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
      refetchOnWindowFocus: false,
    },
  },
});

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
  // The content pane (not the window) scrolls, so reset it when the page changes.
  const mainRef = useRef<HTMLElement>(null);
  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [pathname]);
  return (
    <div className="h-screen flex overflow-hidden bg-muted/30">
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
          <button
            type="button"
            className="hover:text-foreground"
            onClick={async () => {
              await logout().catch(() => undefined);
              queryClient.clear();
              router.navigate({ to: "/" });
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      {/* Only the content area scrolls; the sidebar stays put. */}
      <main ref={mainRef} className="flex-1 min-w-0 p-8 overflow-x-hidden overflow-y-auto">
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

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/app",
  component: AppShell,
  // Session guard: never render app pages without a valid session.
  beforeLoad: async () => {
    try {
      await queryClient.ensureQueryData({ queryKey: ["settings"], queryFn: getSettings });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) throw redirect({ to: "/" });
      // Other failures (server down, etc.) are shown by the pages themselves.
    }
  },
});
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

// Session expired mid-use: drop cached data and go back to the login screen.
setUnauthorizedHandler(() => {
  queryClient.clear();
  if (router.state.location.pathname !== "/") router.navigate({ to: "/" });
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
