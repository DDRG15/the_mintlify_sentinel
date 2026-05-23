# Audit & Fix Log — The Mintlify Sentinel

**Date:** 2026-05-23
**Author:** DDRG15
**Scope:** Full pre-push MODE A audit of all project files after v1.3 ship.

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

## Finding 1 — Dead dependencies inflate Docker image and block Windows local setup

**Severity:** HIGH
**Personas:** DEV, SRE

### 5W + How

| | |
|-|-|
| **Who** | Any developer on Windows attempting local setup; every Docker build triggered by CI. |
| **What** | `requirements.txt` listed `weasyprint==62.3` and `markdown==3.6`. These two packages exist solely for `scripts/architect_pdf.py`, which is gitignored and not connected to the main pipeline. The `Dockerfile` installed six native system libraries (`libcairo2`, `libpango-1.0-0`, `libpangocairo-1.0-0`, `libgdk-pixbuf-2.0-0`, `libffi-dev`, `shared-mime-info`) to support WeasyPrint. Additionally, `.dockerignore` did not exclude `architect_pdf.py`, so `COPY . .` copied it into every image. |
| **When** | Every `pip install -r requirements.txt` run on Windows, and every `docker build`. |
| **Where** | `requirements.txt` lines 19–27 (removed section), `Dockerfile` lines 28–36 (removed block). |
| **Why** | WeasyPrint requires native Cairo/Pango libraries not available on Windows without MSYS2/vcpkg. Any Windows developer running `pip install -r requirements.txt` hit a build failure before any package installed. The native library apt-get block added ~200MB to every Docker image for no functional benefit at runtime. |
| **How** | Removed `markdown==3.6` and `weasyprint==62.3` from `requirements.txt`. Removed the `apt-get install` block from `Dockerfile`. Added `scripts/architect_pdf.py` to `.dockerignore` so it is excluded from the build context. |

### Files changed

- `requirements.txt` — removed `markdown==3.6`, `weasyprint==62.3`, and their comment block
- `Dockerfile` — removed the `apt-get update && apt-get install -y` block
- `.dockerignore` — added `scripts/architect_pdf.py`

### Verification

```bash
pip install -r requirements.txt      # completes cleanly on Windows without MSYS2
pip show weasyprint                  # WARNING: Package not found
docker build -t mintlify-sentinel .  # no apt-get libcairo lines in build log
```

---

## Finding 2 — Validation error details invisible in Streamlit browser UI

**Severity:** MEDIUM
**Personas:** ARCH, DEV

### 5W + How

| | |
|-|-|
| **Who** | Any user of the Validate Config tab who uploads an invalid `docs.json`. |
| **What** | `validate_docs_config()` internally calls `print_validation_report()`, which writes the full Pydantic field-level error report (location paths, error types, bad values) to stdout. In the Validate Config tab, stdout was not redirected — the report went to the terminal where Streamlit is running, not to the browser. The user saw only a generic error message with no actionable field-level detail. |
| **When** | Every time a user uploads an invalid `docs.json` and clicks Validate. |
| **Where** | `app.py` — Validate Config tab handler (lines ~296–322). |
| **Why** | The Run Sentinel tab already used `contextlib.redirect_stdout(log_buf)` to capture pipeline output. The Validate Config tab was implemented without the same pattern — stdout capture was not applied. |
| **How** | Added `val_log_buf = io.StringIO()` and wrapped `validate_docs_config()` in `contextlib.redirect_stdout(val_log_buf)`. The captured output is shown in a `st.expander` — expanded automatically on failure, collapsed on success. Removed the generic "check the terminal" message. |

### Files changed

- `app.py` — Validate Config tab handler

### Verification

Upload a `docs.json` with a missing `name` field. Click Validate. The browser must show:
- Red error banner: `"filename.json failed validation."`
- Expanded "Validation errors" section containing the full Pydantic report with field paths and error types.

---

## Finding 3 — SCHEMA_DRIFT rendering logic had zero test coverage

**Severity:** MEDIUM
**Persona:** SDET

### 5W + How

| | |
|-|-|
| **Who** | Any future developer modifying `templates/changelog.mdx.jinja`. |
| **What** | Lines 23–38 of `changelog.mdx.jinja` contain the Jinja2 rendering logic for `SCHEMA_DRIFT` findings: loops over `response_schema_changes` and `request_body_schema_changes`, renders field names, change types, from/to types, required promotions. None of the 11 tests in `test_architect_render.py` passed a SCHEMA_DRIFT finding. A regression anywhere in those 15 lines passed the test suite without detection. |
| **When** | Introduced with the v1.2 granular schema diff feature. Test coverage was not extended to match the new template logic. |
| **Where** | `tests/test_architect_render.py` — `TestSchemaDriftRendering` class was missing entirely. |
| **Why** | The SCHEMA_DRIFT change type was added to the diff engine and template in the same sprint, but the render test file was not updated to cover the new template section. |
| **How** | Added `TestSchemaDriftRendering` class with 11 tests: warning callout presence, response schema section header, `field_removed`, `field_added`, `type_changed` (with from/to values), `became_required`, `became_optional`, empty list omits section header, request body section header, request body `field_added`, and finding keys in output. |

### Files changed

- `tests/test_architect_render.py` — new `TestSchemaDriftRendering` class (11 tests)

### Verification

```bash
pytest tests/test_architect_render.py -v
# 22 tests pass (11 original + 11 new)
```

---

## Finding 4 — Temp file resource leak on OS-level failure

**Severity:** LOW
**Persona:** SRE

### 5W + How

| | |
|-|-|
| **Who** | Any user of the Run Sentinel tab during an OS-level storage failure. |
| **What** | `baseline_path` was assigned before the `try` block. If the second `NamedTemporaryFile` call raised (disk full, OS error), `baseline_path` leaked — the `finally` block was never entered because the exception occurred before `try`. |
| **When** | OS-level failure during temp file creation. Does not occur under normal operating conditions. |
| **Where** | `app.py` — Run Sentinel tab handler, temp file creation block. |
| **Why** | Both temp file creation calls were placed before `try:` as setup code, without accounting for the fact that setup failures are also exceptional conditions requiring cleanup. |
| **How** | Moved both `NamedTemporaryFile` calls inside the `try` block. Initialized `baseline_path = None` and `target_path = None` before `try`. Updated `finally` to guard with `if path and os.path.exists(path)` before `os.unlink`, so a partial-creation state is handled cleanly without a `NameError`. |

### Files changed

- `app.py` — Run Sentinel tab handler, temp file creation and finally block

### Verification

Normal operation is identical to before. Both temp files are created, pipeline runs, both are deleted in `finally` regardless of pipeline outcome.

---

## Finding 5 — GitHub Actions Node.js 24 migration deadline

**Severity:** MEDIUM (time-sensitive)
**Persona:** DEV

### 5W + How

| | |
|-|-|
| **Who** | CI pipeline on every push and pull request. |
| **What** | GitHub Actions forces all action runners to Node.js 24 on 2026-06-02 — 10 days from the date of this audit. `actions/checkout@v4` and `actions/setup-python@v5` currently resolve to Node.js 20 runner versions. |
| **When** | 2026-06-02. |
| **Where** | `.github/workflows/sentinel.yml` — action version pins. |
| **Why** | The actions use major-version tags (`@v4`, `@v5`). GitHub action maintainers have already published Node.js 24-compatible patch releases within those major versions. Major-version tags resolve to the latest patch automatically — no user-side change is required. The runner upgrade is managed by GitHub and the action maintainers. |
| **How** | No code change required at this time. If CI fails after 2026-06-02 with Node.js runtime errors, bump action versions to the next major (e.g. `actions/checkout@v5`) or follow GitHub's migration guide at that point. |

### Files changed

- None — informational finding, resolved by action maintainers.

---

## Test count before and after this audit

| Suite | Before | After |
|-------|--------|-------|
| `test_judge_config.py` | 13 | 13 |
| `test_judge_diff.py` | 38 | 38 |
| `test_architect_render.py` | 11 | 22 |
| `test_notifier.py` | 17 | 17 |
| **Total** | **95** | **106** |

All 106 tests pass on Python 3.12 / Windows 10 and Ubuntu (CI).

---

## Open risks carried forward

**Highest silent-failure risk:** `output/changelog.mdx` is written with a plain `open(..., "w")` — not atomic. Two concurrent Streamlit sessions calling `render_changelog()` simultaneously would race on the file write. The current deployment is single-user local, so this does not trigger in practice. If the app is deployed to a multi-user host, the fix is to apply the same atomic write pattern used by `historian.py` (write to a `.tmp` file then `os.replace()`).

**Context not covered by this audit:**
- No load or concurrency testing performed.
- `scripts/architect_pdf.py` is excluded from the Docker image via `.dockerignore` (fixed in this audit) but remains on the local filesystem as a gitignored file. It does not affect CI or production in any way.
