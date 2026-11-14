import { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
    </div>
  );
}

export function Panel({
  title,
  children,
  className,
  action,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <Card className={cn("p-5", className)}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-4">
          {title && <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </Card>
  );
}

export function Money({ value, signed = false }: { value: number; signed?: boolean }) {
  const positive = value >= 0;
  const cls = positive ? "text-profit" : "text-loss";
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Math.abs(value));
  return (
    <span className={cls}>
      {signed ? (positive ? "+" : "−") : positive ? "" : "−"}
      {formatted}
    </span>
  );
}

export const CHART_COLORS = [
  "oklch(0.72 0.12 230)",
  "oklch(0.62 0.18 145)",
  "oklch(0.78 0.14 85)",
  "oklch(0.6 0.22 25)",
  "oklch(0.55 0.15 295)",
  "oklch(0.7 0.1 200)",
];

export function EmptyState({
  title = "No data yet",
  hint,
  height = 200,
  action,
}: {
  title?: string;
  hint?: string;
  height?: number;
  action?: ReactNode;
}) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center gap-1 rounded-md border border-dashed border-border text-muted-foreground"
      style={{ minHeight: height }}
    >
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="text-xs">{hint}</p>}
      {action && <div className="mt-2 text-xs">{action}</div>}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  label = "Failed to load data.",
}: {
  error?: unknown;
  onRetry?: () => void;
  label?: string;
}) {
  const msg = error instanceof Error ? error.message : undefined;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-border p-4 text-sm">
      <span className="text-loss">
        {label}
        {msg ? ` ${msg}` : ""}
      </span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="rounded-md border border-border px-2.5 py-1 text-xs hover:bg-muted">
          Retry
        </button>
      )}
    </div>
  );
}
