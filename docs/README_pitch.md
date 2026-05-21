# The Mintlify Sentinel — Product Pitch

## The Problem

Every API-driven product ships breaking changes. Not because engineers are careless — because API evolution is unavoidable. Features get deprecated. Parameters get renamed. Response shapes change as the product grows.

The question isn't whether breaking changes happen. It's whether your team finds them before your customers do.

Right now, most teams don't. They push a release, wait for the support tickets, and spend the next two days tracing which change broke which integration partner. The cost isn't just engineering time. It's trust. A developer who hits a silent breaking change on a Friday afternoon doesn't file a ticket — they stop integrating.

## What the Sentinel Is

The Mintlify Sentinel is an automated API contract monitoring tool built specifically for teams that publish documentation on Mintlify. It runs as part of your release pipeline, takes 10 seconds, and produces a formatted, publishable changelog before any code reaches production.

It doesn't require a new dashboard, a SaaS subscription, or a new tab in the browser. It runs where your code runs. It outputs where your docs live. It gets out of the way.

## What Makes It Different

**Most API diff tools produce output engineers can't share.** Raw JSON, terminal text, or a wall of diffs that only make sense if you already understand the spec format. The Sentinel produces a Mintlify-native MDX file — formatted with the correct callout components (`<Danger>`, `<Warning>`, `<Info>`) that render natively in your documentation site. Your breaking change report is a documentation page, not a log file.

**It's not just "something changed" — it's exactly what changed.** A SCHEMA_DRIFT finding doesn't say "the response schema changed." It says: "`customer_id` field removed, `amount` type changed from `string` to `integer`, `email` became required." Developers reading the report know what to update in their code before they see the first error.

**It separates severity from noise.** Not every change is a breaking change. The Sentinel classifies:
- An endpoint that no longer exists → every client breaks immediately (CRITICAL)
- A parameter or schema field that changed → clients using that contract break (MEDIUM)
- A description that was reworded → zero runtime impact (LOW)

Your team acts on what matters. The noise is logged, not alarmed.

**It has memory.** Every run is recorded. The History tab shows which releases were clean, which had breaking changes, and which endpoints are changing most frequently across your release history. The Sentinel is not a point-in-time checker — it's a continuous audit trail.

## Who It's For

**Developer-relations teams** that maintain public APIs and need to communicate changes clearly, proactively, and automatically — before the support tickets arrive.

**Platform and infrastructure teams** that ship internal APIs consumed by multiple other teams. Every consumer needs a paper trail of what changed and when.

**Documentation teams** that find out about breaking changes from a Slack message the day after the release, and are tired of it.

**Startups and scale-ups** that want to look production-grade to their integration partners. A dated, formatted, severity-ranked API changelog in your documentation site signals that your team takes API stability seriously.

## The Business Case

One undocumented breaking change to a public API can:
- Generate 50+ duplicate support tickets in 24 hours
- Cause integration partners to pause adoption pending investigation
- Trigger a hotfix cycle that costs more engineering time than the original release
- Damage the trust of the developers building on your platform — permanently

The Sentinel eliminates that scenario by making the cost of a breaking change visible before it becomes a production incident. The report is in your docs. Your users see it the same time your team does. The conversation shifts from "why did this break?" to "here's exactly what changed and here's how to update."

## Current State — v1.3 (Production-Ready)

The Sentinel is a fully working Python CLI and browser UI with:

| Capability | Detail |
|------------|--------|
| **4-stage pipeline** | Config validation → semantic diff → MDX rendering → audit gate |
| **Severity classification** | CRITICAL (endpoint removed) / MEDIUM (params or schema changed) / LOW (docs updated) |
| **Granular schema diff** | Field-level change detection: added/removed fields, type changes, required/optional promotions |
| **MDX changelog** | Mintlify-native callouts with field-level sub-lists for schema changes |
| **Browser UI** | Streamlit — upload specs, run, view findings, download changelog, send notifications |
| **Notifications** | Slack + Discord webhooks — CLI flags, env vars, or browser sidebar |
| **Version history** | Every run recorded to `history.json`; History tab in browser UI |
| **YAML + JSON support** | Auto-detects format from content — handles any valid OpenAPI 3.x spec |
| **Docker** | Full pipeline and browser UI run in a container |
| **CI/CD** | GitHub Actions workflow included |
| **Test suite** | 95 automated tests — all pipeline stages covered |

It runs against any two OpenAPI 3.x specification files and integrates with any CI/CD system that can execute a Python script.

## What's Next

The roadmap is straightforward. The core engine is built to extend — none of these require a rewrite.

**GitHub push + CI badge (15 min)**
Push to a public GitHub repo. The CI badge makes the project production-grade at a glance.

**React frontend (when client-facing)**
Replace the Streamlit UI with a React + FastAPI frontend for demos, sales calls, and investor presentations. The Python backend — the diff engine, the renderer, the notifier — doesn't change. React calls a FastAPI wrapper instead of Python directly.

**Mintlify native integration (future)**
A Mintlify app extension that runs the Sentinel automatically on every docs deployment — no separate CI step required. Zero friction for Mintlify users. Dependent on Mintlify's app extension SDK (not yet public).

## The Opportunity

The Sentinel is already solving a real problem for teams that publish APIs with Mintlify docs. The natural next step is distributing it as a product: a Mintlify-native integration that any team can enable in one click, with no pipeline setup required.

The technical foundation is solid. The pipeline works. The output is publication-ready. The question is how far to take it.
