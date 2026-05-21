# The Mintlify Sentinel — Overview for the Technically Curious

## What This Tool Does

The Sentinel is a tool that compares two versions of an API specification file and generates a formatted report of everything that changed between them.

An API specification is a document — written in a standard format called OpenAPI — that describes exactly how a software service works: what features it has, how you call them, and what you get back. When that document changes, some of those changes are harmless. Others break every application that was relying on the old behavior.

The Sentinel automatically tells you which is which.

## Two Ways to Use It

**Browser interface** — open a web page, upload two files, click a button. No terminal required. Results appear on screen as colored alert cards. You can download the report directly from the page and paste a Slack or Discord webhook URL in the sidebar to get a notification sent to your team automatically.

**Command line** — a single `python main.py` command from a terminal. Supports flags for explicit file paths and webhook URLs. Integrates directly into CI/CD pipelines.

Both produce the same output: a formatted MDX file ready to publish to your Mintlify documentation site.

## How It Works (Without the Code)

You give it two files: the old version of the API spec and the new version. It runs them through a four-stage pipeline:

1. **Config validation (hard gate):** Checks that your Mintlify site config (`docs.json`) is structurally correct. If it's broken, the pipeline stops immediately — there's no point running a diff if the output will never render.
2. **Semantic diff:** Looks for three types of changes between the two specs:
   - **Critical:** A feature was completely removed. Every caller using it will get an error the moment the update goes live.
   - **Medium:** The inputs a feature expects changed. Apps that were sending the old inputs will fail.
   - **Low:** Only the description text changed. No functional impact — but worth reviewing.
3. **Changelog rendering:** Produces a formatted MDX file using Mintlify's native callout components (`<Danger>`, `<Warning>`, `<Info>`). Commit it to your docs repo and it renders as a changelog page.
4. **Audit gate:** Reports findings and exits. Never blocks a deployment — the decision to proceed is the engineer's.

## Notifications

After the pipeline runs, the Sentinel can send a formatted summary to Slack or Discord. The message includes the total finding count broken down by severity, plus one entry per finding. You supply the webhook URL — the Sentinel fires it automatically.

## Why This Matters

Without a tool like this, breaking API changes are discovered by your users — not your team. A developer integrating with your API wakes up one morning to find their application throwing errors, traces it back to your last release, and files a support ticket (or just silently stops using your product).

The Sentinel surfaces those changes before the release, not after.

## What It's Built On

- **Python 3.10+** — the programming language it's written in
- **Pydantic v2** — validates that your Mintlify site config is structurally correct before the diff runs
- **Jinja2** — a templating engine that formats findings into a ready-to-publish MDX document
- **Streamlit** — the browser UI that wraps the pipeline in a web interface
- **Mintlify** — the documentation platform the output is designed for

You don't need to know any of these to use the tool. You just need Python installed, one `pip install` command, and either a browser or a terminal.
