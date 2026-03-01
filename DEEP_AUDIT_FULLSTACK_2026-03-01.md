# Deep Audit Report (Backend + frontend + react_frontend + Android)

Date: 2026-03-01
Scope: backend runtime/tests, `frontend`, `react_frontend`, `android/dutytracker_src/app`

## 1) Backend audit

### Commands
1. `python - <<'PY' ... create_app + test_client ... PY`
2. `PYTHONPATH=. pytest --collect-only -q`
3. `ruff check analytics app/services app/service_access app/maintenance app/video/security_audit realtime websocket tests --output-format concise`
4. `python -m compileall -q analytics app/services app/service_access app/maintenance app/video/security_audit realtime websocket tests`

### Result
- `create_app()` smoke failed in current environment: `ModuleNotFoundError: No module named 'celery'`.
- Pytest collection also failed for the same missing dependency path via `tests/conftest.py` -> `app.config`.
- Static quality gates succeeded:
  - Ruff gate: green.
  - Compile check: green.

### Conclusion
- Backend code quality gate is stable, but runtime/test bootstrap is currently blocked by missing Python dependency (`celery`) in the environment.

---

## 2) `frontend` audit (Vite)

### Commands
1. `npm --prefix frontend install --no-audit --no-fund --registry=https://registry.npmjs.org`
2. `npm --prefix frontend run build`

### Result
- Install failed with `403 Forbidden` for `@vitejs/plugin-react-swc`.
- Build failed because `vite` binary is not available (install step did not complete).

### Conclusion
- Frontend build is blocked by package registry access policy / ACL.

---

## 3) `react_frontend` audit (react-scripts)

### Commands
1. `npm --prefix react_frontend ci --registry=https://registry.npmjs.org`
2. `npm --prefix react_frontend run build`

### Result
- Install failed with `403 Forbidden` for `maplibre-gl`.
- Build failed because `react-scripts` is not available (install step did not complete).

### Conclusion
- React frontend build is blocked by package registry access policy / ACL.

---

## 4) Android audit (`android/dutytracker_src/app`)

### Commands
1. `cd android/dutytracker_src/app && ./gradlew :app:tasks`
2. `cd android/dutytracker_src/app && JAVA_HOME=/root/.local/share/mise/installs/java/17.0.2 PATH=/root/.local/share/mise/installs/java/17.0.2/bin:$PATH ./gradlew :app:tasks`
3. `cd android/dutytracker_src/app && JAVA_HOME=/root/.local/share/mise/installs/java/17.0.2 PATH=/root/.local/share/mise/installs/java/17.0.2/bin:$PATH ./gradlew :app:assembleDebug`
4. `cd android/dutytracker_src/app && JAVA_HOME=/root/.local/share/mise/installs/java/17.0.2 PATH=/root/.local/share/mise/installs/java/17.0.2/bin:$PATH ./gradlew :app:lintDebug`

### Result
- On default Java 25 environment, Gradle invocation fails early.
- After switching to JDK 17, Gradle starts, but build still fails at plugin resolution:
  - `Plugin [id: 'com.android.application', version: '8.6.0'] was not found ...`
  - indicates repository/network resolution issue for Android Gradle Plugin artifact.
- Additional finding: Unix `gradlew` in this repo is not a standard wrapper launcher; it is a shim that executes system `gradle`.

### Conclusion
- Android build path requires:
  - JDK 17,
  - reachable plugin repositories (Google/Maven Central),
  - and understanding that Unix path uses system Gradle rather than full wrapper bootstrap.

---

## Overall status

- **Backend**: partially green (lint/compile), runtime tests blocked by missing `celery`.
- **frontend (Vite)**: blocked by npm 403 on `@vitejs/plugin-react-swc`.
- **react_frontend**: blocked by npm 403 on `maplibre-gl`.
- **Android**: blocked by dependency/plugin resolution in current environment; JDK 17 is mandatory.

## Recommended next unblock actions

1. Python env: install backend runtime deps (at minimum `celery`) and re-run backend smoke + pytest collect.
2. npm registry/policy: unblock package downloads for:
   - `@vitejs/plugin-react-swc`
   - `maplibre-gl`
3. Android repositories/network: ensure access to Google + Maven Central repos and re-run:
   - `gradle :app:tasks`
   - `gradle :app:assembleDebug`
   - `gradle :app:lintDebug`
