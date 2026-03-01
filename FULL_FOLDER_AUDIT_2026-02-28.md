# Full Folder-by-Folder Audit (Repeat #2) — 2026-02-28

## Scope and method
- Per-request repeated full project audit by folders with module/function verification.
- Ran structural presence checks, AST parse inventory, lint sweeps, byte-compile validation, and pytest collection.

## Architecture mapping (requested vs observed)
Requested runtime topology:
- Browser -> Flask `run.py` (`:5000`) <-> PostgreSQL (`:5432`)
- React (`:3000`) -> WebSocket (`:8765`) <-> Redis (`:6379`)
- Android Tracker -> Telegram bot (`bot.py`), Tor Proxy (`:9050`)

Observed in repository snapshot:
- Entrypoints/config present: `run.py`, `wsgi.py`, `bot.py`, `worker.py`, `Dockerfile`, `docker-compose.dev.yml`, `docker-compose.prod.yml`, `requirements.txt`, `alembic.ini`.
- Frontend folders present: `react_frontend/` and `frontend/`.

## Folder-by-folder inventory
AST/module inventory for current snapshot:
- Python files discovered/parsible in audit scope: all parsed successfully (no parse failures in scanned files).

Requested structure presence and inventory:
- `app/`: present, 145 files / 142 `.py` / 594 functions / 119 classes.
- `react_frontend/`: present, 45 files.
- `frontend/`: present, 332 files.
- `android/`: present, 108 files.
- `templates/`: present, 13 files.
- `static/`: present, 57 files.
- `k8s/`: present, 12 files.
- `tests/`: present, 53 files / 53 `.py` / 325 functions / 61 classes.
- Top-level runtime/config files listed above: present.

## Verification checks
1) Full Ruff sweep
- `ruff check . --output-format concise`
- Result: pass.

2) Maintained lint gate
- `ruff check . --select E501,E402,F401,F821,E722,E701,E702,F841 --output-format concise`
- Result: pass (`E501` remains zero).

3) Byte-compile
- `python -m compileall -q app tests run.py wsgi.py bot.py worker.py`
- Result: pass.

4) Pytest collection
- `PYTHONPATH=. pytest --collect-only -q`
- Result: pass; `223 tests collected`.
- Note: warning remains for unknown `pytest.mark.asyncio` in `tests/test_master_e2e_smoke.py`.

## Conclusion
- Repeat full folder-by-folder audit completed successfully.
- Structure/entrypoints match requested architecture map at repository level.
- Lint and compile checks are green; pytest collection is stabilized and successful.

## Recommended follow-up
- Optional: register `asyncio` marker in pytest configuration to eliminate collection warnings.
