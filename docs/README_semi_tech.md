# The Mintlify Sentinel — Overview for the Technically Curious

## What This Tool Does

The Sentinel is a command-line tool that compares two versions of an API specification file and generates a formatted report of everything that changed between them.

An API specification is a document — written in a standard format called OpenAPI — that describes exactly how a software service works: what features it has, how you call them, and what you get back. When that document changes, some of those changes are harmless. Others break every application that was relying on the old behavior.

The Sentinel automatically tells you which is which.

## How It Works (Without the Code)

You give it two files: the old version of the API spec and the new version. It runs them through a comparison engine that looks for three types of changes:

1. **Critical:** A feature was completely removed. Every caller using it will get an error the moment the update goes live.
2. **Medium:** The inputs a feature expects changed. Apps that were sending the old inputs will fail.
3. **Low:** Only the description text changed. No functional impact — but your documentation team should review the new wording.

It then generates a formatted report in a file format called MDX, which is the native format of the Mintlify documentation platform. You commit that file to your docs repository, and it appears automatically as a formatted changelog page on your documentation site.

## Why This Matters

Without a tool like this, breaking API changes are discovered by your users — not your team. A developer integrating with your API wakes up one morning to find their application throwing errors, traces it back to your last release, and files a support ticket (or just silently stops using your product).

The Sentinel surfaces those changes before the release, not after.

## What It's Built On

- **Python** — the programming language it's written in
- **Pydantic** — validates that your documentation site config file is structurally correct before anything else runs
- **Jinja2** — a templating system that formats the findings into a ready-to-publish document
- **Mintlify** — the documentation platform the output is designed for

You don't need to know any of these to use the tool. You just need Python installed and one terminal command.
