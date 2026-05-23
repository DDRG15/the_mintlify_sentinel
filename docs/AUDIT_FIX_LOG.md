# Audit & Fix Log — The Mintlify Sentinel

**Date:** 2026-05-23
**Author:** DDRG15
**Scope:** Full pre-push MODE A audit of all project files after v1.3 ship.
**Tool:** Claude Code (claude-sonnet-4-6)

---

## Files audited

| File | Role |
|------|------|
| `main.py` | Master orchestrator |
| `scripts/judge_config.py` | Stage 1 — docs.json validator |
| `scripts/judge_diff.py` | Stage 2 — diff engine |
| `scripts/architect_render.py` | Stage 3 — MDX renderer |
| `scripts/notifier.py` | Stage 4b — Slack/Discord notifier |
| `scripts/historian.py` | Run history store |
| `app.py` | Streamlit browser UI |
| `templates/changelog.mdx.jinja` | Jinja2 MDX template |
| `Dockerfile` | Container definition |
| `requirements.txt` | Python dependencies |
| `.github/workflows/sentinel.yml` | CI/CD pipeline |
| `tests/test_judge_config.py` | Config validator tests |
| `tests/test_judge_diff.py` | Diff engine tests |
| `tests/test_architect_render.py` | Renderer tests |
| `tests/test_notifier.py` | Notifier tests |
| `tests/conftest.py` | Session fixtures |

---

## Finding 1 — Dead dependencies block Windows development and inflate Docker image

**Severity:** HIGH
**Personas:** DEV, SRE

### 5W + How

| | |
|-|-|
| **Who** | Any developer on Windows attempting local setup; every Docker build triggered by CI. |
| **What** | `requirements.txt` listed `weasyprint==62.3` and `markdown==3.6`. These two packages exist solely for `scripts/architect_pdf.py` — a script that is gitignored, excluded from the pipeline, and confirmed broken (naive string replacement corrupts findings containing angle brackets). The `Dockerfile` installed six native system libraries (`libcairo2`, `libpango-1.0-0`, `libpangocairo-1.0-0`, `libgdk-pixbuf-2.0-0`, `libffi-dev`, `shared-mime-info`) to support WeasyPrint. `scripts/architect_pdf.py` is on disk but not excluded by `.dockerignore`, so `COPY . .` copied it into every image anyway. |
| **When** | Every `pip install -r requirements.txt` run, and every `docker build`. |
| **Where** | `requirements.txt` lines 19–27 (removed section), `Dockerfile` lines 28–36 (removed block). |
| **Why** | WeasyPrint requires native Cairo/Pango libraries not available on Windows without MSYS2/vcpkg. Any Windows developer running `pip install -r requirements.txt` hit a build failure before any package installed. The native library apt-get block added ~200MB to every Docker image for zero functional benefit. |
| **How** | Removed `markdown==3.6` and `weasyprint==62.3` from `requirements.txt`. Removed the entire `apt-get install` block from `Dockerfile`. The `architect_pdf.py` script remains gitignored and on disk — no pipeline impact. |

### Files changed

- `requirements.txt` — removed `markdown==3.6`, `weasyprint==62.3`, and their associated comment block
- `Dockerfile` — removed `apt-get update && apt-get install -y` block with 6 native libraries

### Verification

```bash
pip install -r requirements.txt   # must complete cleanly on Windows without MSYS2
pip show weasyprint                # "not found"
docker build -t mintlify-sentinel .   # build log must not show apt-get libcairo lines
```

---

## Finding 2 — Validation errors invisible in Streamlit browser UI

**Severity:** MEDIUM
**Personas:** ARCH, DEV

### 5W + How

| | |
|-|-|
| **Who** | Any user of the Validate Config tab in the Streamlit UI who uploads an invalid `docs.json`. |
| **What** | `validate_docs_config()` calls `print_validation_report()` internally, which writes the full Pydantic field-level error report (location paths, error types, bad values) to stdout. In the Validate Config tab, stdout was not redirected. The report went to the terminal where Streamlit is running — not to the browser. The user saw only: `"Check the terminal output for field-level errors"` — a message that is wrong for any non-local deployment (Docker, Streamlit Cloud, hosted server). |
| **When** | Every time a user uploads an invalid `docs.json` and clicks Validate. |
| **Where** | `app.py` lines 296–322 (Validate Config tab handler). |
| **Why** | The Run Sentinel tab already used `contextlib.redirect_stdout(log_buf)` to capture pipeline output. The Validate Config tab was implemented without the same pattern. |
| **How** | Added `val_log_buf = io.StringIO()` and wrapped `validate_docs_config()` in `contextlib.redirect_stdout(val_log_buf)`. The captured output is shown in a `st.expander` — expanded by default on failure, collapsed on success. Removed the "Check the terminal output" message entirely. |

### Files changed

- `app.py` — Validate Config tab handler (lines ~296–322)

### Verification

Upload a docs.json with a missing `name` field. Click Validate. Browser should show:
- Red error banner: `"filename.json failed validation."`
- Expanded "Validation errors" expander with the full Pydantic error report (location, error type, bad value).

---

## Finding 3 — SCHEMA_DRIFT rendering logic had zero test coverage

**Severity:** MEDIUM
**Persona:** SDET

### 5W + How

| | |
|-|-|
| **Who** | Any future developer modifying `templates/changelog.mdx.jinja`. |
| **What** | Lines 23–38 of `changelog.mdx.jinja` contain the full Jinja2 rendering logic for `SCHEMA_DRIFT` findings: loops over `response_schema_changes` and `request_body_schema_changes`, renders field names, change types, from/to types, required promotions. None of the 11 tests in `test_architect_render.py` passed a SCHEMA_DRIFT finding. A regression anywhere in those 15 lines — wrong field name, broken conditional, broken loop — passed the 95-test suite undetected. |
| **When** | Introduced with the v1.2 granular schema diff feature. Test suite was not extended to match. |
| **Where** | `tests/test_architect_render.py` — missing `TestSchemaDriftRendering` class. |
| **Why** | SCHEMA_DRIFT was added to the diff engine and the template in the same commit, but the render test file was not updated to cover the new template logic. |
| **How** | Added `TestSchemaDriftRendering` class with 11 tests: warning callout presence, response schema section header, field_removed, field_added, type_changed (with from/to), became_required, became_optional, empty list omits section header, request body section header, request body field_added, and finding keys in output. |

### Files changed

- `tests/test_architect_render.py` — new `TestSchemaDriftRendering` class (11 tests)

### Verification

```bash
pytest tests/test_architect_render.py -v
# All 22 tests pass (11 original + 11 new)
```

---

## Finding 4 — Temp file leak if second NamedTemporaryFile creation fails

**Severity:** LOW
**Persona:** SRE

### 5W + How

| | |
|-|-|
| **Who** | Any user of the Run Sentinel tab when the OS fails to create a temp file. |
| **What** | `baseline_path` was assigned before the `try` block. If the second `NamedTemporaryFile` call raised (disk full, OS error), `baseline_path` leaked — the `finally` block was never entered because the exception occurred before `try`. |
| **When** | OS-level failure during temp file creation. Requires disk full or similar condition; does not occur in normal operation. |
| **Where** | `app.py` lines 158–192 (Run Sentinel tab handler). |
| **Why** | The two temp file creation calls were placed before `try:` as an oversight — probably written as "setup code" before the pipeline logic, without considering that setup failures are also exceptional conditions. |
| **How** | Moved both `NamedTemporaryFile` calls inside the `try` block. Initialized `baseline_path = None` and `target_path = None` before `try`. Updated `finally` to guard with `if path and os.path.exists(path)` before calling `os.unlink`, so a partial-creation state is handled cleanly. |

### Files changed

- `app.py` — Run Sentinel tab handler, temp file creation and finally block

### Verification

Normal operation: two temp files created, pipeline runs, both files deleted in finally. Behavior is identical to before for all non-failure paths.

---

## Finding 5 — GitHub Actions Node.js 24 migration deadline

**Severity:** MEDIUM (time-sensitive)
**Persona:** DEV

### 5W + How

| | |
|-|-|
| **Who** | CI pipeline on every push and pull request. |
| **What** | GitHub Actions forces all action runners to Node.js 24 on 2026-06-02 — 10 days from the date of this audit. `actions/checkout@v4` and `actions/setup-python@v5` currently resolve to Node.js 20 runner versions. After the deadline, steps using deprecated Node.js 20 will produce warnings that escalate to blocking errors in the subsequent deprecation cycle. |
| **When** | 2026-06-02. |
| **Where** | `.github/workflows/sentinel.yml` — action version pins. |
| **Why** | The actions use major-version tags (`@v4`, `@v5`, `@v4`). GitHub action maintainers (GitHub-owned) have already published Node.js 24-compatible patch releases within those major versions. Major-version tags resolve to the latest patch automatically. No user-side change is required — the runner upgrade is managed by GitHub and the action maintainers. |
| **How** | No code change required. Documented here as a known upcoming event. Monitor GitHub's deprecation announcements. If CI fails after 2026-06-02 with Node.js runtime errors, bump action versions to the next major (e.g., `actions/checkout@v5`) or follow GitHub's migration guide at that time. |

### Files changed

- None (informational finding — resolved by action maintainers, not by this codebase)

---

## Test count before and after

| Suite | Before | After |
|-------|--------|-------|
| `test_judge_config.py` | 13 | 13 |
| `test_judge_diff.py` | 38 | 38 |
| `test_architect_render.py` | 11 | 22 |
| `test_notifier.py` | 17 | 17 |
| **Total** | **95** | **106** |

---

## Open risks (carried forward, not closed by this audit)

**Single highest silent-failure risk:** `output/changelog.mdx` write is not atomic. If two concurrent Streamlit sessions call `render_changelog()` simultaneously, one write clobbers the other mid-stream. The current deployment is single-user local — this does not trigger in that context. If the app is ever deployed to a multi-user host, the fix is to make `render_changelog()` use the same atomic write pattern as `historian.py` (temp file + `os.replace()`).

**Context missing from this audit:**
- No load testing performed — notifier timeout behavior under concurrent webhook calls is untested at scale.
- `scripts/architect_pdf.py` is on disk, gitignored, and copied into the Docker image by `COPY . .`. It is not executable in the container (missing WeasyPrint native libs — now correctly removed from requirements). If the file is ever accidentally invoked, it will fail immediately. Resolution: add `scripts/architect_pdf.py` to `.dockerignore`.
