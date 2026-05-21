# The Mintlify Sentinel

Breaking API changes reach production silently. A developer on a Friday afternoon traces an error back to your last release, finds an endpoint that no longer exists, and files a ticket — or just stops integrating. The Sentinel makes that scenario impossible: it runs at pipeline time, compares your API specs before anything ships, and renders a publishable Mintlify changelog that your users see before they're impacted.

This is not a diff tool that dumps JSON to a terminal. It is an audit pipeline with a rendered output. The report is a documentation page, not a log file.

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
| MEDIUM | Parameters changed | Clients using removed / renamed params | `<Warning>` |
| LOW | Summary or description text changed | Nobody — zero runtime impact | `<Info>` |

---

## Setup

```bash
# Python 3.9+ required
pip install -r requirements.txt
```

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

Webhook URLs can also be supplied via environment variables instead of flags:

```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
python main.py
```

Copy `.env.example` to `.env` and fill in the placeholders to persist them locally.

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

The suite covers all three severity tiers, edge cases (empty spec, malformed JSON, vendor extension keys), and integration tests against the real fixture files.

---

## Docker

```bash
docker build -t mintlify-sentinel .

# Default run
docker run --rm mintlify-sentinel

# Mount your own specs
docker run --rm \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  mintlify-sentinel
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
  main.py                         Master orchestrator
  docs.json                       Mintlify site config
  requirements.txt                Pinned Python dependencies
  Dockerfile
  input/
    admin-openapi.json            Baseline spec (V1)
    analytics.openapi.json        Target spec (V2)
  output/
    changelog.mdx                 Generated MDX changelog
  scripts/
    judge_config.py               Stage 1: docs.json validator (Pydantic v2)
    judge_diff.py                 Stage 2: semantic diff engine
    architect_render.py           Stage 3: Jinja2 MDX renderer
    notifier.py                   Slack + Discord webhook dispatcher
    architect_pdf.py              PDF variant (optional, requires system deps)
  templates/
    changelog.mdx.jinja           Jinja2 template
  tests/
    test_judge_config.py
    test_judge_diff.py
    test_architect_render.py
    test_notifier.py
  docs/
    README_layperson.md
    README_semi_tech.md
    README_pitch.md
```

---

## Known Limitations

**`architect_pdf.py`** uses naive string replacement to convert Mintlify MDX callouts to HTML for PDF rendering. This is not in the main pipeline and is not covered by the test suite. Use the MDX output for production; the PDF variant is a utility for internal distribution only.

**`weasyprint` on Windows** requires Cairo and Pango native libraries not available by default. Run inside Docker if PDF output is needed on a Windows machine.

**`output/changelog.mdx`** is overwritten on every pipeline run and on every test run. If you need a persistent changelog history, version-control the output directory or implement a separate archiving step downstream.
