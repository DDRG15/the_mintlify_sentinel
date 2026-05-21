# The Mintlify Sentinel — Roadmap

> Last updated: 2026-05-21
> Current version: v1.3 (version history)

---

## What's Shipped (v1.0 → v1.1)

| Feature | Status |
|---------|--------|
| Core 4-stage pipeline | ✅ Done |
| CLI with argparse | ✅ Done |
| Severity ladder: CRITICAL / MEDIUM / LOW | ✅ Done |
| Slack + Discord webhook notifications | ✅ Done |
| Streamlit browser UI (all 4 phases) | ✅ Done |
| Docker support | ✅ Done |
| GitHub Actions CI | ✅ Done |
| 95 tests (judge_config, judge_diff, architect_render, notifier) | ✅ Done |
| YAML OpenAPI spec support | ✅ Done |
| Schema drift detection (SCHEMA_DRIFT — MEDIUM) | ✅ Done |
| Granular schema diff (field-level: added/removed/type/required) | ✅ Done |

---

## Next to Build

### ~~Priority 1 — Granular schema diff (v1.2)~~ ✅ SHIPPED

Field-level diff is live. SCHEMA_DRIFT findings now include `response_schema_changes` and `request_body_schema_changes` lists with per-field entries: `field_added`, `field_removed`, `type_changed`, `became_required`, `became_optional`. The MDX changelog renders a sub-list of changed fields inside the `<Warning>` callout.

---

### ~~Priority 2 — Version history (v1.3)~~ ✅ SHIPPED

History tracking is live. Every pipeline run (CLI and UI) is appended to `output/history.json`. The Streamlit UI has a new **History** tab: summary metrics, a full runs table, and a drill-down selectbox to review findings from any past run.

---

### Priority 3 — GitHub push and CI badge (v1.1 polish)

**What:** Push the repo to GitHub (public or private). Add a CI badge to README.md showing the test run status.

**Why it matters:** Right now the GitHub Actions workflow exists but has never run. Pushing activates it. The badge makes the project look production-grade at a glance.

**Steps:**
1. Create repo at github.com (no webhook URLs in any tracked file — safe to push)
2. `git remote add origin https://github.com/DDRG15/the-mintlify-sentinel.git`
3. `git push -u origin main`
4. Add badge to README.md: `![CI](https://github.com/DDRG15/the-mintlify-sentinel/actions/workflows/sentinel.yml/badge.svg)`

**Estimated effort:** 15 minutes

---

### Priority 4 — React frontend (future, when client-facing)

**What:** Replace the Streamlit UI with a React + FastAPI frontend for client-facing use (demos, sales, investor presentations).

**Why it matters:** Streamlit is the right internal tool. React is the right product. The Python backend does not change at all — React calls a FastAPI wrapper instead of Python directly.

**Where to build it:**
- `api.py` (new) — FastAPI: `POST /run` accepts two files, returns findings JSON
- `frontend/` (new) — React app: calls `/run`, renders finding cards
- `Dockerfile` updates — build React, serve via FastAPI

**Estimated effort:** 2–3 days

---

### Priority 5 — Mintlify native integration (future)

**What:** A Mintlify app extension that runs the Sentinel automatically on every docs deployment — no separate CI step required.

**Why it matters:** Zero-friction for Mintlify users. The Sentinel becomes a native part of the Mintlify publish flow rather than a separate tool that needs to be wired up.

**Dependency:** Mintlify's app extension SDK (not yet public). Track at: https://mintlify.com/docs

**Estimated effort:** Unknown — depends on Mintlify's extension model

---

## Not Building (Intentional Non-Goals)

| Item | Reason |
|------|--------|
| PDF changelog | `architect_pdf.py` exists as a utility but WeasyPrint requires native system libs that aren't available on Windows. Not in the main pipeline. Use MDX for production. |
| Database for history | SQLite or Postgres adds operational complexity. A flat `history.json` file is sufficient until the product scales. |
| Auth / multi-user | Not applicable until the product is client-facing. React + FastAPI is the trigger for adding auth. |
| OpenAPI 2.x (Swagger) support | OpenAPI 3.x is the current standard. Adding 2.x support requires a format-conversion layer. Low ROI. |
