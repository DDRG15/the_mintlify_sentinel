# Streamlit UI — Implementation Plan

## Why Streamlit First

The pipeline already works. The data contract is clean: two files in, a findings list out.
Streamlit wraps that in a browser window without touching any existing code.
When the product is ready to face clients, React replaces the frontend — the Python backend stays identical.

---

## What the UI Does

A user opens the browser, uploads two OpenAPI spec files, clicks Run, and sees the findings
displayed as colored cards — red for CRITICAL, yellow for MEDIUM, blue for LOW.
They can download the generated `changelog.mdx` directly from the page.
If webhooks are configured, they can fire the Slack or Discord notification from the UI too.

---

## Phase 1 — Core UI (Day 1, ~3-4 hours)

**Goal:** Working browser interface that runs the full pipeline.

### Files to create
- `app.py` (project root) — the Streamlit app entry point

### What it includes
- Page title and description
- File uploader for baseline spec (V1)
- File uploader for target spec (V2)
- "Run Sentinel" button
- Results section:
  - Summary bar: X CRITICAL / Y MEDIUM / Z LOW
  - One colored card per finding (🔴 red, 🟡 yellow, 🔵 blue)
  - Clean diff message if no findings
- Download button for `output/changelog.mdx`

### Dependency to add to requirements.txt
```
streamlit==1.35.0
```

### Run command
```bash
streamlit run app.py
```

---

## Phase 2 — Webhook Integration (Day 1 or 2, ~1-2 hours)

**Goal:** Fire Slack/Discord notifications from inside the UI.

### What it adds to app.py
- Expandable sidebar section: "Notifications"
- Text input: Slack Webhook URL
- Text input: Discord Webhook URL
- "Send Notification" button (fires after pipeline runs)
- Status indicator: ✅ Sent / ❌ Failed per channel

---

## Phase 3 — docs.json Validator Panel (Day 2, ~1 hour)

**Goal:** Expose Stage 1 (judge_config.py) as a standalone UI panel.

### What it adds
- Second tab in the UI: "Validate Config"
- File uploader for docs.json
- "Validate" button
- Structured error report if validation fails
- Green success panel if it passes

---

## Phase 4 — Polish (Day 2, ~1-2 hours)

**Goal:** Make it look intentional, not like a script someone threw in a browser.

### What it includes
- Mintlify brand colors (primary green #16A34A)
- Custom page icon (favicon)
- Sidebar with project info and links
- Spinner while pipeline runs ("Running Sentinel...")
- Timestamp on results ("Last run: 14:32:01")
- Collapsible raw JSON view of findings (for developers)

---

## Future — React Upgrade

When the product needs to face clients or be sold:

| Streamlit stays | React replaces |
|----------------|----------------|
| Internal dev tool | Public-facing product |
| Your own pipeline runs | Client-facing demo |
| Quick testing | Investor demo |

**Nothing in the Python backend changes.** The pipeline, the notifier, the diff engine — all identical.
React just calls the same functions through a FastAPI wrapper (one file, ~50 lines) instead of directly.

### FastAPI wrapper (when needed, ~1 day)
- `api.py` — exposes `POST /run` that accepts two files, returns findings JSON
- React calls `/run`, renders the result
- Streamlit keeps calling Python directly

---

## Full Dependency List for Streamlit Phase

Add to `requirements.txt`:
```
streamlit==1.35.0
```

No other new dependencies. Everything else (pydantic, jinja2, etc.) is already installed.

---

## Estimated Total Time

| Phase | Time |
|-------|------|
| Phase 1 — Core UI | 3-4 hours |
| Phase 2 — Webhooks | 1-2 hours |
| Phase 3 — Config validator | 1 hour |
| Phase 4 — Polish | 1-2 hours |
| **Total** | **~1.5 days** |
