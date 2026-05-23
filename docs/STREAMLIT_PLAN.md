# Streamlit UI — Implementation Record

> **Status: COMPLETE.** All five phases shipped. `app.py` is live at `http://localhost:8501`.

---

## What Was Built

A browser interface for the Sentinel pipeline. A user opens the page, uploads two OpenAPI spec files, clicks Run, and sees findings displayed as colored cards — red for CRITICAL, yellow for MEDIUM, blue for LOW. They can download `changelog.mdx` directly from the page, fire Slack/Discord notifications from the sidebar, validate a `docs.json` file in a separate tab, and inspect the full pipeline log in a collapsible expander.

---

## Phase 1 — Core UI ✓

- Page title and description
- File uploader for baseline spec (V1)
- File uploader for target spec (V2)
- "Run Sentinel" button (disabled until both files are uploaded)
- Results section:
  - Summary bar: Total / CRITICAL / MEDIUM / LOW metrics
  - One colored card per finding (`st.error` / `st.warning` / `st.info`)
  - Clean diff success message if no findings
- Download button for `output/changelog.mdx`

---

## Phase 2 — Webhook Integration ✓

- Sidebar: Slack Webhook URL input (password-masked)
- Sidebar: Discord Webhook URL input (password-masked)
- Notifications fire automatically after each pipeline run
- Per-channel status shown inline: ✅ Sent (HTTP 200/204) / ❌ Failed

---

## Phase 3 — docs.json Validator Panel ✓

- Second tab: "Validate Config"
- File uploader for `docs.json`
- "Validate" button runs `validate_docs_config()` in isolation
- Green success panel if valid
- Red error panel if validation fails (field-level errors printed to terminal)

---

## Phase 4 — Polish ✓

- Mintlify brand green (`#16A34A`) applied to primary button via custom CSS
- Spinner while pipeline runs ("Running Sentinel...")
- Last-run timestamp displayed above results
- Collapsible **Pipeline log** expander — shows full stdout from all 4 stages
- Collapsible **Raw JSON findings** expander — structured view for developers
- Sidebar pipeline stage table

---

## Phase 5 — Version History Tab ✓

- Third tab: "History"
- `load_history()` called on every tab render — no stale state
- Summary metrics row: total runs, total findings, total critical, clean runs
- `st.dataframe` table of all runs: timestamp, baseline, target, finding counts per tier
- `st.selectbox` drill-down: select any past run, see its finding cards
- `historian.append_run()` called in the Run Sentinel tab after each pipeline execution
- `output/history.json` gitignored — machine-local, never committed

---

## Run Command

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Also runnable in Docker:

```bash
docker run --rm -p 8501:8501 mintlify-sentinel streamlit run app.py --server.address 0.0.0.0
```

---

## Future — React Upgrade (if ever needed)

If and only if production-scale deployment is ever required, and if that need ever arises:

| Streamlit stays | React replaces |
|----------------|----------------|
| Internal dev tool | Public-facing deployment, if ever needed |
| Personal pipeline runs | Shared access, if ever required |
| Quick testing | Scale testing, if ever applicable |

**Nothing in the Python backend changes.** The pipeline, the notifier, the diff engine — all identical. React would call the same functions through a FastAPI wrapper (one file, ~50 lines) instead of directly. This is not planned or scheduled.

```python
# api.py — FastAPI wrapper (when needed)
# POST /run → accepts two files → returns findings JSON
# React calls /run, Streamlit keeps calling Python directly
```
