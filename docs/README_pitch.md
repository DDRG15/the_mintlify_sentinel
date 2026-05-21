# The Mintlify Sentinel — Product Pitch

## The Problem

Every API-driven product ships breaking changes. Not because engineers are careless — because API evolution is unavoidable. The question isn't whether breaking changes will happen. It's whether your team finds them before your users do.

Right now, most teams don't have an answer to that question. They push a release, wait for the support tickets, and then spend two days tracing which change broke which client. The cost isn't just engineering time. It's trust. A developer who hits a silent breaking change on a Friday afternoon doesn't come back.

## What the Sentinel Is

The Mintlify Sentinel is an automated API contract monitoring tool built specifically for teams that publish documentation on Mintlify. It runs as part of your release pipeline, takes 10 seconds, and produces a formatted, publishable changelog before any code reaches production.

It doesn't require a separate dashboard, a new SaaS subscription, or a new tab open in a browser. It runs where your code runs, outputs where your docs live, and gets out of the way.

## What Makes It Different

Most API diff tools produce raw JSON output or a wall of terminal text that only engineers can interpret. The Sentinel produces a Mintlify-native MDX file — formatted with the correct callout components (`<Danger>`, `<Warning>`, `<Info>`) that render natively in your documentation site. Your breaking change report is a documentation page, not a log file.

It also separates severity from noise. Not every change is a breaking change. The Sentinel distinguishes between:
- An endpoint that no longer exists (every client breaks immediately)
- A parameter that changed (clients using that parameter break)
- A description that was reworded (zero runtime impact)

Your team acts on what matters. The rest is logged, not alarmed.

## Who It's For

**Developer-relations teams** that maintain public APIs and need to communicate changes clearly and proactively.

**Platform and infrastructure teams** that ship internal APIs consumed by multiple other teams and need a paper trail of contract changes.

**Documentation teams** that are tired of finding out about breaking changes from a Slack message the day after the release.

## The Business Case

One undocumented breaking change to a public API can:
- Generate 50+ duplicate support tickets in 24 hours
- Cause integration partners to pause adoption pending investigation
- Trigger a hotfix cycle that costs more engineering time than the original release

The Sentinel eliminates that scenario by making the cost of a breaking change visible before it becomes a production incident. The report is in your docs. Your users see it the same time your team does. The conversation shifts from "why did this break?" to "here's what changed and here's how to update."

## Current State

The Sentinel is a production-ready Python CLI with:
- Pydantic v2 schema validation for docs.json
- Two-phase semantic diff engine (set difference + intersection analysis)
- Jinja2-powered MDX changelog rendering with severity-conditional Mintlify callouts
- Full pytest test suite across all three pipeline stages
- GitHub Actions CI workflow
- Docker support for containerized execution

It runs against any two OpenAPI 3.x specification files and integrates with any CI/CD system that can execute a Python script.

## What's Next

The roadmap is straightforward:
1. **Webhook delivery** — push the changelog diff to Slack, Linear, or any webhook endpoint at pipeline time, not just file output
2. **Schema drift detection** — extend beyond endpoint-level changes to catch response body schema mutations (field type changes, required field additions)
3. **Version history** — track diffs across multiple release pairs and surface trends (which endpoints change most frequently, which are stable)
4. **Mintlify native integration** — a Mintlify app extension that runs the Sentinel automatically on every docs deployment, without a separate CI step

The core engine is built to extend. None of these require a rewrite.
