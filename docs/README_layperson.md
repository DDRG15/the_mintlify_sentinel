# What Is The Mintlify Sentinel?

Think of the Sentinel as a **spell checker for your API documentation** — but instead of catching typos, it catches the kind of changes that break things for your users without anyone noticing until the complaints start rolling in.

## The Problem It Solves

When a software product has a public API (a way for other apps to talk to it), that API is a contract: "Send me a request this way, and I'll always respond that way."

When developers update the API and that contract changes — a feature gets removed, a required piece of information gets renamed — every app that was relying on the old version stops working. Silently. No warning. Users just see errors.

The Sentinel watches those changes. Before your team pushes an update live, it reads both versions of the API, compares them, and tells you exactly what changed and how serious it is.

## What It Produces

A clean, readable report — formatted for your documentation website — that lists every change in plain language:

- **Red alert (CRITICAL):** Something was completely removed. Anyone using it will immediately break.
- **Yellow warning (MEDIUM):** The way you call this feature changed. Some users will be affected.
- **Blue notice (LOW):** Only the description text changed. Nothing breaks, but it's worth reviewing.

## Who Uses This

Your engineering or developer-relations team runs it as part of their regular release process. It takes about 10 seconds. The report is automatically added to your documentation site.

## What You Don't Need to Know

You don't need to understand code, APIs, or documentation formats to benefit from this tool. The report it produces is readable by anyone on the team — product, support, sales — and gives everyone a clear picture of what changed before users are impacted.
