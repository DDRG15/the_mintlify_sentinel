import os
import sys
import json
from unittest.mock import patch, MagicMock
import urllib.error
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from notifier import notify, _build_slack_payload, _build_discord_payload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CRITICAL_FINDING = {
    "signature": "DELETE /v1/users",
    "method": "DELETE",
    "path": "/v1/users",
    "severity": "CRITICAL",
    "change_type": "ENDPOINT_REMOVED",
    "description": "Endpoint was removed.",
}

MEDIUM_FINDING = {
    "signature": "GET /v1/products",
    "method": "GET",
    "path": "/v1/products",
    "severity": "MEDIUM",
    "change_type": "PARAMETERS_MODIFIED",
    "description": "Parameters changed.",
    "params_v1_count": 2,
    "params_v2_count": 1,
}

LOW_FINDING = {
    "signature": "GET /v1/orders",
    "method": "GET",
    "path": "/v1/orders",
    "severity": "LOW",
    "change_type": "DOCS_UPDATED",
    "description": "`summary` changed.",
}


# ---------------------------------------------------------------------------
# Slack payload builder
# ---------------------------------------------------------------------------

class TestBuildSlackPayload:

    def test_clean_diff_produces_check_header(self):
        payload = _build_slack_payload([])
        texts = [b.get("text", {}).get("text", "") for b in payload["blocks"]]
        assert any("Clean" in t or "✅" in t for t in texts)

    def test_critical_finding_produces_red_header(self):
        payload = _build_slack_payload([CRITICAL_FINDING])
        header = payload["blocks"][0]["text"]["text"]
        assert "🔴" in header

    def test_medium_only_produces_yellow_header(self):
        payload = _build_slack_payload([MEDIUM_FINDING])
        header = payload["blocks"][0]["text"]["text"]
        assert "🟡" in header

    def test_low_only_produces_blue_header(self):
        payload = _build_slack_payload([LOW_FINDING])
        header = payload["blocks"][0]["text"]["text"]
        assert "🔵" in header

    def test_finding_signature_appears_in_blocks(self):
        payload = _build_slack_payload([CRITICAL_FINDING])
        all_text = json.dumps(payload)
        assert "DELETE /v1/users" in all_text

    def test_more_than_10_findings_adds_overflow_notice(self):
        many = [CRITICAL_FINDING.copy() for _ in range(12)]
        for i, f in enumerate(many):
            f["signature"] = f"DELETE /v1/resource/{i}"
        payload = _build_slack_payload(many)
        all_text = json.dumps(payload)
        assert "more" in all_text

    def test_payload_is_valid_json_serialisable(self):
        payload = _build_slack_payload([CRITICAL_FINDING, MEDIUM_FINDING])
        assert json.dumps(payload)  # must not raise


# ---------------------------------------------------------------------------
# Discord payload builder
# ---------------------------------------------------------------------------

class TestBuildDiscordPayload:

    def test_clean_diff_produces_green_embed(self):
        payload = _build_discord_payload([])
        embed = payload["embeds"][0]
        assert "✅" in embed["title"]
        assert embed["color"] == 3066993  # green

    def test_critical_finding_produces_red_embed(self):
        payload = _build_discord_payload([CRITICAL_FINDING])
        summary_embed = payload["embeds"][0]
        assert summary_embed["color"] == 15158332  # red

    def test_finding_signature_appears_in_embeds(self):
        payload = _build_discord_payload([CRITICAL_FINDING])
        all_text = json.dumps(payload)
        assert "DELETE /v1/users" in all_text

    def test_more_than_9_findings_adds_overflow_embed(self):
        many = [CRITICAL_FINDING.copy() for _ in range(11)]
        for i, f in enumerate(many):
            f["signature"] = f"DELETE /v1/resource/{i}"
        payload = _build_discord_payload(many)
        # 1 summary + 9 individual + 1 overflow = 11 embeds
        assert len(payload["embeds"]) == 11

    def test_payload_is_valid_json_serialisable(self):
        payload = _build_discord_payload([CRITICAL_FINDING, LOW_FINDING])
        assert json.dumps(payload)


# ---------------------------------------------------------------------------
# notify() — skips gracefully when URLs are empty or placeholder
# ---------------------------------------------------------------------------

class TestNotifySkipBehaviour:

    def test_no_urls_returns_not_configured(self):
        result = notify([], slack_url="", discord_url="")
        assert result["slack"]["sent"] is False
        assert result["discord"]["sent"] is False

    def test_non_http_url_is_skipped(self):
        result = notify([], slack_url="not-a-url", discord_url="also-not-a-url")
        assert result["slack"]["sent"] is False
        assert result["discord"]["sent"] is False


# ---------------------------------------------------------------------------
# notify() — HTTP success and failure paths (mocked)
# ---------------------------------------------------------------------------

class TestNotifyHTTP:

    def test_slack_success_returns_sent_true(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = notify(
                [CRITICAL_FINDING],
                slack_url="https://hooks.slack.com/services/fake",
                discord_url="",
            )
        assert result["slack"]["sent"] is True
        assert result["slack"]["status"] == 200

    def test_discord_success_returns_sent_true(self):
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = notify(
                [CRITICAL_FINDING],
                slack_url="",
                discord_url="https://discord.com/api/webhooks/fake/fake",
            )
        assert result["discord"]["sent"] is True

    def test_slack_http_error_returns_sent_false(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url=None, code=400, msg="Bad Request", hdrs=None, fp=None
            ),
        ):
            result = notify(
                [],
                slack_url="https://hooks.slack.com/services/fake",
                discord_url="",
            )
        assert result["slack"]["sent"] is False
        assert result["slack"]["status"] == 400

    def test_discord_network_error_returns_sent_false(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            result = notify(
                [],
                slack_url="",
                discord_url="https://discord.com/api/webhooks/fake/fake",
            )
        assert result["discord"]["sent"] is False

    def test_notify_never_raises_on_exception(self):
        with patch("urllib.request.urlopen", side_effect=Exception("total failure")):
            result = notify(
                [CRITICAL_FINDING],
                slack_url="https://hooks.slack.com/services/fake",
                discord_url="https://discord.com/api/webhooks/fake/fake",
            )
        assert result["slack"]["sent"] is False
        assert result["discord"]["sent"] is False


# ---------------------------------------------------------------------------
# Environment variable fallback
# ---------------------------------------------------------------------------

class TestEnvVarFallback:

    def test_slack_url_read_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/env")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = notify([], slack_url="", discord_url="")
        assert result["slack"]["sent"] is True

    def test_discord_url_read_from_env(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/env/env")
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = notify([], slack_url="", discord_url="")
        assert result["discord"]["sent"] is True
