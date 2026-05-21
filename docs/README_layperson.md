# The Mintlify Sentinel — Plain Language Guide

## The short version

The Sentinel checks whether software updates will break anything for your customers before your team publishes them. It takes 10 seconds, runs automatically, and produces a plain-language report that anyone on the team can read.

---

## The problem it solves

When a software product has a way for other apps to connect to it — called an API — there is an invisible rulebook that governs how that connection works. It says things like: "If you want customer data, ask for it this way, and you'll always get it back in this format."

Your engineering team is constantly improving the product. Sometimes those improvements change the rulebook. A feature gets removed. A data field gets renamed. A required piece of information is added.

The connected apps were never told. Their instructions still describe the old rules. So they break. Silently. No warning. Your integration partner's app throws errors on a Tuesday morning. Their users see failed transactions. By the time anyone figures out what happened, the damage is done.

This is called a **breaking change**. It happens all the time at companies with public APIs, and most teams have no systematic way to catch it before it reaches their customers.

---

## What the Sentinel does

Before your team publishes an update, the Sentinel reads both the old version and the new version of the rulebook side by side and finds every single difference. Then it tells you:

**Red alert — CRITICAL**
Something was completely removed. Any connected app using that feature will stop working the moment the update goes live. Fix it or warn your partners first.

**Yellow warning — MEDIUM**
The way a feature works changed. Maybe it now requires a different piece of information. Maybe the data it returns looks different. The Sentinel tells you not just that something changed, but exactly what: "The `customer_id` field was removed" or "The `amount` field changed from text to a number." No guessing, no opening two files and comparing by hand.

**Blue notice — LOW**
Only the description text was updated. Nothing actually breaks — but your documentation now says something different, and your team should review it.

---

## The report

The Sentinel automatically publishes a formatted, color-coded report to your documentation website — the same place your developers and integration partners read your technical docs. They see it the same day you publish the update. The conversation shifts from "why did this break?" to "here's what changed and here's how to update your code."

---

## History

Every time the Sentinel runs, it records the result. Over time you build a complete picture: which releases were clean, which had breaking changes, which features change most often. This lives in the browser interface under the History tab — a table of every past check, with the ability to drill into any run and see its individual findings.

---

## Notifications

The moment the Sentinel finishes, it can automatically send a message to your team's Slack channel or Discord server. It lists exactly what changed, how many issues were found, and how serious they are. No one needs to remember to check a dashboard. The report finds them.

---

## How your team uses it

**Option 1 — The browser (no technical knowledge required)**
A member of the engineering team opens the Sentinel's web page, uploads two files (the old API rulebook and the new one), and clicks a button. Results appear in about 10 seconds as colored cards. Anyone on the team can read them. The report can be downloaded directly from the page.

**Option 2 — Automatic (for the release pipeline)**
Once set up by a developer, the Sentinel runs automatically every time the team prepares a release. No one has to remember to check anything.

---

## What everyone on the team gets out of it

| Role | What changes |
|------|-------------|
| **Engineering** | Breaking changes caught before production, not after |
| **Developer relations** | Partners and integrators see a clear changelog before the release ships |
| **Support** | Fewer "why did my integration break" tickets |
| **Product / leadership** | Visibility into API stability — which features are changing, which are stable |

---

## What you don't need to know

You don't need to understand what an API is. You don't need to know what OpenAPI, JSON, or YAML mean. You don't need to read code.

What matters is this: your product makes promises to the software that connects to it. The Sentinel makes sure your team knows before you break those promises — not after.
