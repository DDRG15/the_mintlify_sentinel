# Node.js 24 Migration — GitHub Actions CI

## Status

**PENDING — must be completed before 2026-06-02.**

Not broken yet. CI is green. This is a scheduled deprecation — GitHub forces the upgrade on June 2nd, 2026. If it is not done by then, both CI jobs will fail on every push.

---

## What the warning says

GitHub Actions showed this on every CI run starting with push `68e89fb` (2026-05-23):

```
Node.js 20 actions are deprecated. The following actions are running on
Node.js 20 and may not work as expected:
  actions/checkout@v4
  actions/setup-python@v5
  actions/upload-artifact@v4

Actions will be forced to run with Node.js 24 by default starting June 2nd, 2026.
Node.js 20 will be removed from the runner on September 16th, 2026.

To opt into Node.js 24 now, set the FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true
environment variable on the runner or in your workflow file.

Once Node.js 24 becomes the default, you can temporarily opt out by setting
ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true.
```

The warning appears in both CI jobs: **Run pytest** and **Run Sentinel pipeline**.

---

## What is actually changing

GitHub Actions runners execute action code (checkout, setup-python, upload-artifact)
inside a Node.js runtime. The runtime version is controlled by GitHub, not by us.

Timeline:
- **2026-06-02** — Node.js 24 becomes the default. Actions not compatible with Node.js 24
  will fail with a runtime error on every CI run.
- **2026-09-16** — Node.js 20 is removed from runners entirely.

Our Python code, tests, and pipeline logic are not affected. This is purely a CI
infrastructure change — the action runner version, not Python or the Sentinel itself.

---

## Affected file

**One file:** `.github/workflows/sentinel.yml`

Three action version pins are running on Node.js 20:

| Action | Current pin | Used in |
|--------|-------------|---------|
| `actions/checkout` | `@v4` | Both jobs (test + pipeline) |
| `actions/setup-python` | `@v5` | Both jobs (test + pipeline) |
| `actions/upload-artifact` | `@v4` | Pipeline job only |

Current workflow snapshot (as of 2026-05-23):

```yaml
# test job
- uses: actions/checkout@v4
- uses: actions/setup-python@v5

# pipeline job
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
- uses: actions/upload-artifact@v4
```

---

## Implementation plan

### Step 1 — Opt in early and test (do this first)

Add one `env:` block to the workflow, at the top level before `jobs:`:

```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'
```

Full workflow structure after this change:

```yaml
name: Mintlify Sentinel

on:
  push:
    branches:
      - "**"
  pull_request:
    branches:
      - main

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'

jobs:
  test:
    ...
  pipeline:
    ...
```

Push and watch CI. Two outcomes:

**Outcome A — CI passes green (expected)**
The action maintainers have already shipped Node.js 24 compatible patches within
the current major versions (@v4, @v5). The env var tells GitHub to use Node.js 24
now, and everything works. Done. Warnings disappear. No further action needed.

**Outcome B — CI fails with a runtime error**
One or more actions has not yet been updated within its current major version.
Go to Step 2.

---

### Step 2 — Bump action versions (only if Step 1 fails)

If Step 1 fails, identify which action broke from the CI log, then bump that action
to its next major version. Check the GitHub Actions marketplace for the current
Node.js 24 compatible release:

| Action | Marketplace URL to check |
|--------|--------------------------|
| `actions/checkout` | github.com/actions/checkout/releases |
| `actions/setup-python` | github.com/actions/setup-python/releases |
| `actions/upload-artifact` | github.com/actions/upload-artifact/releases |

Likely bumps (verify on marketplace before applying):
- `actions/checkout@v4` → `actions/checkout@v5`
- `actions/setup-python@v5` → `actions/setup-python@v6`
- `actions/upload-artifact@v4` → `actions/upload-artifact@v5`

Change only the actions that actually failed. Push again. Verify CI is green.

---

## How to verify it is fixed

CI run after the fix should show:
- No deprecation warnings in the Annotations section
- Both jobs green: **Run pytest** + **Run Sentinel pipeline**
- `pytest` reports 113 passed (or more if tests were added)
- `changelog-mdx` artifact uploaded

If warnings disappear entirely after Step 1, the migration is complete.

---

## Why this is not urgent today but is urgent this week

- Today (2026-05-23): CI is green, warnings are cosmetic.
- June 2nd (2026-06-02): GitHub forces Node.js 24. If the actions are not compatible,
  every push breaks CI. No tests run. No changelog artifact. The pipeline is dead.
- The fix is a 3-line change to one file. It takes 5 minutes.
- Risk of waiting: if you forget and push on June 3rd, CI fails and you will have
  to fix it under pressure. Do it before June 2nd on a calm day.

---

## Context for the next AI session

If you are reading this in a future session, here is what you need to know:

1. The Sentinel's CI pipeline has two jobs: `test` (pytest 113 tests) and `pipeline`
   (runs `python main.py`, uploads `output/changelog.mdx` as artifact).

2. The workflow file is at `.github/workflows/sentinel.yml`. It currently pins three
   GitHub Actions at version tags that run on Node.js 20.

3. The fix is Step 1 above. Add the `env:` block, push, verify green. If it fails,
   do Step 2 and bump the specific action that broke.

4. Do not bump action versions without checking the marketplace first — version numbers
   listed here are estimates, not confirmed. Always verify on the release page.

5. After the fix: update this file. Change Status from PENDING to RESOLVED and add
   the date and commit hash.

---

## Resolution log

| Date | Action | Result |
|------|--------|--------|
| 2026-05-23 | Identified during CI run after push `68e89fb` | PENDING |
| _(fill in)_ | Step 1 applied — FORCE_JAVASCRIPT_ACTIONS_TO_NODE24 | _(fill in)_ |
| _(fill in)_ | Step 2 applied (if needed) — version bump | _(fill in)_ |
