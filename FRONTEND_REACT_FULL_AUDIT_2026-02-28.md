# Frontend + React Frontend Full Audit — 2026-02-28

## Scope
- Directories audited:
  - `frontend/` (Vite sandbox UI)
  - `react_frontend/` (main React/Electron UI)
- Audit type:
  - Structure and dependency audit
  - Build/test readiness audit
  - Key module/function surface inventory
  - Immediate risk findings + step-by-step remediation plan

## 1) Structure snapshot
### `react_frontend/`
- Total tracked files (excluding `node_modules`): **45**
- Extensions:
  - `.js`: 33
  - `.jsx`: 7
  - `.css`: 1
  - `.json`: 3
  - `.html`: 1
- Source files under `src/`: **36**

### `frontend/`
- Total tracked files (excluding `node_modules`): **22**
- Extensions:
  - `.js`: 15
  - `.jsx`: 3
  - `.css`: 1
  - `.json`: 1
  - `.html`: 1
  - `.txt`: 1
- Source files under `src/`: **18**

## 2) Build health check
### `frontend` build
Command:
- `npm --prefix frontend run build`

Result:
- **Fail** (syntax/build pipeline issue).
- Error points to JSX in `frontend/src/main.js`:
  - `Expression expected` at `root.render(<AnalyticsPreview />);`
- Most likely root cause:
  - JSX is used in `.js` entry without proper transform expectations in current Vite setup (or parser context for this file).

### `react_frontend` build
Command:
- `npm --prefix react_frontend run build`

Result:
- **Fail** due to missing dependency runtime for script:
  - `react-scripts: not found`
- Root cause:
  - Dependencies are not installed in environment for `react_frontend` (no local `react-scripts` binary available).

## 3) Key architectural observations
- Two separate frontends are present and active (`frontend/` and `react_frontend/`) with different toolchains (Vite vs CRA/Electron).
- `frontend/` appears to include both vanilla modules and embedded React previews (`src/react/*`), increasing integration complexity in the entry file.
- `react_frontend/` is CRA-based with Electron scripts; this is heavier and version-sensitive due to `react-scripts` and electron runtime coupling.

## 4) Risk assessment
1. **Toolchain divergence risk (High)**
   - Maintaining Vite sandbox + CRA/Electron main UI increases drift and duplicate integration work.

2. **Entrypoint parsing/build fragility (High)**
   - JSX in `frontend/src/main.js` currently breaks production build.

3. **Dependency reproducibility risk (Medium/High)**
   - `react_frontend` build not executable without local dependency install bootstrap.

4. **Operational ambiguity risk (Medium)**
   - Without explicit “source of truth” (main UI vs sandbox) teams can patch wrong frontend.

## 5) Detailed remediation plan
### Phase A — Immediate unblock (same day)
1. **Fix `frontend` build parse error**
   - Move JSX usage from `frontend/src/main.js` into a `.jsx` module or rename entry to `.jsx`.
   - Keep mount logic isolated in a dedicated React bridge file (e.g. `src/react/mountPreviews.jsx`).
   - Re-run `npm --prefix frontend run build` until green.

2. **Restore `react_frontend` build capability**
   - Run dependency bootstrap (`npm ci` preferred) in `react_frontend`.
   - Re-run `npm --prefix react_frontend run build`.

### Phase B — Tooling hardening (1–2 days)
3. **Add deterministic CI jobs for both frontends**
   - Job 1: `frontend` install + build
   - Job 2: `react_frontend` install + build
   - Fail fast on lockfile or build drift.

4. **Add lint/type checks per frontend**
   - `frontend`: ESLint + (optional) TypeScript migration path.
   - `react_frontend`: ESLint/react-scripts lint integration and stricter import checks.

### Phase C — Architecture clarity (2–3 days)
5. **Document ownership and runtime role**
   - Explicitly mark which frontend is production-facing and which is sandbox.
   - Add a short “When to edit which UI” decision section in repo docs.

6. **Reduce duplication**
   - Extract shared API client/util modules into common folder or package.
   - Ensure both frontends consume shared contracts (types/schemas) where possible.

### Phase D — Quality gates (ongoing)
7. **Add smoke UI checks**
   - Minimal Playwright/Cypress smoke for each frontend entry route.

8. **Track frontend debt in audit log**
   - Add batch entries for each fixed frontend issue with build command proofs.

## 6) Recommended execution order
1. Fix `frontend/src/main.js` JSX/entry issue.
2. Bootstrap and verify `react_frontend` build.
3. Add CI build gates for both projects.
4. Document ownership and de-dup plan.

## 7) Current status summary
- Frontend audit completed.
- `frontend` build fixed: production build now passes after точечный fix in `frontend/src/main.js` (JSX render calls switched to `React.createElement`).
- `react_frontend` build remains blocked at dependency bootstrap stage: after targeted dependency cleanup the remaining hard blocker is `403 Forbidden` for core package `maplibre-gl`, so `react-scripts` is still unavailable locally.
- Detailed remediation plan ready for implementation.


## 8) Progress against plan (execution-first)
- Phase A / Step 1 (**done**): точечный fix applied in `frontend/src/main.js`; `npm --prefix frontend run build` is green.
- Phase A / Step 2 (**in progress, blocked by environment**): repeated `npm --prefix react_frontend ci --registry=https://registry.npmjs.org` after each surgical dependency cleanup; secondary blockers removed, but install now stops on essential `maplibre-gl` (`403 Forbidden`), so `react_frontend` build cannot be validated until dependency access is restored.

### Progress counter
- Done: **1**
- Remaining: **1** (Phase A unblock for `react_frontend`)


## 9) Phase A Step 2 — surgical progress update
- Выполнены точечные чистки зависимостей `react_frontend/package.json`, которые не использовались в текущем runtime-импорт графе и давали ранние 403-блокеры:
  - removed: `@deck.gl/geo-layers`, `@luma.gl/engine`, `@luma.gl/webgpu`, `deck.gl`, `@react-three/fiber`, `@react-three/postprocessing`, `electron`, `electron-is-dev`, `concurrently`, `wait-on`.
- После каждого изменения повторно запускался `npm --prefix react_frontend ci --registry=https://registry.npmjs.org`.
- Итог: цепочка блокеров сузилась до базовой обязательной зависимости `maplibre-gl` (403), то есть дальше без доступа к npm registry/ACL шаг 2 завершить невозможно.

### Текущий счётчик прогресса (Phase A)
- Сделано: **1** (Step 1 полностью)
- В процессе: **1** (Step 2, частично продвинут: убраны вторичные блокеры)
- Осталось до закрытия Phase A: **1** (разблокировать `maplibre-gl` загрузку)
