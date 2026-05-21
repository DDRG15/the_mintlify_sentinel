# =============================================================================
# notifier.py
# The Mintlify Sentinel — Slack & Discord Notification Dispatcher
#
# PURPOSE:
#   Sends a formatted findings summary to Slack and/or Discord after the
#   diff engine completes. Notification failure never blocks the pipeline —
#   the Sentinel always exits 0 from Stage 4 regardless of whether the
#   notification succeeded.
#
# SLACK SETUP:
#   1. Go to https://api.slack.com/apps → Create New App → From Scratch
#   2. Enable "Incoming Webhooks" under Features
#   3. Click "Add New Webhook to Workspace" → select a channel → copy the URL
#   4. Set environment variable: SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
#      OR pass via CLI: python main.py --slack-webhook https://hooks.slack.com/services/...
#
# DISCORD SETUP:
#   1. Open your Discord server → go to the channel you want alerts in
#   2. Channel Settings (gear icon) → Integrations → Webhooks → New Webhook
#   3. Copy the webhook URL
#   4. Set environment variable: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
#      OR pass via CLI: python main.py --discord-webhook https://discord.com/api/webhooks/...
#
# USAGE (called by main.py):
#   from notifier import notify
#   notify(findings, slack_url="...", discord_url="...")
#
# EXIT CODE: Never raises. Returns dict with per-channel success/failure.
# =============================================================================

import json
import urllib.request
import urllib.error
import os


# =============================================================================
# SECTION 1 — SEVERITY FORMATTING
# =============================================================================

# Emoji and color constants used across both platforms.
_SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "MEDIUM":   "🟡",
    "LOW":      "🔵",
}

# Discord embed sidebar color per severity (decimal RGB).
_DISCORD_COLOR = {
    "CRITICAL": 15158332,  # red    #E74C3C
    "MEDIUM":   15105570,  # orange #E67E22
    "LOW":      3447003,   # blue   #3498DB
    "CLEAN":    3066993,   # green  #2ECC71
}


def _severity_counts(findings: list) -> tuple:
    critical = sum(1 for f in findings if f.get("severity") == "CRITICAL")
    medium   = sum(1 for f in findings if f.get("severity") == "MEDIUM")
    low      = sum(1 for f in findings if f.get("severity") == "LOW")
    return critical, medium, low


# =============================================================================
# SECTION 2 — HTTP DISPATCHER
# =============================================================================

def _post_json(url: str, payload: dict) -> tuple:
    """
    [POSTs a JSON payload to `url` using only stdlib urllib — no requests dep.
     Returns (success: bool, status_code: int, error_message: str).]
    """
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "MintlifySentinel/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, resp.status, ""
    except urllib.error.HTTPError as exc:
        return False, exc.code, str(exc.reason)
    except urllib.error.URLError as exc:
        return False, 0, str(exc.reason)
    except Exception as exc:
        return False, 0, str(exc)


# =============================================================================
# SECTION 3 — SLACK FORMATTER
# =============================================================================

def _build_slack_payload(findings: list) -> dict:
    """
    [Builds a Slack Block Kit payload. Uses a header block for the title,
     a context block for the summary line, and individual section blocks
     for each finding — capped at 10 to avoid Slack's 50-block limit on
     large diffs.]
    """
    critical, medium, low = _severity_counts(findings)
    total = len(findings)

    if not findings:
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Mintlify Sentinel — API Surface Clean",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "No contract changes detected. The API surface is stable.",
                    },
                },
            ]
        }

    # Determine the header tone from the highest severity present.
    if critical:
        header_emoji = "🔴"
        header_text  = "Mintlify Sentinel — Breaking Changes Detected"
    elif medium:
        header_emoji = "🟡"
        header_text  = "Mintlify Sentinel — Parameter Changes Detected"
    else:
        header_emoji = "🔵"
        header_text  = "Mintlify Sentinel — Documentation Changes Detected"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{header_emoji} {header_text}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{total} finding(s)* — "
                    f"🔴 {critical} CRITICAL   "
                    f"🟡 {medium} MEDIUM   "
                    f"🔵 {low} LOW"
                ),
            },
        },
        {"type": "divider"},
    ]

    # List individual findings — cap at 10 so the message stays readable.
    display_findings = findings[:10]
    for f in display_findings:
        emoji = _SEVERITY_EMOJI.get(f.get("severity", "LOW"), "•")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *{f.get('severity')} — {f.get('change_type')}*\n"
                    f"`{f.get('signature')}`\n"
                    f"{f.get('description', '')}"
                ),
            },
        })

    if len(findings) > 10:
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"_...and {len(findings) - 10} more. See output/changelog.mdx for the full report._",
            }],
        })

    return {"blocks": blocks}


# =============================================================================
# SECTION 4 — DISCORD FORMATTER
# =============================================================================

def _build_discord_payload(findings: list) -> dict:
    """
    [Builds a Discord Webhook payload using the embeds API.
     One embed per finding — capped at 10 (Discord limit is 10 embeds/message).
     Clean diffs get a single green embed.]
    """
    critical, medium, low = _severity_counts(findings)
    total = len(findings)

    if not findings:
        return {
            "embeds": [{
                "title": "✅ Mintlify Sentinel — API Surface Clean",
                "description": "No contract changes detected. The API surface is stable.",
                "color": _DISCORD_COLOR["CLEAN"],
            }]
        }

    if critical:
        summary_title = "🔴 Mintlify Sentinel — Breaking Changes Detected"
        top_color     = _DISCORD_COLOR["CRITICAL"]
    elif medium:
        summary_title = "🟡 Mintlify Sentinel — Parameter Changes Detected"
        top_color     = _DISCORD_COLOR["MEDIUM"]
    else:
        summary_title = "🔵 Mintlify Sentinel — Documentation Changes Detected"
        top_color     = _DISCORD_COLOR["LOW"]

    # Summary embed (always first).
    summary_embed = {
        "title": summary_title,
        "description": (
            f"**{total} finding(s)**\n"
            f"🔴 {critical} CRITICAL   "
            f"🟡 {medium} MEDIUM   "
            f"🔵 {low} LOW"
        ),
        "color": top_color,
    }

    embeds = [summary_embed]

    # Individual finding embeds — Discord hard limit is 10 per message.
    # Reserve slot 0 for the summary, so max 9 individual findings shown.
    display_findings = findings[:9]
    for f in display_findings:
        sev    = f.get("severity", "LOW")
        emoji  = _SEVERITY_EMOJI.get(sev, "•")
        color  = _DISCORD_COLOR.get(sev, _DISCORD_COLOR["LOW"])
        embeds.append({
            "title": f"{emoji} {f.get('change_type')} — {sev}",
            "description": (
                f"**`{f.get('signature')}`**\n"
                f"{f.get('description', '')}"
            ),
            "color": color,
        })

    if len(findings) > 9:
        embeds.append({
            "title": "...",
            "description": f"*...and {len(findings) - 9} more. See `output/changelog.mdx` for the full report.*",
            "color": _DISCORD_COLOR["CLEAN"],
        })

    return {"embeds": embeds}


# =============================================================================
# SECTION 5 — PUBLIC API
# =============================================================================

def notify(
    findings: list,
    slack_url: str | None = None,
    discord_url: str | None = None,
) -> dict:
    """
    [Sends findings to Slack and/or Discord. Both channels are optional —
     passing None (or an empty string) for a URL skips that channel silently.

     Returns a result dict:
       {
         "slack":   {"sent": bool, "status": int, "error": str},
         "discord": {"sent": bool, "status": int, "error": str},
       }

     Never raises. Notification failures are printed as warnings and the
     pipeline continues. A broken webhook URL is an ops problem, not a
     code problem.]
    """

    # Fall back to environment variables if CLI flags were not provided.
    slack_url   = slack_url   or os.environ.get("SLACK_WEBHOOK_URL",   "")
    discord_url = discord_url or os.environ.get("DISCORD_WEBHOOK_URL", "")

    results = {
        "slack":   {"sent": False, "status": 0, "error": "not configured"},
        "discord": {"sent": False, "status": 0, "error": "not configured"},
    }

    # ── Slack ─────────────────────────────────────────────────────────────
    if slack_url and slack_url.startswith("http"):
        payload = _build_slack_payload(findings)
        ok, code, err = _post_json(slack_url, payload)
        results["slack"] = {"sent": ok, "status": code, "error": err}
        if ok:
            print(f"[notifier] ✓ Slack notification sent (HTTP {code}).")
        else:
            print(f"[notifier] ✗ Slack notification failed (HTTP {code}): {err}")
    else:
        print("[notifier]   Slack webhook not configured — skipping.")

    # ── Discord ───────────────────────────────────────────────────────────
    if discord_url and discord_url.startswith("http"):
        payload = _build_discord_payload(findings)
        ok, code, err = _post_json(discord_url, payload)
        results["discord"] = {"sent": ok, "status": code, "error": err}
        if ok:
            print(f"[notifier] ✓ Discord notification sent (HTTP {code}).")
        else:
            print(f"[notifier] ✗ Discord notification failed (HTTP {code}): {err}")
    else:
        print("[notifier]   Discord webhook not configured — skipping.")

    return results
