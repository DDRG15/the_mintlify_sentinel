# The Mintlify Sentinel

Breaking API changes reach production silently. A developer on a Friday afternoon traces an error back to your last release, finds an endpoint that no longer exists, and files a ticket — or just stops integrating. The Sentinel makes that scenario impossible: it runs at pipeline time, compares your API specs before anything ships, and renders a publishable Mintlify changelog that your users see before they're impacted.

This is not a diff tool that dumps JSON to a terminal. It is an audit pipeline with a rendered output. The report is a documentation page, not a log file.

---

## Legal Disclaimer and Take-Down Notice

This is an unofficial, non-commercial, educational project.

1. **No Affiliation.** This repository and its creator are not affiliated with, endorsed by, sponsored by, or associated with Mintlify in any way.

2. **Educational Purpose.** This codebase was built as a personal proof-of-concept to practice DevSecOps, containerization, Python scripting, and OpenAPI semantic diffing. The test fixtures used in this repository — `input/admin-openapi.json` and `input/analytics.openapi.json` — are Mintlify's publicly published API specifications, sourced from the `mintlify/docs` repository. The `docs.json` configuration follows the structure of Mintlify's publicly available starter kit. This project has absolutely zero commercial value.

3. **License Compliance.** All Mintlify materials used as test fixtures in this project originate from MIT-licensed public repositories (`mintlify/docs`, `mintlify/starter`). The MIT license permits use, reproduction, and distribution. This project complies with those terms.

4. **Take-Down Request.** If you are an authorized representative of Mintlify and wish for this repository to be modified or deleted, please open an Issue in this repository and I will comply immediately.

---

## How It Works

Four stages. One entry point. Ten seconds.

```
docs.json ──────────────────────► judge_config.py   Stage 1: config validation (hard gate)
                                                           │
baseline-openapi.json ──┐                                  ▼
                        ├──────► judge_diff.py      Stage 2: semantic diff (CRITICAL/MEDIUM/LOW)
target-openapi.json  ───┘                                  │
                                                           ▼
                                   architect_render.py   Stage 3: MDX changelog generation
                                                           │
                                                           ▼
                                        output/changelog.mdx   → commit to docs repo
```

**Stage 1** validates `docs.json` against the Mintlify schema using Pydantic v2. A structurally invalid config destroys a Mintlify site build. This stage exits `1` immediately so you don't spend time debugging a diff whose output will never render.

**Stage 2** runs a two-phase semantic diff. Phase 1 computes set difference: every endpoint in V1 that is absent from V2 is CRITICAL. Phase 2 computes intersection analysis: surviving endpoints are checked for parameter changes (MEDIUM) and documentation drift (LOW). One finding per endpoint. MEDIUM suppresses LOW for the same signature.

**Stage 3** renders the findings list through a Jinja2 template into a Mintlify-native MDX file. CRITICAL findings become `<Danger>` callouts. MEDIUM becomes `<Warning>`. LOW becomes `<Info>`. Copy the file to your docs repo and push — it renders natively.

**Stage 4** is the audit gate. It always exits `0`. The Sentinel surfaces findings; it does not block deployments. That decision belongs to the engineer who reads the report.

---

## Severity Ladder

| Level | What Happened | Who Breaks | Mintlify Callout |
|-------|--------------|------------|-----------------|
| CRITICAL | Endpoint deleted | Every client calling that route | `<Danger>` |
| MEDIUM | Parameters changed | Clients using removed or renamed params | `<Warning>` |
| MEDIUM | Response or request body schema changed (field added/removed, type changed, required promotion) | Clients relying on the previous data shape | `<Warning>` |
| LOW | Summary or description text changed | Nobody — zero runtime impact | `<Info>` |

---

## Setup

```bash
# Python 3.10+ required
pip install -r requirements.txt
```

---

## Browser UI

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Upload two OpenAPI specs, click **Run Sentinel**, and see findings as colored cards. Slack and Discord webhook URLs can be entered in the sidebar — notifications fire automatically after each run. A second tab runs the docs.json validator in isolation. A third **History** tab shows every past run with a drill-down into findings. A collapsible pipeline log shows the full stage output after each run.

---

## Running the Pipeline

```bash
# Default — uses input/admin-openapi.json vs input/analytics.openapi.json
python main.py

# Explicit paths
python main.py --baseline path/to/v1.json --target path/to/v2.json --config path/to/docs.json

# With Slack and/or Discord notifications
python main.py --slack-webhook https://hooks.slack.com/services/... --discord-webhook https://discord.com/api/webhooks/...

# Show all flags
python main.py --help
```

The rendered changelog is written to `output/changelog.mdx`.

Webhook URLs can also be supplied via environment variables:

```bash
# Linux / macOS
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Windows PowerShell
$env:SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

python main.py
```

Copy `.env.example` to `.env` and fill in the placeholders to persist them locally. `.env` is listed in `.gitignore` and will never be committed.

---

## Exit Codes

| Code | When |
|------|------|
| `0` | Always — including when findings are detected (audit mode) |
| `1` | `docs.json` failed structural validation |

---

## Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=scripts --cov-report=term-missing
```

106 tests across 4 modules: `test_judge_config`, `test_judge_diff`, `test_architect_render`, `test_notifier`. Covers all three severity tiers, edge cases (empty spec, malformed JSON, vendor extension keys), webhook HTTP success/failure paths, field-level schema diff assertions, SCHEMA_DRIFT callout rendering, and integration tests against the real fixture files. A session fixture in `conftest.py` preserves `output/changelog.mdx` across test runs.

---

## Docker

```bash
# Build
docker build -t mintlify-sentinel .

# Run pipeline (default)
docker run --rm mintlify-sentinel

# Mount your own specs and retrieve output
docker run --rm \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  mintlify-sentinel

# Run the browser UI
docker run --rm -p 8501:8501 mintlify-sentinel streamlit run app.py --server.address 0.0.0.0
```

---

## Running Individual Stages

```bash
python scripts/judge_config.py          # validate docs.json only
python scripts/judge_diff.py            # diff engine, test harness mode
python scripts/architect_render.py      # render changelog from last diff
```

---

## Project Structure

```
the_mintlify_sentinel/
  main.py                         Master orchestrator (CLI entry point)
  app.py                          Streamlit browser UI
  docs.json                       Mintlify site config (follows mintlify/starter structure)
  requirements.txt                Pinned Python dependencies
  Dockerfile
  .dockerignore
  .gitignore
  .gitattributes                  LF line ending normalization
  .env.example                    Webhook URL template (copy to .env)
  input/
    admin-openapi.json            Mintlify Admin API spec — baseline fixture (source: mintlify/docs)
    analytics.openapi.json        Mintlify Analytics API spec — target fixture (source: mintlify/docs)
  output/
    changelog.mdx                 Generated MDX changelog
  scripts/
    judge_config.py               Stage 1: docs.json validator (Pydantic v2)
    judge_diff.py                 Stage 2: semantic diff engine
    architect_render.py           Stage 3: Jinja2 MDX renderer
    notifier.py                   Slack + Discord webhook dispatcher
    historian.py                  Run history store (output/history.json)
  templates/
    changelog.mdx.jinja           Jinja2 template
  tests/
    conftest.py                   Session fixture — preserves output/changelog.mdx across test runs
    test_judge_config.py
    test_judge_diff.py
    test_architect_render.py
    test_notifier.py
  docs/
    ROADMAP.md                    Feature roadmap
  .github/
    workflows/
      sentinel.yml                CI: test → pipeline → artifact upload
```

---

## Known Limitations

**`weasyprint` on Windows** requires Cairo and Pango native libraries not available by default. Run inside Docker if PDF output is needed on a Windows machine.
