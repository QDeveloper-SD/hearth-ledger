# Hearth Ledger — MVP Structure

A local-first family accounting app. Runs on a NAS or home PC. One Python process serves a REST API **and** the built frontend. Data lives in a single JSON file on disk.

---

## 1. Goals & non-goals

**Goals**
- Run entirely on the family's own hardware. No cloud, no SaaS.
- Single command to start: `python -m hearth` (or `./run.sh`).
- One JSON file as the database. Edits mutate the file in place; no event log, no append-only growth.
- Read-only Public.com brokerage integration for the Portfolio page.
- Eight pages already designed in `src/routes/` get wired to real data.

**Non-goals (MVP)**
- Multi-tenant / multi-family deployments.
- Trading endpoints on Public.com.
- Encrypted-at-rest storage (filesystem perms only).
- Mobile apps. Browser is the only client.
- Real-time push. Frontend polls or refetches on user action.

---

## 2. Top-level layout

```
family_accounting/
├── backend/                     # NEW — Python package
│   ├── __init__.py
│   ├── __main__.py              # entrypoint: `python -m backend`
│   ├── app.py                   # FastAPI app factory, CORS, static mount
│   ├── config.py                # paths, env, default data location
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── json_store.py        # atomic read/write + file lock
│   │   └── schema.py            # Pydantic models for the JSON document
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              # local login (single user/family password)
│   │   ├── ledger.py            # GET/POST/PATCH/DELETE entries
│   │   ├── portfolio.py         # local holdings + Public.com sync
│   │   ├── debt.py              # debt accounts CRUD
│   │   ├── income.py            # income sources CRUD
│   │   ├── risk.py              # derived metrics (read-only)
│   │   ├── planning.py          # calendar/calc tools state
│   │   ├── settings.py          # config (api key, theme, etc.)
│   │   └── dashboard.py         # aggregates for landing page
│   ├── integrations/
│   │   ├── __init__.py
│   │   └── public_api.py        # Public.com REST client (read-only)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── metrics.py           # net worth, sharpe, vol, DTI, etc.
│   │   └── pdf.py               # PDF export (Print PDF button)
│   └── tests/
│       ├── test_json_store.py
│       ├── test_ledger.py
│       └── test_metrics.py
│
├── data/                        # NEW — runtime data (git-ignored)
│   ├── hearth.json              # the one JSON document
│   ├── hearth.json.bak          # rolling backup on every write
│   └── config.json              # API key, theme, data dir override
│
├── src/                         # EXISTING — frontend (kept as-is structurally)
│   └── ...                      # routes refactored to call /api/* via fetch
│
├── requirements.txt             # NEW
├── run.sh                       # NEW — convenience launcher
├── mvp_structure.md             # THIS FILE
└── mpv_prompt.md                # original UI spec (kept)
```

`wrangler.jsonc` and `@cloudflare/vite-plugin` will be removed — the app is no longer deployed to Cloudflare. Vite builds a static SPA; FastAPI serves the `dist/` directory.

---

## 3. The JSON document

One file: `data/hearth.json`. Read fully into memory on each request, validated through Pydantic, mutated, written back atomically (`tmp + rename`) under a `filelock`. A `.bak` of the previous version is kept.

```jsonc
{
  "version": 1,
  "updated_at": "2026-05-20T14:30:00Z",
  "auth": {
    "username": "family",
    "password_hash": "argon2id$..."
  },
  "settings": {
    "data_dir": null,
    "live_sync": true,
    "theme": "light",
    "public_api_key_enc": null
  },
  "ledger": [
    { "id": "ulid", "date": "2026-05-15", "desc": "Grocery", "category": "Food", "amount": -184.22 }
  ],
  "debts": [
    { "id": "ulid", "name": "Mortgage", "balance": -238000, "rate": 0.0625, "min_payment": 1820 }
  ],
  "income_sources": [
    { "id": "ulid", "name": "Salary — Acme", "amount": 4820, "cadence": "biweekly" }
  ],
  "portfolio": {
    "manual_holdings": [
      { "symbol": "VTI", "qty": 120, "cost_basis": 24000 }
    ],
    "public_cache": {
      "fetched_at": "2026-05-20T14:25:00Z",
      "account_value": 186432.10,
      "holdings": []
    }
  },
  "planning": {
    "events": [],
    "scenarios": []
  }
}
```

Why one document (not one file per table): scale is small (one family, decades of ledger entries is still well under a few MB), and the user explicitly requested it. Pydantic validation on every write keeps it honest.

Write strategy keeps the file from "ballooning": no events, no audit log, only the current state.

---

## 4. API surface

All routes prefixed `/api`. Auth via session cookie (signed, HttpOnly) set on `POST /api/auth/login`.

| Method | Path                              | Purpose                                  |
|-------:|-----------------------------------|------------------------------------------|
| POST   | `/api/auth/login`                 | username + password → session cookie     |
| POST   | `/api/auth/logout`                |                                          |
| GET    | `/api/dashboard`                  | aggregates for landing page              |
| GET    | `/api/ledger`                     | list (paginated, filterable)             |
| POST   | `/api/ledger`                     | add entry                                |
| PATCH  | `/api/ledger/{id}`                | edit                                     |
| DELETE | `/api/ledger/{id}`                | remove                                   |
| GET    | `/api/ledger/summary`             | category totals, monthly trend           |
| GET    | `/api/portfolio`                  | merged manual + Public.com cache         |
| POST   | `/api/portfolio/sync`             | refresh Public.com data                  |
| GET/POST/PATCH/DELETE | `/api/debts[/{id}]`  |                                          |
| GET/POST/PATCH/DELETE | `/api/income[/{id}]` |                                          |
| GET    | `/api/risk`                       | derived: net worth, DTI, emergency fund  |
| GET/POST/PATCH/DELETE | `/api/planning/events[/{id}]` |                                  |
| GET    | `/api/settings`                   |                                          |
| PATCH  | `/api/settings`                   |                                          |
| POST   | `/api/settings/api-key`           | set Public.com API key                   |
| POST   | `/api/export/pdf`                 | returns PDF blob (sections in body)      |

All responses are JSON with consistent envelope:
```json
{ "data": ..., "error": null }
```

---

## 5. Public.com integration

`backend/integrations/public_api.py` — thin httpx client. Read-only methods only:
- `get_account()`
- `get_holdings()`
- `get_historical(symbol, range)` (if available)

Endpoint URLs and auth scheme will be confirmed against Public.com's official docs **before** implementation — not invented. Results cached into `portfolio.public_cache` with a TTL (default 15 min) to avoid hammering the API on every page load.

If `settings.public_api_key_enc` is unset, the Portfolio page works in manual-only mode and the sync button shows "Set API key in Settings."

---

## 6. Frontend changes

Minimal — pages keep their layout, but the hardcoded arrays move out:

- Add `src/lib/api.ts`: a typed fetch wrapper around `/api/*`.
- Each `app.*.tsx` route uses TanStack Query (`@tanstack/react-query` is already a dependency) to load its data.
- Login page (`index.tsx`) calls `POST /api/auth/login` instead of just navigating.
- Settings page wires Public.com API key field to `POST /api/settings/api-key`.
- Drop Cloudflare Workers config: remove `wrangler.jsonc`, `@cloudflare/vite-plugin`, simplify `vite.config.ts`, and adjust `src/server.ts`/`src/start.ts` (or remove SSR entirely and ship as SPA — recommended for local use).

---

## 7. Auth

Single shared family credential. On first run, `data/hearth.json` doesn't exist → the backend creates it and prompts (via a first-run endpoint) to set username/password. Password hashed with argon2. Session cookie signed with a key kept in `data/config.json` (auto-generated on first run).

No OAuth, no MFA, no per-user roles in MVP.

---

## 8. Run story

```bash
# one-time
pip install -r requirements.txt
bun install
bun run build          # produces dist/

# every run
python -m backend      # serves API + dist/ on http://localhost:8765
```

Or `./run.sh` does both. On a NAS, the same command works under systemd or PM2-style supervisors.

---

## 9. Tests

- `pytest` with `tmp_path` for JSON store tests.
- `httpx.AsyncClient` against the FastAPI app for endpoint tests.
- Public.com client tested against recorded fixtures (no live calls in CI).

Target: storage + ledger CRUD + metrics covered before shipping. Public.com client covered by integration tests gated on an env var.

---

## 10. Decisions (locked in 2026-05-20)

1. **Auth:** single shared family password. Stored as argon2id hash on `hearth.json`.
2. **Frontend deploy:** Cloudflare Workers adapter is being removed. `wrangler.jsonc` and `@cloudflare/vite-plugin` go away; Vite produces a static SPA; FastAPI serves `dist/` and `/api/*` from the same process.
3. **Public.com integration:** stubbed pending the official API docs URL from the user. Stub returns empty holdings + a clear "API not configured" status so the rest of the app works.
4. **PDF export:** included in MVP. `reportlab` stays in `requirements.txt`.
5. **Port:** default `8765`, overridable via `HEARTH_PORT` env var.
