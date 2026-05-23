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
# SCHEMA_DRIFT renders field-level change lists inside <Warning>
# ---------------------------------------------------------------------------

class TestSchemaDriftRendering:

    _RESP_DRIFT = {
        "signature": "GET /v1/users",
        "method": "GET",
        "path": "/v1/users",
        "severity": "MEDIUM",
        "change_type": "SCHEMA_DRIFT",
        "description": "The response schema changed between versions.",
        "response_schema_changes": [
            {"field": "email",  "change": "field_removed"},
            {"field": "phone",  "change": "field_added"},
            {"field": "id",     "change": "type_changed", "from_type": "string", "to_type": "integer"},
            {"field": "name",   "change": "became_required"},
            {"field": "bio",    "change": "became_optional"},
        ],
        "request_body_schema_changes": [],
    }

    _REQ_DRIFT = {
        "signature": "POST /v1/users",
        "method": "POST",
        "path": "/v1/users",
        "severity": "MEDIUM",
        "change_type": "SCHEMA_DRIFT",
        "description": "The request body schema changed between versions.",
        "response_schema_changes": [],
        "request_body_schema_changes": [
            {"field": "email", "change": "field_added"},
        ],
    }

    def test_schema_drift_renders_warning_callout(self):
        render_changelog([self._RESP_DRIFT])
        content = _read_output()
        assert "<Warning>" in content
        assert "</Warning>" in content
        assert "<Danger>" not in content

    def test_response_schema_section_header_present(self):
        render_changelog([self._RESP_DRIFT])
        assert "Response schema field changes" in _read_output()

    def test_field_removed_renders_in_output(self):
        render_changelog([self._RESP_DRIFT])
        content = _read_output()
        assert "field removed" in content
        assert "email" in content

    def test_field_added_renders_in_output(self):
        render_changelog([self._RESP_DRIFT])
        content = _read_output()
        assert "field added" in content
        assert "phone" in content

    def test_type_changed_renders_with_from_and_to(self):
        render_changelog([self._RESP_DRIFT])
        content = _read_output()
        assert "type changed" in content
        assert "string" in content
        assert "integer" in content

    def test_became_required_renders(self):
        render_changelog([self._RESP_DRIFT])
        assert "became required" in _read_output()

    def test_became_optional_renders(self):
        render_changelog([self._RESP_DRIFT])
        assert "became optional" in _read_output()

    def test_empty_response_changes_omits_section_header(self):
        finding = {**self._RESP_DRIFT, "response_schema_changes": []}
        render_changelog([finding])
        assert "Response schema field changes" not in _read_output()

    def test_request_body_section_header_present(self):
        render_changelog([self._REQ_DRIFT])
        assert "Request body schema field changes" in _read_output()

    def test_request_body_field_added_renders(self):
        render_changelog([self._REQ_DRIFT])
        content = _read_output()
        assert "field added" in content
        assert "email" in content

    def test_schema_drift_finding_keys_present_in_output(self):
        render_changelog([self._RESP_DRIFT])
        content = _read_output()
        assert "SCHEMA_DRIFT" in content
        assert "GET /v1/users" in content


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
