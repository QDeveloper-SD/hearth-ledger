import { useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Panel, EmptyState } from "@/components/finance/primitives";

const usdFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
export const usd = (v: number) => usdFmt.format(v);

export type FieldDef = {
  key: string;
  label: string;
  type: "text" | "number" | "date";
  required?: boolean;
  min?: number;
  max?: number;
  step?: string;
  placeholder?: string;
  hint?: string;
};

export type ColumnDef<T> = {
  header: string;
  cell: (row: T) => ReactNode;
  align?: "right";
};

export type FormValues = Record<string, string>;

/** Returns an error message for a field value, or null when valid. */
export function validateField(f: FieldDef, raw: string): string | null {
  const v = raw.trim();
  if (v === "") return f.required ? "Required" : null;
  if (f.type === "number") {
    const n = Number(v);
    if (!Number.isFinite(n)) return "Enter a number";
    if (f.min != null && n < f.min) return `Must be at least ${f.min}`;
    if (f.max != null && n > f.max) return `Must be at most ${f.max}`;
  }
  if (f.type === "date") {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);
    const d = m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : null;
    if (!m || !d || d.getUTCMonth() !== +m[2] - 1 || d.getUTCDate() !== +m[3]) return "Use YYYY-MM-DD";
  }
  return null;
}

/** Parse helpers for toBody callbacks. */
export const num = (s: string) => Number(s.trim());
export const optNum = (s: string) => (s.trim() === "" ? null : Number(s.trim()));
export const optStr = (s: string) => (s.trim() === "" ? null : s.trim());

type Props<T extends { id: string }> = {
  /** DOM id, used for scroll-to from the summary. */
  anchor: string;
  title: string;
  note?: string;
  subtotal: number;
  rows: T[];
  columns: ColumnDef<T>[];
  fields: FieldDef[];
  itemLabel: string;
  emptyTitle: string;
  emptyHint: string;
  /** Initial form values for a new row, or for editing an existing one. */
  toForm: (row?: T) => FormValues;
  toBody: (form: FormValues) => Omit<T, "id">;
  onCreate: (body: Omit<T, "id">) => Promise<unknown>;
  onUpdate: (id: string, body: Omit<T, "id">) => Promise<unknown>;
  onDelete: (id: string) => Promise<unknown>;
  rowLabel: (row: T) => string;
};

export function HoldingsSection<T extends { id: string }>(p: Props<T>) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState<T | null>(null);
  const [form, setForm] = useState<FormValues>({});

  const done = () => {
    for (const k of ["portfolio", "dashboard", "risk"]) qc.invalidateQueries({ queryKey: [k] });
  };
  const save = useMutation({
    mutationFn: () => {
      const body = p.toBody(form);
      return target ? p.onUpdate(target.id, body) : p.onCreate(body);
    },
    onSuccess: () => { done(); setOpen(false); },
  });
  const del = useMutation({ mutationFn: (id: string) => p.onDelete(id), onSuccess: done });

  const openDialog = (row?: T) => {
    setTarget(row ?? null);
    setForm(p.toForm(row));
    save.reset();
    setOpen(true);
  };

  const errors = Object.fromEntries(p.fields.map((f) => [f.key, validateField(f, form[f.key] ?? "")]));
  const valid = Object.values(errors).every((e) => e === null);
  const apiError = save.error instanceof Error ? save.error.message : null;

  return (
    <div id={p.anchor} className="scroll-mt-4">
      <Panel
        title={p.title}
        action={
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold tabular-nums">{usd(p.subtotal)}</span>
            <Button size="sm" onClick={() => openDialog()}><Plus className="h-3.5 w-3.5 mr-1" />Add</Button>
          </div>
        }
      >
        {p.note && <p className="-mt-2 mb-3 text-xs text-muted-foreground">{p.note}</p>}
        {p.rows.length === 0 ? (
          <EmptyState
            height={110}
            title={p.emptyTitle}
            hint={p.emptyHint}
            action={<Button size="sm" variant="outline" onClick={() => openDialog()}><Plus className="h-3.5 w-3.5 mr-1" />Add {p.itemLabel}</Button>}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted-foreground uppercase text-left">
                <tr>
                  {p.columns.map((c) => (
                    <th key={c.header} className={"py-2 pr-3 font-medium " + (c.align === "right" ? "text-right" : "")}>{c.header}</th>
                  ))}
                  <th className="text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {p.rows.map((row) => (
                  <tr key={row.id}>
                    {p.columns.map((c) => (
                      <td key={c.header} className={"py-2.5 pr-3 " + (c.align === "right" ? "text-right tabular-nums" : "")}>{c.cell(row)}</td>
                    ))}
                    <td className="text-right whitespace-nowrap">
                      <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Edit ${p.rowLabel(row)}`} onClick={() => openDialog(row)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost" size="icon" className="h-7 w-7 text-loss" aria-label={`Delete ${p.rowLabel(row)}`}
                        disabled={del.isPending}
                        onClick={() => { if (window.confirm(`Delete ${p.rowLabel(row)}?`)) del.mutate(row.id); }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {del.error instanceof Error && <p className="mt-2 text-xs text-loss">{del.error.message}</p>}
          </div>
        )}
      </Panel>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{target ? "Edit" : "Add"} {p.itemLabel}</DialogTitle></DialogHeader>
          <form
            className="space-y-3"
            onSubmit={(e) => { e.preventDefault(); if (valid && !save.isPending) save.mutate(); }}
          >
            {p.fields.map((f) => {
              const err = (form[f.key] ?? "") !== "" ? errors[f.key] : null;
              return (
                <div key={f.key}>
                  <Label htmlFor={`${p.anchor}-${f.key}`}>{f.label}{f.required ? " *" : ""}</Label>
                  <Input
                    id={`${p.anchor}-${f.key}`}
                    type={f.type === "date" ? "text" : f.type}
                    step={f.type === "number" ? (f.step ?? "any") : undefined}
                    min={f.min}
                    max={f.max}
                    placeholder={f.type === "date" ? (f.placeholder ?? "YYYY-MM-DD") : f.placeholder}
                    value={form[f.key] ?? ""}
                    onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                    aria-invalid={err ? true : undefined}
                  />
                  {err ? <p className="mt-1 text-xs text-loss">{err}</p>
                    : f.hint ? <p className="mt-1 text-xs text-muted-foreground">{f.hint}</p> : null}
                </div>
              );
            })}
            {apiError && <p className="text-sm text-loss">{apiError}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!valid || save.isPending}>
                {save.isPending ? "Saving…" : target ? "Save" : "Add"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
