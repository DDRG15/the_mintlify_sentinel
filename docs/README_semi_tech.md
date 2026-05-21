# The Mintlify Sentinel — Overview for the Technically Curious

## What it does

The Sentinel is an automated API contract auditing tool. You give it two versions of an OpenAPI specification — the current version and the proposed new one — and it identifies every change between them, ranked by severity. The output is a formatted report ready to publish to a Mintlify documentation site.

It works from a browser or a command line. Results arrive in about 10 seconds.

---

## Two ways to run it

**Browser interface**
Run `streamlit run app.py`, open `http://localhost:8501`, upload two spec files (JSON or YAML), and click **Run Sentinel**. Results appear as color-coded finding cards. You can download the changelog file directly, enter Slack or Discord webhook URLs in the sidebar to fire notifications, and review past runs in the History tab — all without touching a terminal.

**Command line**
Run `python main.py` from the project folder. Accepts explicit file paths via flags (`--baseline`, `--target`). Webhook URLs can be passed as flags or set as environment variables. The formatted changelog is saved to `output/changelog.mdx`.

Both produce the same output.

---

## The four stages

Every run goes through four stages in sequence:

**Stage 1 — Config validation**
Checks that your Mintlify site configuration file (`docs.json`) is structurally correct. If it's broken, the pipeline stops immediately. A misconfigured `docs.json` causes the entire Mintlify site build to fail, so there is no point running a diff whose output will never render.

**Stage 2 — Semantic diff**
Compares the two API specs and classifies every difference:

| Severity | What it means |
|----------|--------------|
| **CRITICAL** | An endpoint that existed in V1 is gone in V2. Every caller will get an error on deployment. |
| **MEDIUM (PARAMETERS_MODIFIED)** | The inputs an endpoint accepts have changed. |
| **MEDIUM (SCHEMA_DRIFT)** | The data shape returned or accepted by an endpoint changed. The Sentinel tells you exactly which fields were added, removed, or had their types changed — not just that something changed. |
| **LOW** | Only the description text was updated. Zero runtime impact. |

One finding per endpoint — if an endpoint has both a parameter change and a schema change, only the higher-severity finding is reported.

**Stage 3 — MDX rendering**
A template converts the findings into a Mintlify-native MDX file using the correct callout components: `<Danger>` for CRITICAL, `<Warning>` for MEDIUM (with a field-level change sub-list), `<Info>` for LOW. Commit the file to your docs repo and it renders natively.

**Stage 4 — Audit gate**
Always exits with code 0. The Sentinel is an auditing tool, not a deployment blocker. The decision to proceed belongs to the engineer.

---

## What the Sentinel detects (with examples)

| Change | Severity | What you see |
|--------|----------|-------------|
| Endpoint `DELETE /v1/users/{id}` removed | CRITICAL | "Endpoint existed in baseline but is absent in target" |
| `limit` parameter removed from `GET /users` | MEDIUM | "Endpoint parameters were altered. V1=2 → V2=1 (-1)" |
| `id` field changed from `string` to `integer` in response | MEDIUM | "response schema changed" + field sub-list: `id — type changed string → integer` |
| `email` field added to required in request body | MEDIUM | "request body schema changed" + field sub-list: `email — became required` |
| Summary text rewritten | LOW | "summary changed" |

---

## Notifications

After the pipeline runs, the Sentinel can send a formatted summary to Slack or Discord. Supply the webhook URL via `--slack-webhook`, `--discord-webhook`, or the environment variables `SLACK_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL`. The message includes total finding counts by severity and one line per finding.

---

## History tab

Every run is automatically recorded in `output/history.json`. The browser UI's History tab shows a table of all past runs (timestamp, spec filenames, finding counts by severity) and lets you click into any past run to review its individual findings. This turns the Sentinel from a point-in-time check into a continuous audit trail.

---

## Supported formats and environments

- OpenAPI 3.x — JSON or YAML (auto-detected from file content, not extension)
- Python 3.10 or later
- Docker — the full pipeline and the browser UI both run in a container
- GitHub Actions CI — a pre-built workflow is included in `.github/workflows/sentinel.yml`

---

## Tech stack in plain terms

| Tool | What it does in the Sentinel |
|------|------------------------------|
| Python 3.10+ | The core language — all pipeline logic is pure Python |
| Pydantic v2 | Validates that `docs.json` matches the Mintlify schema |
| Jinja2 | Converts the findings list into the MDX changelog file |
| PyYAML | Parses YAML-format OpenAPI specs |
| Streamlit 1.35 | Provides the browser interface |
| pytest | 95 automated tests covering all pipeline stages |

No database. No external services. No paid subscriptions.

---

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Run with the included example specs
python main.py

# Run with your own files
python main.py --baseline path/to/v1.json --target path/to/v2.json

# Run with Slack notification
python main.py --slack-webhook https://hooks.slack.com/services/...

# Open the browser UI
streamlit run app.py

# Run all tests
pytest tests/ -v
```
