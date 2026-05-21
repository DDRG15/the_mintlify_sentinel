# What Is The Mintlify Sentinel?

Think of the Sentinel as a **spell checker for your API documentation** — but instead of catching typos, it catches the kind of changes that break things for your users without anyone noticing until the complaints start rolling in.

## The Problem It Solves

When a software product has a public API (a way for other apps to talk to it), that API is a contract: "Send me a request this way, and I'll always respond that way."

When developers update the API and that contract changes — a feature gets removed, a required piece of information gets renamed — every app that was relying on the old version stops working. Silently. No warning. Users just see errors.

The Sentinel watches those changes. Before your team pushes an update live, it reads both versions of the API, compares them, and tells you exactly what changed and how serious it is.

## How Your Team Uses It

There are two ways to run the Sentinel — one requires no technical knowledge at all:

**Option 1 — Browser interface (no terminal needed)**
Open a browser, go to the Sentinel's web page, upload the two API files, and click a button. The results appear on screen as colored alerts. You can download the report directly from the page.

**Option 2 — Command line (for developers)**
A developer runs a single command from their terminal. The report is automatically generated and saved to a file.

Either way, the whole process takes about 10 seconds.

## What It Produces

A clean, readable report — formatted for your documentation website — that lists every change in plain language:

- **Red alert (CRITICAL):** Something was completely removed. Anyone using it will immediately break.
- **Yellow warning (MEDIUM):** The way you call this feature changed. Some users will be affected.
- **Blue notice (LOW):** Only the description text changed. Nothing breaks, but it's worth reviewing.

The report is published directly to your documentation site. Your users see it before any code reaches production.

## Notifications

When the Sentinel finishes, it can automatically send a summary message to your team's Slack channel or Discord server — listing exactly which changes were detected and how serious they are. No one needs to remember to check a report; the report finds them.

## Who Uses This

Your engineering or developer-relations team runs it as part of their regular release process. Everyone else on the team — product, support, sales — reads the report and knows what changed before your users are impacted.

## What You Don't Need to Know

You don't need to understand code, APIs, or documentation formats to benefit from this tool. The report it produces is readable by anyone on the team, and the browser interface means anyone can trigger a check without touching a terminal.
