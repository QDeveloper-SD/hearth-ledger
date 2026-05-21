# Hearth Ledger

A local-first family accounting app. Runs on your own hardware (NAS, mini-PC, or laptop) — no cloud, no SaaS, no third party touching your numbers. One Python process serves both the REST API and the web UI; all data lives in a single JSON file on disk.

> **Version 1.0** — first public release. The full MVP is wired end-to-end and usable day-to-day; a few visualizations and conveniences are listed under [Roadmap](#roadmap).

---

## Why

Most household-finance tools are cloud SaaS. That means handing every transaction, balance, and brokerage position to a vendor who can change pricing, get breached, or shut down. Hearth Ledger is the opposite: clone the repo, run one command, and the whole family's books live on a machine you control. The only external service it talks to is your brokerage — and only to *read* your portfolio.

---

## Features (v1)

Hearth Ledger has eight pages, all wired to a real backend:

| Page          | What it does                                                                                   |
| ------------- | ---------------------------------------------------------------------------------------------- |
| **Dashboard** | Net-worth donut (assets only), recent ledger activity, debt & income summaries at a glance.    |
| **Ledger**    | Full transaction CRUD with date / description / category / amount. Pagination + filtering.     |
| **Portfolio** | Public.com brokerage sync (read-only), plus manual holdings and cash accounts you enter by hand. |
| **Debt**      | Track loans, mortgages, credit-card balances with interest rate and minimum payment.           |
| **Income**    | Recurring income sources with cadence (weekly / biweekly / monthly / annual).                  |
| **Risk**      | Derived metrics — debt-to-income, emergency-fund coverage — and insurance toggles.             |
| **Planning**  | Calendar of upcoming financial events and client-side scenario calculators.                    |
| **Settings**  | Change password, set Public.com API key, switch light / dark theme, export PDF report.         |

**Other v1 capabilities**

- Single-process deploy: FastAPI serves both `/api/*` and the built React SPA from one port.
- Argon2id-hashed shared family password (one login for the household).
- Atomic JSON writes with cross-process file locking and rolling `.bak` recovery.
- PDF export of current financial state (basic single-column layout).
- Light / dark theme, persisted per install.
- Test suite covering JSON storage, ledger CRUD, metrics, and the Public.com client (mocked, never hits live endpoints).

---

## Tech stack

- **Backend:** Python 3.11+, FastAPI, Pydantic, httpx, argon2-cffi, reportlab.
- **Frontend:** React 19, TanStack Router + Query, Vite, Tailwind CSS, shadcn/ui, Recharts.
- **Storage:** one JSON document at `data/hearth.json`. No database server.
- **External integrations:** Public.com brokerage API (read-only, optional).

---

## Quickstart

Requires Python 3.11+ and [Bun](https://bun.sh) (or npm).

```bash
git clone <your-fork-url> hearth-ledger
cd hearth-ledger

# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bun install

# Build the frontend
bun run build

# Run
python -m backend
```

Or use the included convenience script (creates the venv, installs deps, builds the SPA, and starts the server):

```bash
./run.sh
```

Then open <http://127.0.0.1:8765>.

### First login

A fresh `data/hearth.json` is created on first run with default credentials:

```
username: admin
password: password
```

**Change these immediately** from the Settings page.

---

## Configuration

All configuration is environment-variable driven:

| Variable          | Default       | Purpose                                              |
| ----------------- | ------------- | ---------------------------------------------------- |
| `HEARTH_HOST`     | `127.0.0.1`   | Bind address. Set to `0.0.0.0` to expose on the LAN. |
| `HEARTH_PORT`     | `8765`        | HTTP port.                                           |
| `HEARTH_DATA_DIR` | `./data`      | Where `hearth.json` and its backup live.             |

Example for a NAS install reachable across the house:

```bash
HEARTH_HOST=0.0.0.0 HEARTH_PORT=8765 HEARTH_DATA_DIR=/volume1/hearth ./run.sh
```

---

## Public.com integration (optional)

The Portfolio page works in fully manual mode if you skip this.

1. Go to your Public.com account settings and generate an API **secret**.
2. In Hearth Ledger → Settings → "Public.com API Key", paste the secret and save.
3. On the Portfolio page, click **Sync** to pull positions.

The client exchanges your secret for a short-lived access token (cached for 24 hours, auto-refreshed on 401). Only read endpoints are called — Hearth Ledger cannot place trades and has no code path that does so.

---

## Data & backup

Your books are a single file: `data/hearth.json`. To back up, copy that file. To migrate to a new machine, copy `data/` over.

A rolling backup at `data/hearth.json.bak` is rewritten on every change. For real disaster-recovery, schedule your own snapshot of `data/` to another disk or off-machine location.

---

## Development

```bash
# Backend tests
source .venv/bin/activate
python -m pytest backend/tests -q

# Frontend dev server (hot reload, proxies /api/* to the Python backend)
bun run dev

# Lint
bun run lint
```

Project layout, API surface, and architectural decisions are documented in [`mvp_structure.md`](./mvp_structure.md). The original UI brief is in [`mpv_prompt.md`](./mpv_prompt.md).

---

## Security notes

Hearth Ledger is designed for a **trusted home network**. v1 does not:

- Encrypt data at rest (relies on filesystem permissions).
- Support TLS directly (put it behind a reverse proxy — Caddy, nginx, or Tailscale Funnel — if you expose it beyond localhost).
- Support multiple users with separate logins (one shared family password by design).

If you bind to `0.0.0.0`, only do so on a network you control, and put a reverse proxy with HTTPS in front.

---

## Roadmap

Things deferred past v1 and likely candidates for v1.1:

- Historical portfolio time series → enables a real Portfolio line chart and non-zero Sharpe / volatility.
- Planning calendar Add / Edit UI (events are read-only in v1).
- Richer PDF report (charts, multi-column layout).
- Frontend bundle code-splitting.
- Optional encryption-at-rest for `hearth.json`.

---

## License

TBD — add your preferred license here before publishing.
