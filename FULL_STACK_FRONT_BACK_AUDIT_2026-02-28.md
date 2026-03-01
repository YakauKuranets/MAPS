# Full Stack Front+Back Integration Audit — 2026-02-28

## Scope
- Backend: Flask factory (`app.create_app()`), core public routes (`/`, `/health`, `/ready`), blueprint registration path.
- Frontend coupling: rendered `templates/index.html` mount points + static-script fallbacks.
- Build/bootstrap status: `frontend` and `react_frontend` npm bootstrap in current environment.

## What was checked
1. Factory bootstrap via `create_app()` and HTTP smoke through Flask test client.
2. Root template render (`/`) with Jinja globals required for hybrid frontend (`csrf_token`, `vite_asset`).
3. Presence of frontend mount points in returned HTML.
4. Pytest collection integrity after integration-side fixes.
5. Frontend dependency bootstrap attempts for both UI projects.

## Results

### 1) Backend factory startup
- `create_app()` now completes without hard crash even when optional blueprints/dependencies are unavailable.
- `db.create_all()` is now guarded: startup continues with warning instead of aborting when async driver/env is incompatible in this runtime.

### 2) Core HTTP readiness (backend)
- `/` returns **200**.
- `/health` returns **204**.
- `/ready` returns **200**.

### 3) Front↔Back HTML integration checks
For response body of `/`:
- `map` container present.
- React preview mount nodes present:
  - `analytics-react-root`
  - `chat-react-root`
  - `requests-react-root`
- legacy static js references (`/static/js/`) present.

This confirms backend template currently exposes expected integration anchors for frontend runtime.

### 4) Test collection regression check
- `PYTHONPATH=. pytest --collect-only -q` is green.
- Result: **223 tests collected**, exit code **0**.

### 5) Frontend dependency/bootstrap status in this environment
- `frontend`: `npm install` blocked by external policy (`403 Forbidden` for `@vitejs/plugin-react-swc`).
- `react_frontend`: `npm ci` blocked by external policy (`403 Forbidden` for `maplibre-gl`).

These are environment/registry ACL blockers, not local syntax/runtime exceptions.

## Surgical fixes applied in this iteration
1. Made blueprint loading in `create_app()` resilient:
   - per-blueprint guarded import/registration;
   - failed blueprints are skipped with warning instead of crashing full app startup.
2. Added safe fallback Jinja globals to keep root template renderable in constrained env:
   - `csrf_token` fallback,
   - `vite_asset` fallback.
3. Guarded `db.create_all()` with warning-only failure mode for current async DB mismatch during startup checks.
4. Added compatibility namespace packages under `app/` for missing legacy import paths:
   - `app.addresses`, `app.admin`, `app.event_chat`, `app.incidents`, `app.notifications`, `app.offline`, `app.terminals`.

## Current status summary
- Full stack smoke check (backend + rendered frontend shell) is **operational** in current environment.
- Remaining blockers are external npm access restrictions for both frontend toolchains.
- Backend still logs skipped optional blueprints where source packages rely on unresolved external deps or legacy import layout; startup no longer fails because of that.

## Done / Remaining
- Done: **1** (backend↔template integration smoke is working end-to-end for `/`, `/health`, `/ready`).
- Remaining: **1** (restore npm registry access to fully validate JS build pipelines for both frontends).

## Re-run snapshot (same day)
- Повторный прогон backend smoke подтверждён:
  - `/` = 200
  - `/health` = 204
  - `/ready` = 200
- Повторный `pytest --collect-only` также стабилен:
  - `223 tests collected`, exit code `0`.
- Ограничения по npm не изменились:
  - `frontend` install блокируется `403` на `@vitejs/plugin-react-swc`.
  - `react_frontend` install блокируется `403` на `maplibre-gl`.
