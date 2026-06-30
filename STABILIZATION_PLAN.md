# SecAudit Stabilization Plan

## Decision

Stop adding product features temporarily. Stabilize the current workflow first.

The recent bugs are not isolated defects. They come from weak boundaries between frontend state, backend persistence, long-running jobs, and UI rendering.

## Root Causes

| Area | Current Problem | Impact |
| --- | --- | --- |
| Frontend state | `static/js/main.js` is a large global-state file using `S.*`, inline `onclick`, and manual DOM render paths | Easy to miss one state branch; UI can show stale project/framework/job state |
| Backend state | SQLite persistence, schema migration, job lifecycle, project CRUD, question merge, findings persistence are spread across a large `db.py` | Behavior changes are hard to reason about and test in isolation |
| Long-running jobs | Jobs run through `asyncio.create_task` inside the FastAPI process | Works for Pi MVP, but restart/cancel/retry semantics are fragile |
| LLM output | LLM is treated as if it will follow exact JSON/count requirements | Needs explicit validation, retry, and user-visible partial/error states |
| Verification | Fixes were validated manually and reactively | Regressions appeared in mobile navigation, checkbox state, module load, and job status |
| UI source of truth | Sometimes frontend state was treated as source of truth; sometimes backend project data was | User could not tell whether a framework was actually selected |

## Stabilization Success Criteria

| Area | Criteria |
| --- | --- |
| Project setup | Opening a project always shows backend-persisted framework, scope, context, responsibility level, and question count |
| Framework selection | Toggling frameworks and starting generation persists exactly the visible checkbox state |
| Question generation | If target is 5, job is not marked `done` unless 5 total questions exist or target is explicitly adjusted |
| Job visibility | Project list, record view, and report view show consistent job status after refresh |
| Report flow | Leaving and returning to report view never loses generated reports or active job state |
| Mobile | Sidebar, setup, record, report, and project list remain usable after refresh and navigation |
| Deployment | Version, static asset query strings, Pi container health, and API smoke checks are verified every time |

## Immediate Freeze Rules

Do not add new product features until these are done:

| Gate | Requirement |
| --- | --- |
| G1 | Define canonical frontend state ownership: backend project snapshot is source of truth for persisted setup fields |
| G2 | Add smoke-test script for API and static JS load checks |
| G3 | Add manual mobile regression checklist to README or docs |
| G4 | Split frontend code by domain or at least create explicit render/load helpers for setup, record, report, projects |
| G5 | Add backend consistency checks around job completion and target counts |

Status as of `2026.06.29.25`:

| Gate | Status |
| --- | --- |
| G1 | Partially complete: setup fields hydrate from backend; framework payload is read from visible checkbox DOM before save |
| G2 | Complete: `smoke_check.ps1` covers local syntax, version consistency, critical frontend hooks, static browser wiring, optional Pi/API checks |
| G3 | Complete: manual browser checks are documented below |
| G4 | Partially complete: `static/js/ui.js` owns shared UI helpers; `static/js/projects.js` owns project list/open/create/delete and job badge rendering |
| G5 | Partially complete: question jobs no longer mark `done` when total questions are below target |

## Short-Term Work Plan

| Priority | Work | Reason |
| --- | --- | --- |
| P0 | Build `smoke_check.ps1` | Done |
| P0 | Add backend smoke checks for selected project: project fields, framework count, question count, job status | Done; use `-Pi -ApiKey ... -ProjectId ...` |
| P0 | Normalize setup state flow: `load project -> hydrate form -> render frameworks -> sync DOM before save` | Partially done; module split still pending |
| P1 | Add job completion invariant: `done` only if count/expected condition is satisfied | Prevent false success |
| P1 | Add job badge start time / elapsed visibility | Done; project list badges show elapsed time and tooltip details |
| P1 | Add UI warning when LLM returns fewer questions than requested | Done; record view shows produced/target count and retry/manual-add actions |
| P1 | Add Playwright or lightweight browser automation for module load + click smoke test | Done as static browser wiring checks; can later upgrade to real browser click automation |
| P2 | Split `static/js/main.js` into modules: projects, setup, record, report, admin | In progress: `ui.js` and `projects.js` extracted; continue one domain at a time after smoke checks |
| P2 | Add framework ingestion pipeline v1 | Done: upload now produces markdown preview, diagnostics, scanned-PDF warning, and extracted controls |
| P2 | Split `db.py` into project/question/job/finding/framework persistence modules | Reduce hidden coupling and large-file edits |
| P2 | Introduce formal job runner abstraction | Makes cancel/retry/restart semantics explicit |

## Minimum Deployment Checklist

Run before deploying to Pi:

```powershell
powershell -ExecutionPolicy Bypass -File .\smoke_check.ps1
```

After deploying to Pi:

```powershell
ssh pi@192.168.88.115 "cd /home/pi/secaudit && docker compose up -d --build secaudit"
ssh pi@192.168.88.115 "curl -fsS http://127.0.0.1:18000/api/version && echo"
ssh pi@192.168.88.115 "docker ps --filter name=secaudit --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'"
ssh pi@192.168.88.115 "docker logs --tail 50 secaudit"
```

Optional authenticated Pi/API smoke:

```powershell
$env:SECAUDIT_API_KEY="<local secret>"
powershell -ExecutionPolicy Bypass -File .\smoke_check.ps1 -Pi -ProjectId "<project id>"
```

Manual browser checks:

| Flow | Expected Result |
| --- | --- |
| Load homepage | Sidebar version matches API version; buttons work |
| Open existing project | Setup form and framework checkboxes match backend project |
| Add one framework and generate | Backend project `frameworks` includes selected framework |
| Generate 5 questions | Job does not show done unless total questions reach 5 |
| Navigate away during job | Project list shows running badge; returning resumes polling |
| Generate report and leave page | Report job remains visible; completed report loads from DB |

## Recommended Refactor Boundary

Do not rewrite the whole app at once. Use staged stabilization.

| Stage | Scope |
| --- | --- |
| 1 | Keep current UI, add smoke checks and state invariants |
| 2 | Extract frontend modules without changing UX |
| 3 | Extract DB modules without changing schema |
| 4 | Add browser/API automated regression tests |
| 5 | Replace in-process background jobs only if operational need justifies it |

## Current Known Risks

| Risk | Severity | Notes |
| --- | --- | --- |
| `main.js` remains too large | High | New features can break unrelated UI |
| Inline `onclick` handlers | Medium | One module syntax error disables all buttons |
| LLM exact count is not guaranteed | High | Must rely on validation/retry/error states |
| Job runner is in-process | Medium | Pi restart interrupts jobs |
| No automated browser regression | High | Mobile/UI regressions are found by the user instead of predeploy checks |
