# Desktop FastAPI + HTMX + pywebview

Local desktop shell: FastAPI serves HTML on loopback, HTMX swaps partials, pywebview wraps the UI.

## Quick path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python run_desktop.py
```

Browser-only:

```bash
uvicorn app.main:app --reload --port 8765
```

Open `http://127.0.0.1:8765`.

## Details

| Topic | Where |
|-------|--------|
| App name | `APP_NAME` / `APP_ID` in `.env` |
| UI | `templates/html/`, `templates/html/partials/` |
| QC | `templates/qc/` |
| Routes | `app/api/v1/` — copy `demo/` |
| Services | `app/services/` — copy `demo.py` |
| Database | stdlib `sqlite3` — `data/app.db` next to the .exe (or repo in dev) |
| Paths | `resource_root()` = bundled files (`_MEIPASS` when frozen); `writable_root()` = folder next to the binary |
| Desktop window | `run_desktop.py` |

## Checklist

- [ ] `pytest -q` is green
- [ ] Desktop window (or browser) loads the home page
- [ ] Ping swaps the HTMX partial without a full reload
