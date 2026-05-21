# The Mintlify Sentinel — Roadmap

> Last updated: 2026-05-21
> Current version: v1.1 (post-YAML + schema drift)

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
| 74 tests (judge_config, judge_diff, architect_render, notifier) | ✅ Done |
| YAML OpenAPI spec support | ✅ Done |
| Schema drift detection (SCHEMA_DRIFT — MEDIUM) | ✅ Done |

---

## Next to Build

### Priority 1 — Granular schema diff (v1.2)

**What:** Instead of "response schema changed", tell the developer *exactly* what changed:
- Which fields were added / removed
- Which field types changed (`string` → `integer`)
- Which fields became required

**Why it matters:** The current SCHEMA_DRIFT finding says "the response schema changed" — useful, but not actionable on its own. A developer still has to open both specs to know what changed. Granular output makes the finding self-contained.

**Where to build it:**
- `scripts/judge_diff.py` — replace the serialised-diff check in Rule C with a recursive property-level walker
- `templates/changelog.mdx.jinja` — add a sub-list of changed fields inside the `<Warning>` callout
- `tests/test_judge_diff.py` — add field-level assertions

**Estimated effort:** 3–4 hours

---

### Priority 2 — Version history (v1.3)

**What:** Track and store diff results across multiple release pairs. Surface trends: which endpoints change most often, which are stable, how many findings per release.

**Why it matters:** The current tool is stateless — each run is independent. Version history turns it into a continuous monitoring tool rather than a point-in-time check.

**Where to build it:**
- `scripts/historian.py` (new) — append findings to a JSON or SQLite store keyed by timestamp + spec pair
- `app.py` — add a "History" tab showing a table of past runs
- `output/history.json` (new) — flat file store (no database dependency)

**Estimated effort:** 1 day

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
