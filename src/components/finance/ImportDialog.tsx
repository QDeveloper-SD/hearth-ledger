import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload, Download, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { importFile, type ImportKind, type ImportResult } from "@/lib/api";

type Col = { name: string; required: boolean; what: string; example: string };
type Spec = { title: string; queryKey: string; columns: Col[]; notes: string[]; template: string; previewCols: string[] };

const SPECS: Record<ImportKind, Spec> = {
  ledger: {
    title: "Ledger",
    queryKey: "ledger",
    columns: [
      { name: "date", required: true, what: "Transaction date. YYYY-MM-DD preferred; MM/DD/YYYY, M/D/YY and Excel date cells also work.", example: "2026-01-06" },
      { name: "description", required: true, what: "What the transaction was.", example: "Grocery store" },
      { name: "category", required: true, what: "Category name.", example: "Food" },
      { name: "amount", required: true, what: "Negative for expenses, positive for money in. $ , and (parentheses) are understood.", example: "-84.32" },
    ],
    notes: ['Entries with the category "Income" are what the dashboard counts as income.', "Rows that already exist (same date, description, category and amount) are skipped, so re-importing a file is safe."],
    template: "date,description,category,amount\n2026-01-05,Paycheck,Income,2500.00\n2026-01-06,Grocery store,Food,-84.32\n",
    previewCols: ["date", "desc", "category", "amount"],
  },
  debts: {
    title: "Debt",
    queryKey: "debts",
    columns: [
      { name: "name", required: true, what: "Name of the debt account.", example: "Visa card" },
      { name: "balance", required: true, what: "Amount owed, as a positive number.", example: "4200.50" },
      { name: "rate", required: false, what: "Annual interest rate in percent. Default 0.", example: "19.9" },
      { name: "min_payment", required: false, what: "Minimum monthly payment. Default 0.", example: "95" },
    ],
    notes: ["Debts whose name already exists (case-insensitive) are skipped."],
    template: "name,balance,rate,min_payment\nVisa card,4200.50,19.9,95\nCar loan,12800,6.9,310\n",
    previewCols: ["name", "balance", "rate", "min_payment"],
  },
  income: {
    title: "Income",
    queryKey: "income",
    columns: [
      { name: "name", required: true, what: "Name of the income source.", example: "Main salary" },
      { name: "amount", required: true, what: "Amount per paycheck.", example: "2400" },
      { name: "cadence", required: true, what: "One of weekly, biweekly, monthly, annual.", example: "biweekly" },
    ],
    notes: ["Income sources whose name already exists (case-insensitive) are skipped."],
    template: "name,amount,cadence\nMain salary,2400,biweekly\nSide gig,300,monthly\n",
    previewCols: ["name", "amount", "cadence"],
  },
};

function downloadTemplate(kind: ImportKind) {
  const blob = new Blob([SPECS[kind].template], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${kind}-template.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function ImportDialog({ kind, open, onOpenChange }: { kind: ImportKind; open: boolean; onOpenChange: (o: boolean) => void }) {
  const spec = SPECS[kind];
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reset() { setFile(null); setPreview(null); setResult(null); setError(null); }

  const dry = useMutation({
    mutationFn: (f: File) => importFile(kind, f, true),
    onSuccess: (r) => { setPreview(r); setError(null); },
    onError: (e: Error) => { setPreview(null); setError(e.message); },
  });
  const commit = useMutation({
    mutationFn: (f: File) => importFile(kind, f, false),
    onSuccess: (r) => {
      setResult(r); setError(null);
      for (const k of [spec.queryKey, "dashboard", "risk"]) qc.invalidateQueries({ queryKey: [k] });
    },
    onError: (e: Error) => setError(e.message),
  });

  function pick(f: File | null) {
    setFile(f); setPreview(null); setError(null);
    if (f) dry.mutate(f);
  }

  const summary = (r: ImportResult, done: boolean) => (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-sm">
      <Stat label="Rows read" value={r.total_rows} />
      <Stat label={done ? "Imported" : "Valid"} value={done ? r.imported_count : r.valid_count} />
      <Stat label="Duplicates skipped" value={r.duplicate_count} />
      <Stat label="Errors skipped" value={r.error_count} />
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import {spec.title} from a spreadsheet</DialogTitle>
          <DialogDescription>Upload a .csv or .xlsx file. You will see a preview before anything is saved.</DialogDescription>
        </DialogHeader>

        {!result && (
          <div className="space-y-4 text-sm">
            <div className="rounded-md border border-border p-3 space-y-2">
              <p className="font-medium">File format</p>
              <p className="text-muted-foreground">
                Accepted: <span className="font-medium text-foreground">.csv</span> or <span className="font-medium text-foreground">.xlsx</span> (first sheet).
                The <span className="font-medium text-foreground">first row must be the header row</span> with these column names (case does not matter):
              </p>
              <table className="w-full text-xs">
                <thead className="text-left text-muted-foreground uppercase">
                  <tr><th className="py-1 pr-2">Column</th><th className="pr-2">Required</th><th className="pr-2">Contents</th><th>Example</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {spec.columns.map((c) => (
                    <tr key={c.name} className="align-top">
                      <td className="py-1.5 pr-2 font-mono">{c.name}</td>
                      <td className="pr-2">{c.required ? "Required" : "Optional"}</td>
                      <td className="pr-2">{c.what}</td>
                      <td className="font-mono">{c.example}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-0.5">
                {spec.notes.map((n) => <li key={n}>{n}</li>)}
                <li>Blank rows are ignored. Rows with problems are skipped and listed; the rest are imported.</li>
              </ul>
              <Button variant="outline" size="sm" onClick={() => downloadTemplate(kind)}><Download className="h-4 w-4" /> Download template</Button>
            </div>

            <div>
              <input
                ref={inputRef}
                type="file"
                accept=".csv,.xlsx"
                className="hidden"
                onChange={(e) => { pick(e.target.files?.[0] ?? null); e.target.value = ""; }}
              />
              <Button onClick={() => inputRef.current?.click()} disabled={dry.isPending || commit.isPending}>
                <Upload className="h-4 w-4" /> {file ? "Choose a different file" : "Choose file"}
              </Button>
              {file && <span className="ml-3 text-muted-foreground"><FileSpreadsheet className="inline h-4 w-4 mr-1" />{file.name}</span>}
            </div>

            {dry.isPending && <p className="text-muted-foreground">Reading file…</p>}
            {error && <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-destructive">{error}</div>}

            {preview && (
              <div className="space-y-3">
                {summary(preview, false)}
                {preview.preview.length > 0 && (
                  <div className="max-h-56 overflow-auto rounded-md border border-border">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-background text-left text-muted-foreground uppercase">
                        <tr>{spec.previewCols.map((c) => <th key={c} className="px-2 py-1">{c}</th>)}</tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {preview.preview.map((r, i) => (
                          <tr key={i}>{spec.previewCols.map((c) => <td key={c} className="px-2 py-1">{String(r[c])}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {preview.valid_count > 20 && <p className="text-xs text-muted-foreground">Showing the first 20 of {preview.valid_count} rows.</p>}
                {preview.errors.length > 0 && (
                  <div className="rounded-md border border-destructive/40 p-2 text-xs max-h-32 overflow-auto">
                    <p className="font-medium text-destructive mb-1">{preview.error_count} row(s) have errors and will be skipped:</p>
                    <ul className="space-y-0.5">{preview.errors.map((e) => <li key={e.row}>{e.message}</li>)}</ul>
                    {preview.errors_truncated && <p className="mt-1 text-muted-foreground">…and more (showing the first {preview.errors.length}).</p>}
                  </div>
                )}
                {preview.duplicate_count > 0 && <p className="text-xs text-muted-foreground">{preview.duplicate_count} row(s) already exist and will be skipped.</p>}
                {preview.valid_count === 0 && <p className="text-xs text-muted-foreground">There is nothing new to import from this file.</p>}
              </div>
            )}
          </div>
        )}

        {result && (
          <div className="space-y-3 text-sm">
            <p className="font-medium text-profit">Import complete.</p>
            {summary(result, true)}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button onClick={() => { reset(); onOpenChange(false); }}>Close</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => { reset(); onOpenChange(false); }}>Cancel</Button>
              <Button disabled={!file || !preview || preview.valid_count === 0 || commit.isPending} onClick={() => file && commit.mutate(file)}>
                {commit.isPending ? "Importing…" : `Import ${preview?.valid_count ?? 0} rows`}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border p-2">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
