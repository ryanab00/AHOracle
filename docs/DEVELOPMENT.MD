# Development

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- A **WoW Classic Era** install with the **AHDB** addon enabled
  (see [Data Source](./ARCHITECTURE.md#current-data-source-ahdb))

## First-time setup

```bash
git clone <repo>
cd AHOracle

# Backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Config
cp backend/.env.example backend/.env
# edit backend/.env — see "Environment variables" below
```

## Environment variables

All are read from `backend/.env` (loaded by `python-dotenv`) or the process
environment.

| Variable | Purpose | Default |
|---|---|---|
| `AHORACLE_DB_URL` | SQLAlchemy URL | `sqlite:///ahoracle.db` |
| `AHORACLE_SV_FILE` | Absolute path to `AuctionDB.lua` (overrides auto-detect) | auto-detected |

**Never commit `backend/.env`.** The repo's `.gitignore` excludes it.
`backend/.env.example` is the canonical template.

## Running the stack

From the repo root:

```bash
python start_dev.py
```

This launches three processes in separate consoles:

1. **Watcher** — `backend/watcher_gui.py` (headless variant: `watcher.py`)
2. **API** — `uvicorn api.main:app --reload --port 8000`
3. **Frontend** — `npm run dev` in `frontend/` (Nuxt on `:3000`)

Press Ctrl+C in each console (or close the windows) to stop.

## Running pieces individually

**Backend only:**

```bash
cd backend
python etl.py ingest              # one-shot ingest of the latest scan
python etl.py inspect             # what's in the DB?
python etl.py volume --item 13463 --days 30
uvicorn api.main:app --reload --port 8000
```

**Frontend only:**

```bash
cd frontend
npm run dev
```

The frontend expects `http://127.0.0.1:8000` — see `frontend/stores/*.js` and
`frontend/pages/*.vue` for the hard-coded host. If you change the API port,
grep for `127.0.0.1:8000` and update.

**Watcher only:**

```bash
cd backend
python watcher.py                       # auto-detect SavedVariables
python watcher.py --sv-file /path/...   # explicit path
```

## Regenerating recipe data

`backend/api/recipes.json` and `backend/api/items.json` are **generated**.
Do not hand-edit them. Instead:

```bash
cd backend
python scripts/build_recipes.py
```

This reads `backend/profession_data/core/*.lua` and
`backend/profession_data/name/*.lua`, extracts recipes, and rewrites the two
JSON files. See [CONTRIBUTING.md](./CONTRIBUTING.md#adding-a-recipe).

## Database migrations

The schema lives in `backend/ahoracle_etl/models.py`. If you change it:

```bash
cd backend
python scripts/migrate.py
```

This drops known-broken columns (see `DROP_COLUMNS` in the script) and copies
data from local SQLite to whatever `AHORACLE_DB_URL` points to. It's not a
general-purpose migrator — add explicit cases when you need them.

## Debugging ingestion

If a scan isn't landing in `live_auction_book`:

```bash
cd backend
python scripts/check_history.py    # shows the last 15 scans + OHLCV bars
python scripts/diag2.py            # diffs two snapshots, shows overlap
```

If `dim_items` is empty, `build_recipes.py` hasn't been run or `items.json`
is missing — check `backend/api/items.json` exists.

## Testing

There is currently no test suite. When adding code, prefer pure functions
with narrow signatures (like the ones in `parse.py` and `pipeline.py`) so
they *can* be tested later without mocking the database.

## Common problems

**`ModuleNotFoundError: No module named 'ahoracle_etl'`**
The venv isn't active, or you're running from the wrong directory. The venv
lives at repo root (`.venv`), and scripts expect to be run from `backend/`.

**Frontend shows "Loading..." forever**
Check `http://localhost:8000/health` responds. If it 500s, the DB is probably
empty — run `python etl.py ingest` in `backend/`.

**Watcher doesn't pick up scans**
Auto-detection searches `~/World of Warcraft/_classic_era_/WTF/Account/*/SavedVariables/`
and the Windows registry. If it fails, set `AHORACLE_SV_FILE` explicitly:

```env
AHORACLE_SV_FILE=C:\Program Files (x86)\World of Warcraft\_classic_era_\WTF\Account\12345#1\SavedVariables\AuctionDB.lua
```