import os
import sys
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from architect_render import render_changelog

OUTPUT_PATH = os.path.join(ROOT_DIR, "output", "changelog.mdx")


def _read_output() -> str:
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Clean diff
# ---------------------------------------------------------------------------

class TestCleanDiff:

    def test_empty_findings_renders_check_callout(self):
        render_changelog([])
        content = _read_output()
        assert "<Check>" in content
        assert "<Danger>" not in content
        assert "<Warning>" not in content
        assert "<Info>" not in content

    def test_empty_findings_does_not_render_action_required_text(self):
        render_changelog([])
        content = _read_output()
        assert "Review carefully before deploying" not in content


# ---------------------------------------------------------------------------
# CRITICAL renders as <Danger>
# ---------------------------------------------------------------------------

class TestCriticalRendering:

    def test_critical_finding_renders_danger_callout(self):
        render_changelog([{
            "signature": "DELETE /v1/users",
            "method": "DELETE",
            "path": "/v1/users",
            "severity": "CRITICAL",
            "change_type": "ENDPOINT_REMOVED",
            "description": "Endpoint was removed.",
        }])
        content = _read_output()
        assert "<Danger>" in content
        assert "</Danger>" in content
        assert "CRITICAL" in content
        assert "DELETE /v1/users" in content

    def test_critical_does_not_render_warning_or_info(self):
        render_changelog([{
            "signature": "GET /v1/items",
            "method": "GET",
            "path": "/v1/items",
            "severity": "CRITICAL",
            "change_type": "ENDPOINT_REMOVED",
            "description": "Gone.",
        }])
        content = _read_output()
        assert "<Warning>" not in content
        assert "<Info>" not in content


# ---------------------------------------------------------------------------
# MEDIUM renders as <Warning>
# ---------------------------------------------------------------------------

class TestMediumRendering:

    def test_medium_finding_renders_warning_callout(self):
        render_changelog([{
            "signature": "GET /v1/products",
            "method": "GET",
            "path": "/v1/products",
            "severity": "MEDIUM",
            "change_type": "PARAMETERS_MODIFIED",
            "description": "Parameters were changed.",
            "params_v1_count": 2,
            "params_v2_count": 1,
        }])
        content = _read_output()
        assert "<Warning>" in content
        assert "</Warning>" in content
        assert "<Danger>" not in content
        assert "<Info>" not in content

    def test_medium_signature_appears_in_output(self):
        render_changelog([{
            "signature": "POST /v1/orders",
            "method": "POST",
            "path": "/v1/orders",
            "severity": "MEDIUM",
            "change_type": "PARAMETERS_MODIFIED",
            "description": "Params changed.",
            "params_v1_count": 3,
            "params_v2_count": 2,
        }])
        assert "POST /v1/orders" in _read_output()


# ---------------------------------------------------------------------------
# LOW renders as <Info>
# ---------------------------------------------------------------------------

class TestLowRendering:

    def test_low_finding_renders_info_callout(self):
        render_changelog([{
            "signature": "GET /v1/orders",
            "method": "GET",
            "path": "/v1/orders",
            "severity": "LOW",
            "change_type": "DOCS_UPDATED",
            "description": "`summary` changed.",
        }])
        content = _read_output()
        assert "<Info>" in content
        assert "</Info>" in content
        assert "<Danger>" not in content
        assert "<Warning>" not in content


# ---------------------------------------------------------------------------
# Mixed severities render all three callouts in correct order
# ---------------------------------------------------------------------------

class TestMixedSeverityRendering:

    def test_all_three_severities_render_correct_callouts(self):
        render_changelog([
            {
                "signature": "DELETE /v1/admin",
                "method": "DELETE",
                "path": "/v1/admin",
                "severity": "CRITICAL",
                "change_type": "ENDPOINT_REMOVED",
                "description": "Removed.",
            },
            {
                "signature": "GET /v1/products",
                "method": "GET",
                "path": "/v1/products",
                "severity": "MEDIUM",
                "change_type": "PARAMETERS_MODIFIED",
                "description": "Params changed.",
                "params_v1_count": 1,
                "params_v2_count": 0,
            },
            {
                "signature": "GET /v1/orders",
                "method": "GET",
                "path": "/v1/orders",
                "severity": "LOW",
                "change_type": "DOCS_UPDATED",
                "description": "Docs updated.",
            },
        ])
        content = _read_output()
        assert "<Danger>" in content
        assert "<Warning>" in content
        assert "<Info>" in content
        assert content.index("<Danger>") < content.index("<Warning>")
        assert content.index("<Warning>") < content.index("<Info>")
