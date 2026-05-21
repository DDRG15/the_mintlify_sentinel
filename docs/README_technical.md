# The Mintlify Sentinel — Technical Reference

## Architecture

```
docs.json ─────────────────────► judge_config.py    Stage 1: Pydantic v2 config validation
                                        │
baseline-openapi.{json,yaml} ──┐        ▼
                                ├──► judge_diff.py     Stage 2: Semantic diff engine v4.0
target-openapi.{json,yaml}  ───┘        │
                                        ▼
                               architect_render.py    Stage 3: Jinja2 MDX renderer
                                        │
                                        ▼
                               output/changelog.mdx   → commit to docs repo
                                        │
                               historian.py           Append to output/history.json
```

`main.py` owns sequencing and exit codes. All business logic lives in the four engine modules. `notifier.py` fires after Stage 4 independently of pipeline success/failure state.

---

## Stage 1 — Config Validation (`scripts/judge_config.py`)

**What:** Validates `docs.json` against a Pydantic v2 model derived from the Mintlify site configuration schema.

**Why it's a hard gate:** A malformed `docs.json` causes the Mintlify build to fail completely. Running a diff whose output will never render is wasteful and misleading — stop early.

**Exit behaviour:** Returns `True` (valid) or `False` (invalid). `main.py` calls `sys.exit(1)` on `False`. This is the only place in the pipeline that can produce a non-zero exit code.

---

## Stage 2 — Diff Engine (`scripts/judge_diff.py`) — v4.0

### File loading (`load_openapi`)

Reads the file, tries `json.loads()` first, falls back to `yaml.safe_load()` if JSON fails. Format is detected from content — not file extension — because Streamlit writes uploaded files to temp paths with `.json` suffixes regardless of origin format. Raises `RuntimeError` with a prefix of `[FILE NOT FOUND]` or `[INVALID FORMAT]` on failure.

### Contract extraction (`extract_contracts`)

Returns `dict[signature, operation_object]`. The key is the normalised signature string (e.g. `"GET /v1/users/{id}"`). The value is the raw OpenAPI Operation Object dict.

Filters applied during extraction:
- Vendor extension keys (`x-*`) → skipped
- Path-level structural keys (`summary`, `description`, `parameters`, `$ref`, `servers`) → skipped
- HTTP methods normalised to uppercase

### Phase 1 — Set difference (`_find_removed_endpoints`)

```python
removed = v1_contracts.keys() - v2_contracts.keys()
```

Every signature in V1 but absent from V2 → `CRITICAL / ENDPOINT_REMOVED`.

### Phase 2 — Intersection analysis (`_find_modified_endpoints`)

```python
shared = v1_contracts.keys() & v2_contracts.keys()
```

For each shared signature, rules are evaluated in priority order. The first rule that fires produces the finding; subsequent rules are skipped (**single finding per endpoint**).

**Rule B — PARAMETERS_MODIFIED (MEDIUM)**
Compares `_serialise_params(v1_op["parameters"])` against `_serialise_params(v2_op["parameters"])`. `_serialise_params` uses `json.dumps(sort_keys=True)` to normalise key ordering and eliminate false positives from spec reformatting.

**Rule C — SCHEMA_DRIFT (MEDIUM)**
Fast path: serialise and compare `responses` and `requestBody` objects. If either differs, runs a property-level walk via `_diff_schema_properties()`.

**Rule A — DOCS_UPDATED (LOW)**
Compares `summary` and `description` strings. Only fires if neither Rule B nor Rule C fired.

### Schema diff helpers

**`_extract_json_schema(holder)`**
Navigates `holder → content → application/json → schema`. Works for both a response object and a `requestBody` object.

**`_get_primary_response_schema(responses)`**
Selects the primary success response schema. Preference: `200 → 201 → 202 → first 2xx → first response`.

**`_diff_schema_properties(v1_schema, v2_schema)`**
Compares two schema objects at the `properties` level. Returns a list of change dicts:

| `change` value | Meaning |
|----------------|---------|
| `field_removed` | Field present in V1 `properties`, absent in V2 |
| `field_added` | Field absent in V1 `properties`, present in V2 |
| `type_changed` | Field exists in both; `.type` key differs. Includes `from_type` and `to_type` |
| `became_required` | Field in both versions' `properties`, added to `required` array in V2 |
| `became_optional` | Field in both versions' `properties`, removed from `required` array in V2 |

Required changes are only reported for fields that exist in both versions — added/removed fields report their own change type.

### Finding dict schema

```python
{
    # All findings
    "signature":   str,   # e.g. "GET /v1/users/{id}"
    "method":      str,   # "GET"
    "path":        str,   # "/v1/users/{id}"
    "severity":    str,   # "CRITICAL" | "MEDIUM" | "LOW"
    "change_type": str,   # "ENDPOINT_REMOVED" | "PARAMETERS_MODIFIED" | "SCHEMA_DRIFT" | "DOCS_UPDATED"
    "description": str,

    # PARAMETERS_MODIFIED only
    "params_v1_count": int,
    "params_v2_count": int,

    # SCHEMA_DRIFT only
    "response_schema_changes":     list[dict],  # see _diff_schema_properties output
    "request_body_schema_changes": list[dict],
}
```

### Severity rank and sort

`_combine_and_sort(phase1, phase2)` merges and sorts by `(severity_rank, signature)`:
- CRITICAL → 0
- MEDIUM → 1
- LOW → 2

---

## Stage 3 — MDX Renderer (`scripts/architect_render.py`)

Calls `jinja2.Environment(loader=FileSystemLoader("templates")).get_template("changelog.mdx.jinja")` and renders with `{"changes": findings}`. Writes to `output/changelog.mdx`.

Template logic:
- Empty list → `<Check>` callout
- CRITICAL → `<Danger>` callout
- MEDIUM → `<Warning>` callout, with an optional field-level sub-list rendered from `response_schema_changes` and `request_body_schema_changes` if present and non-empty
- LOW → `<Info>` callout

---

## History Store (`scripts/historian.py`)

**`append_run(findings, baseline_path, target_path) → list`**
Builds a run record, inserts at index 0 (newest first), and atomically writes `output/history.json` via a `.tmp` file + `os.replace()`.

**`load_history() → list`**
Reads `output/history.json`. Returns `[]` if file missing or JSON is corrupt.

### Run record schema

```python
{
    "id":        str,   # "20260521_143015" — sortable
    "timestamp": str,   # ISO 8601, second precision
    "baseline":  str,   # os.path.basename(baseline_path)
    "target":    str,   # os.path.basename(target_path)
    "total":     int,
    "critical":  int,
    "medium":    int,
    "low":       int,
    "findings":  list[dict],   # full finding dicts as above
}
```

---

## Notifier (`scripts/notifier.py`)

**`notify(findings, slack_url, discord_url) → dict`**
Builds and fires payloads to Slack and/or Discord. Falls back to `SLACK_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL` env vars if URL arguments are empty strings.

Adds `User-Agent: MintlifySentinel/1.0` — required to bypass Cloudflare's bot protection on Discord webhooks.

Never raises. Returns `{"slack": {...}, "discord": {...}}` with `sent: bool` and `status: int` (or `error: str`).

---

## CLI Reference (`main.py`)

```
python main.py [OPTIONS]

Options:
  --baseline PATH       Baseline OpenAPI spec (V1). Default: input/admin-openapi.json
  --target PATH         Target OpenAPI spec (V2). Default: input/analytics.openapi.json
  --config PATH         Mintlify docs.json. Default: docs.json
  --slack-webhook URL   Slack Incoming Webhook URL
  --discord-webhook URL Discord Webhook URL
```

Environment variables (read by `notifier.py`):
```
SLACK_WEBHOOK_URL
DISCORD_WEBHOOK_URL
```

Exit codes:
```
0 — Always, including when findings are present (audit mode)
1 — docs.json failed structural validation
```

---

## Test Coverage (95 tests)

| Module | File | Tests | What's covered |
|--------|------|-------|---------------|
| `judge_config` | `test_judge_config.py` | 13 | Valid configs, missing required fields, malformed JSON, empty file, file-not-found |
| `judge_diff` | `test_judge_diff.py` | 52 | `extract_contracts`, all 4 rule types, schema helpers (`_diff_schema_properties`, `_extract_json_schema`, `_get_primary_response_schema`), field-level granular diff, edge cases, YAML loading, integration against real fixtures |
| `architect_render` | `test_architect_render.py` | 9 | Correct callout per severity, clean diff, mixed severity, callout exclusivity |
| `notifier` | `test_notifier.py` | 21 | Slack/Discord payload building, HTTP success/failure, env var fallback, skip behaviour, exception safety |

`conftest.py` — session-scoped autouse fixture backs up and restores `output/changelog.mdx` so test runs never corrupt a real pipeline output.

Run the full suite:
```bash
pytest tests/ -v
pytest tests/ -v --cov=scripts --cov-report=term-missing
```

---

## Docker

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/output
CMD ["python", "main.py"]
```

WeasyPrint's Cairo/Pango system libs are included even though `architect_pdf.py` is not in the main pipeline — Docker layer caching means the apt step is paid once.

```bash
docker build -t mintlify-sentinel .
docker run --rm mintlify-sentinel
docker run --rm -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" mintlify-sentinel
docker run --rm -p 8501:8501 mintlify-sentinel streamlit run app.py --server.address 0.0.0.0
```

---

## GitHub Actions CI (`.github/workflows/sentinel.yml`)

Two jobs, sequenced:

1. **`test`** — `ubuntu-latest`, Python 3.12, installs requirements, runs `pytest tests/ -v --cov=scripts --cov-report=term-missing`
2. **`pipeline`** — `needs: test`, runs `python main.py`, uploads `output/changelog.mdx` as artifact `changelog-mdx`

Triggers: push to any branch, PR targeting `main`.

---

## Project Structure

```
the_mintlify_sentinel/
  main.py                    Master orchestrator and CLI entry point
  app.py                     Streamlit browser UI (3 tabs)
  docs.json                  Mintlify site config (validated by Stage 1)
  requirements.txt           Pinned Python dependencies
  Dockerfile
  .dockerignore
  .gitignore
  .gitattributes             LF line ending normalisation
  .env.example               Webhook URL template
  input/
    admin-openapi.json       Baseline spec (V1 fixture)
    analytics.openapi.json   Target spec (V2 fixture)
  output/
    changelog.mdx            Generated MDX changelog (gitignored)
    history.json             Run history store (gitignored)
  scripts/
    judge_config.py          Stage 1: Pydantic v2 docs.json validator
    judge_diff.py            Stage 2: Semantic diff engine v4.0
    architect_render.py      Stage 3: Jinja2 MDX renderer
    notifier.py              Slack + Discord webhook dispatcher
    historian.py             Run history store (append + load)
    architect_pdf.py         PDF variant (optional — requires WeasyPrint system libs)
  templates/
    changelog.mdx.jinja      Jinja2 template
  tests/
    conftest.py              Session fixture — preserves output/changelog.mdx
    test_judge_config.py
    test_judge_diff.py
    test_architect_render.py
    test_notifier.py
  docs/
    README_layperson.md      Non-technical explanation
    README_semi_tech.md      Semi-technical overview
    README_technical.md      This file — full technical reference
    README_pitch.md          Product pitch
    STREAMLIT_PLAN.md        UI implementation record
    ROADMAP.md               Prioritised backlog
  .github/
    workflows/
      sentinel.yml           CI: test → pipeline → artifact upload
```

---

## Known Limitations

**`architect_pdf.py`** — not in the main pipeline. Uses naive string replacement to convert MDX callouts to HTML. Will corrupt output if finding descriptions contain angle brackets. WeasyPrint requires native system libs that aren't available on Windows outside of Docker.

**`output/history.json`** — flat file, no locking. Concurrent writes from multiple processes would corrupt it. Acceptable for the current use case (one pipeline run at a time). Not a concern until the React frontend + multi-user scenario.

**`extract_contracts`** — the spec diff is shallow: it compares the primary JSON schema one level deep (direct properties). It does not recursively walk nested `$ref` objects, `allOf`/`anyOf`/`oneOf` compositions, or array item schemas. Sufficient for the vast majority of real-world OpenAPI specs; the next step would be a `$ref` resolver.
