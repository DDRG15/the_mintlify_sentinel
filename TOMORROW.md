# Next Session

## Current state: v1.2 — shipped

Everything below is done. See `docs/ROADMAP.md` for the full priority list.

---

## Option A — Try the UI (5 min)

If you haven't opened the browser UI yet:

```bash
streamlit run app.py
```

Open http://localhost:8501, upload these two files:
- V1: `input/admin-openapi.json`
- V2: `input/analytics.openapi.json`

Expected: 6 red CRITICAL cards, download button, pipeline log expander.

---

## Option B — Push to GitHub (15 min)

The repo is clean. No webhook URLs in any tracked file. Safe to push at any time.

1. Create a new repo at github.com (public or private)
2. Add the remote and push:

```bash
git remote add origin https://github.com/DDRG15/the-mintlify-sentinel.git
git push -u origin main
```

GitHub Actions triggers automatically — runs the full 74-test suite + pipeline.

Then add the CI badge to README.md:
```
![CI](https://github.com/DDRG15/the-mintlify-sentinel/actions/workflows/sentinel.yml/badge.svg)
```

---

## Option C — Version history (Priority 2 from ROADMAP)

Track diff results across multiple runs. Surface trends: which endpoints change
most often, which are stable, how many findings per release.

Files:
- `scripts/historian.py` (new) — append findings to `output/history.json`
- `app.py` — add a "History" tab showing a table of past runs

Estimated: 1 day.

---

## Completed — v1.0 → v1.1

- [x] requirements.txt
- [x] Template bug fix (severity-conditional callouts)
- [x] argparse CLI flags
- [x] Step label fix (STEP 4/4)
- [x] Circular import fix
- [x] 74 tests — judge_config, judge_diff, architect_render, notifier
- [x] conftest.py — test isolation for output/changelog.mdx
- [x] Slack + Discord webhook notifier
- [x] README.md (GitHub, layperson, semi-tech, pitch)
- [x] Dockerfile + .dockerignore
- [x] GitHub Actions CI
- [x] .gitignore + .gitattributes + .env.example
- [x] Discord live test — HTTP 204
- [x] Slack live test — HTTP 200
- [x] Docker live test — exits 0
- [x] Streamlit UI — all 4 phases (core, webhooks, validator tab, polish)
- [x] YAML OpenAPI spec support (auto-detects by content, not extension)
- [x] Schema drift detection — SCHEMA_DRIFT MEDIUM (response + request body)
- [x] ROADMAP.md — full prioritized backlog
- [x] Granular schema diff — field-level changes in SCHEMA_DRIFT findings (v1.2, 95 tests)
