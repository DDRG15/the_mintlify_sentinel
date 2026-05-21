import os
import sys
import json
import tempfile
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from judge_diff import (
    load_openapi,
    extract_contracts,
    run_diff,
    _find_removed_endpoints,
    _find_modified_endpoints,
    _combine_and_sort,
    _extract_json_schema,
    _get_primary_response_schema,
    _diff_schema_properties,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec(paths: dict) -> dict:
    return {
        "openapi": "3.0.1",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": paths,
    }


def _write_spec(paths: dict) -> str:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(_make_spec(paths), tmp)
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# extract_contracts()
# ---------------------------------------------------------------------------

class TestExtractContracts:

    def test_extracts_get_endpoint(self):
        doc = _make_spec({"/users": {"get": {"summary": "List users"}}})
        assert "GET /users" in extract_contracts(doc)

    def test_extracts_multiple_methods_on_same_path(self):
        doc = _make_spec({
            "/users": {
                "get": {"summary": "List"},
                "post": {"summary": "Create"},
            }
        })
        contracts = extract_contracts(doc)
        assert "GET /users" in contracts
        assert "POST /users" in contracts

    def test_ignores_vendor_extension_keys(self):
        doc = _make_spec({
            "/users": {
                "get": {"summary": "List"},
                "x-internal": True,
            }
        })
        contracts = extract_contracts(doc)
        assert "GET /users" in contracts
        assert len(contracts) == 1

    def test_ignores_non_http_method_structural_keys(self):
        doc = _make_spec({
            "/users": {
                "get": {"summary": "List"},
                "summary": "User operations",
                "parameters": [],
            }
        })
        assert len(extract_contracts(doc)) == 1

    def test_normalises_method_to_uppercase(self):
        doc = _make_spec({"/items": {"get": {}}})
        contracts = extract_contracts(doc)
        assert "GET /items" in contracts
        assert "get /items" not in contracts

    def test_empty_spec_returns_empty_dict(self):
        doc = {"openapi": "3.0.1", "info": {}}
        assert extract_contracts(doc) == {}

    def test_spec_with_empty_paths_returns_empty_dict(self):
        assert extract_contracts(_make_spec({})) == {}


# ---------------------------------------------------------------------------
# CRITICAL — removed endpoints
# ---------------------------------------------------------------------------

class TestCriticalFindings:

    def test_removed_endpoint_produces_critical_finding(self):
        v1 = extract_contracts(_make_spec({
            "/users": {"get": {}},
            "/orders": {"delete": {}},
        }))
        v2 = extract_contracts(_make_spec({"/users": {"get": {}}}))
        findings = _find_removed_endpoints(v1, v2)
        assert len(findings) == 1
        assert findings[0]["severity"] == "CRITICAL"
        assert findings[0]["change_type"] == "ENDPOINT_REMOVED"
        assert findings[0]["signature"] == "DELETE /orders"

    def test_multiple_removals_all_surface_as_critical(self):
        v1 = extract_contracts(_make_spec({
            "/a": {"get": {}},
            "/b": {"post": {}},
            "/c": {"delete": {}},
        }))
        v2 = extract_contracts(_make_spec({}))
        findings = _find_removed_endpoints(v1, v2)
        assert len(findings) == 3
        assert all(f["severity"] == "CRITICAL" for f in findings)

    def test_clean_diff_produces_no_critical_findings(self):
        v1 = extract_contracts(_make_spec({"/users": {"get": {}}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": {}}}))
        assert _find_removed_endpoints(v1, v2) == []

    def test_added_endpoint_does_not_produce_critical_finding(self):
        v1 = extract_contracts(_make_spec({"/users": {"get": {}}}))
        v2 = extract_contracts(_make_spec({
            "/users": {"get": {}},
            "/orders": {"get": {}},
        }))
        assert _find_removed_endpoints(v1, v2) == []


# ---------------------------------------------------------------------------
# MEDIUM — parameter modifications
# ---------------------------------------------------------------------------

class TestMediumFindings:

    def test_parameter_added_produces_medium_finding(self):
        v1 = extract_contracts(_make_spec({"/users": {"get": {"parameters": []}}}))
        v2 = extract_contracts(_make_spec({
            "/users": {"get": {"parameters": [{"name": "limit", "in": "query"}]}}
        }))
        findings = _find_modified_endpoints(v1, v2)
        medium = [f for f in findings if f["severity"] == "MEDIUM"]
        assert len(medium) == 1
        assert medium[0]["change_type"] == "PARAMETERS_MODIFIED"

    def test_parameter_removed_produces_medium_finding(self):
        v1 = extract_contracts(_make_spec({
            "/users": {"get": {"parameters": [{"name": "limit", "in": "query"}]}}
        }))
        v2 = extract_contracts(_make_spec({"/users": {"get": {"parameters": []}}}))
        medium = [f for f in _find_modified_endpoints(v1, v2) if f["severity"] == "MEDIUM"]
        assert len(medium) == 1

    def test_medium_finding_includes_param_counts(self):
        v1 = extract_contracts(_make_spec({
            "/users": {"get": {"parameters": [
                {"name": "limit", "in": "query"},
                {"name": "offset", "in": "query"},
            ]}}
        }))
        v2 = extract_contracts(_make_spec({"/users": {"get": {"parameters": []}}}))
        medium = [f for f in _find_modified_endpoints(v1, v2) if f["severity"] == "MEDIUM"][0]
        assert medium["params_v1_count"] == 2
        assert medium["params_v2_count"] == 0

    def test_medium_suppresses_low_for_same_endpoint(self):
        v1 = extract_contracts(_make_spec({
            "/users": {"get": {
                "summary": "List users v1",
                "parameters": [{"name": "limit", "in": "query"}],
            }}
        }))
        v2 = extract_contracts(_make_spec({
            "/users": {"get": {
                "summary": "List users v2",
                "parameters": [],
            }}
        }))
        findings = _find_modified_endpoints(v1, v2)
        assert len(findings) == 1
        assert findings[0]["severity"] == "MEDIUM"

    def test_identical_parameters_produce_no_medium_finding(self):
        params = [{"name": "id", "in": "path", "required": True}]
        v1 = extract_contracts(_make_spec({"/users/{id}": {"get": {"parameters": params}}}))
        v2 = extract_contracts(_make_spec({"/users/{id}": {"get": {"parameters": params}}}))
        medium = [f for f in _find_modified_endpoints(v1, v2) if f["severity"] == "MEDIUM"]
        assert medium == []


# ---------------------------------------------------------------------------
# LOW — documentation updates
# ---------------------------------------------------------------------------

class TestLowFindings:

    def test_summary_change_produces_low_finding(self):
        v1 = extract_contracts(_make_spec({"/users": {"get": {"summary": "List users"}}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": {"summary": "Retrieve users"}}}))
        low = [f for f in _find_modified_endpoints(v1, v2) if f["severity"] == "LOW"]
        assert len(low) == 1
        assert low[0]["change_type"] == "DOCS_UPDATED"

    def test_description_change_produces_low_finding(self):
        v1 = extract_contracts(_make_spec({"/items": {"get": {"description": "Returns all items."}}}))
        v2 = extract_contracts(_make_spec({"/items": {"get": {"description": "Returns all available items."}}}))
        low = [f for f in _find_modified_endpoints(v1, v2) if f["severity"] == "LOW"]
        assert len(low) == 1

    def test_identical_docs_produce_no_low_finding(self):
        op = {"summary": "Get item", "description": "Fetches one item by ID."}
        v1 = extract_contracts(_make_spec({"/items/{id}": {"get": op}}))
        v2 = extract_contracts(_make_spec({"/items/{id}": {"get": op}}))
        assert _find_modified_endpoints(v1, v2) == []

    def test_no_docs_fields_produces_no_finding(self):
        v1 = extract_contracts(_make_spec({"/ping": {"get": {}}}))
        v2 = extract_contracts(_make_spec({"/ping": {"get": {}}}))
        assert _find_modified_endpoints(v1, v2) == []


# ---------------------------------------------------------------------------
# MEDIUM — schema drift (response / request body changes)
# ---------------------------------------------------------------------------

class TestSchemaDrift:

    def test_response_schema_change_produces_schema_drift(self):
        v1_op = {"responses": {"200": {"content": {"application/json": {
            "schema": {"type": "object", "properties": {"id": {"type": "string"}}}}}}}}
        v2_op = {"responses": {"200": {"content": {"application/json": {
            "schema": {"type": "object", "properties": {"id": {"type": "integer"}}}}}}}}
        v1 = extract_contracts(_make_spec({"/users": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        assert len(findings) == 1
        assert findings[0]["change_type"] == "SCHEMA_DRIFT"
        assert findings[0]["severity"] == "MEDIUM"
        assert "response schema" in findings[0]["description"]

    def test_request_body_change_produces_schema_drift(self):
        v1_op = {"requestBody": {"content": {"application/json": {
            "schema": {"required": ["name"], "properties": {"name": {"type": "string"}}}}}}}
        v2_op = {"requestBody": {"content": {"application/json": {
            "schema": {"required": ["name", "email"], "properties": {
                "name": {"type": "string"}, "email": {"type": "string"}}}}}}}
        v1 = extract_contracts(_make_spec({"/users": {"post": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"post": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        assert len(findings) == 1
        assert findings[0]["change_type"] == "SCHEMA_DRIFT"
        assert "request body schema" in findings[0]["description"]

    def test_identical_schema_produces_no_drift(self):
        op = {"responses": {"200": {"content": {"application/json": {
            "schema": {"type": "object", "properties": {"id": {"type": "string"}}}}}}}}
        v1 = extract_contracts(_make_spec({"/users": {"get": op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": op}}))
        assert _find_modified_endpoints(v1, v2) == []

    def test_schema_drift_suppressed_by_parameters_modified(self):
        v1_op = {
            "parameters": [{"name": "limit", "in": "query"}],
            "responses": {"200": {"content": {"application/json": {
                "schema": {"type": "object", "properties": {"id": {"type": "string"}}}}}}},
        }
        v2_op = {
            "parameters": [],
            "responses": {"200": {"content": {"application/json": {
                "schema": {"type": "object", "properties": {"id": {"type": "integer"}}}}}}},
        }
        v1 = extract_contracts(_make_spec({"/users": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        assert len(findings) == 1
        assert findings[0]["change_type"] == "PARAMETERS_MODIFIED"

    def test_schema_drift_suppresses_docs_updated(self):
        v1_op = {
            "summary": "Get user",
            "responses": {"200": {"content": {"application/json": {
                "schema": {"properties": {"id": {"type": "string"}}}}}}},
        }
        v2_op = {
            "summary": "Retrieve user",
            "responses": {"200": {"content": {"application/json": {
                "schema": {"properties": {"id": {"type": "integer"}}}}}}},
        }
        v1 = extract_contracts(_make_spec({"/users/{id}": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users/{id}": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        assert len(findings) == 1
        assert findings[0]["change_type"] == "SCHEMA_DRIFT"


# ---------------------------------------------------------------------------
# Sorting and combining
# ---------------------------------------------------------------------------

class TestCombineAndSort:

    def test_findings_sorted_critical_before_medium_before_low(self):
        low    = {"severity": "LOW",      "signature": "GET /z"}
        medium = {"severity": "MEDIUM",   "signature": "GET /m"}
        crit   = {"severity": "CRITICAL", "signature": "GET /a"}
        result = _combine_and_sort([crit], [medium, low])
        assert result[0]["severity"] == "CRITICAL"
        assert result[1]["severity"] == "MEDIUM"
        assert result[2]["severity"] == "LOW"

    def test_same_severity_sorted_alphabetically(self):
        f1 = {"severity": "CRITICAL", "signature": "GET /z"}
        f2 = {"severity": "CRITICAL", "signature": "DELETE /a"}
        result = _combine_and_sort([f1], [f2])
        assert result[0]["signature"] == "DELETE /a"
        assert result[1]["signature"] == "GET /z"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_spec_vs_empty_spec_is_clean(self):
        path_a = _write_spec({})
        path_b = _write_spec({})
        try:
            assert run_diff(path_a, path_b) == []
        finally:
            os.unlink(path_a)
            os.unlink(path_b)

    def test_malformed_spec_raises_runtime_error(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        tmp.write("not valid json {{{")
        tmp.close()
        try:
            # With pyyaml installed the loader tries JSON then YAML; both fail
            # so the message is "INVALID FORMAT". Without pyyaml it is
            # "INVALID JSON". Both contain "INVALID".
            with pytest.raises(RuntimeError, match="INVALID"):
                load_openapi(tmp.name)
        finally:
            os.unlink(tmp.name)

    def test_yaml_spec_loads_correctly(self):
        yaml_content = (
            "openapi: '3.0.1'\n"
            "info:\n"
            "  title: YAML API\n"
            "  version: '1.0'\n"
            "paths:\n"
            "  /users:\n"
            "    get:\n"
            "      summary: List users\n"
        )
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        tmp.write(yaml_content)
        tmp.close()
        try:
            doc = load_openapi(tmp.name)
            assert doc["info"]["title"] == "YAML API"
            assert "/users" in doc["paths"]
        finally:
            os.unlink(tmp.name)

    def test_missing_file_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="FILE NOT FOUND"):
            load_openapi("/nonexistent/path/openapi.json")

    def test_run_diff_with_real_project_fixtures(self):
        baseline = os.path.join(ROOT_DIR, "input", "admin-openapi.json")
        target   = os.path.join(ROOT_DIR, "input", "analytics.openapi.json")
        findings = run_diff(baseline, target)
        assert len(findings) > 0
        assert all(f["severity"] == "CRITICAL" for f in findings)


# ---------------------------------------------------------------------------
# Schema helpers — unit tests for _diff_schema_properties
# ---------------------------------------------------------------------------

class TestSchemaHelpers:

    def test_field_removed(self):
        v1 = {"properties": {"id": {"type": "string"}, "name": {"type": "string"}}}
        v2 = {"properties": {"id": {"type": "string"}}}
        changes = _diff_schema_properties(v1, v2)
        assert {"field": "name", "change": "field_removed"} in changes

    def test_field_added(self):
        v1 = {"properties": {"id": {"type": "string"}}}
        v2 = {"properties": {"id": {"type": "string"}, "email": {"type": "string"}}}
        changes = _diff_schema_properties(v1, v2)
        assert {"field": "email", "change": "field_added"} in changes

    def test_type_changed(self):
        v1 = {"properties": {"id": {"type": "string"}}}
        v2 = {"properties": {"id": {"type": "integer"}}}
        changes = _diff_schema_properties(v1, v2)
        assert changes == [{"field": "id", "change": "type_changed",
                             "from_type": "string", "to_type": "integer"}]

    def test_became_required(self):
        v1 = {"properties": {"id": {"type": "string"}, "email": {"type": "string"}},
              "required": ["id"]}
        v2 = {"properties": {"id": {"type": "string"}, "email": {"type": "string"}},
              "required": ["id", "email"]}
        changes = _diff_schema_properties(v1, v2)
        assert {"field": "email", "change": "became_required"} in changes

    def test_became_optional(self):
        v1 = {"properties": {"id": {"type": "string"}}, "required": ["id"]}
        v2 = {"properties": {"id": {"type": "string"}}}
        changes = _diff_schema_properties(v1, v2)
        assert {"field": "id", "change": "became_optional"} in changes

    def test_identical_schema_returns_empty(self):
        schema = {"properties": {"id": {"type": "string"}}, "required": ["id"]}
        assert _diff_schema_properties(schema, schema) == []

    def test_no_properties_returns_empty(self):
        assert _diff_schema_properties({"type": "string"}, {"type": "integer"}) == []

    def test_empty_schemas_return_empty(self):
        assert _diff_schema_properties({}, {}) == []

    def test_non_dict_input_returns_empty(self):
        assert _diff_schema_properties(None, {}) == []
        assert _diff_schema_properties({}, None) == []

    def test_required_only_reported_for_shared_fields(self):
        # field added to V2 AND listed as required — should produce field_added, not became_required
        v1 = {"properties": {"id": {"type": "string"}}}
        v2 = {"properties": {"id": {"type": "string"}, "email": {"type": "string"}},
              "required": ["email"]}
        changes = _diff_schema_properties(v1, v2)
        change_types = [c["change"] for c in changes]
        assert "became_required" not in change_types
        assert "field_added" in change_types

    def test_extract_json_schema_gets_application_json(self):
        holder = {"content": {"application/json": {"schema": {"type": "object"}}}}
        assert _extract_json_schema(holder) == {"type": "object"}

    def test_extract_json_schema_returns_empty_for_missing(self):
        assert _extract_json_schema({}) == {}
        assert _extract_json_schema({"content": {}}) == {}

    def test_get_primary_response_schema_prefers_200(self):
        responses = {
            "404": {"content": {"application/json": {"schema": {"type": "string"}}}},
            "200": {"content": {"application/json": {"schema": {"type": "object"}}}},
        }
        schema = _get_primary_response_schema(responses)
        assert schema == {"type": "object"}


# ---------------------------------------------------------------------------
# Granular schema diff — field-level assertions on SCHEMA_DRIFT findings
# ---------------------------------------------------------------------------

class TestGranularSchemaDiff:

    def _resp_op(self, props, required=None):
        schema = {"type": "object", "properties": props}
        if required:
            schema["required"] = required
        return {"responses": {"200": {"content": {"application/json": {"schema": schema}}}}}

    def _req_op(self, props, required=None):
        schema = {"type": "object", "properties": props}
        if required:
            schema["required"] = required
        return {"requestBody": {"content": {"application/json": {"schema": schema}}}}

    def test_field_removed_in_response_schema_changes(self):
        v1_op = self._resp_op({"id": {"type": "string"}, "name": {"type": "string"}})
        v2_op = self._resp_op({"id": {"type": "string"}})
        v1 = extract_contracts(_make_spec({"/users": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        sc = findings[0]["response_schema_changes"]
        assert any(c["field"] == "name" and c["change"] == "field_removed" for c in sc)

    def test_field_added_in_response_schema_changes(self):
        v1_op = self._resp_op({"id": {"type": "string"}})
        v2_op = self._resp_op({"id": {"type": "string"}, "email": {"type": "string"}})
        v1 = extract_contracts(_make_spec({"/users": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        sc = findings[0]["response_schema_changes"]
        assert any(c["field"] == "email" and c["change"] == "field_added" for c in sc)

    def test_type_changed_in_response_schema_changes(self):
        v1_op = self._resp_op({"id": {"type": "string"}})
        v2_op = self._resp_op({"id": {"type": "integer"}})
        v1 = extract_contracts(_make_spec({"/users": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        sc = findings[0]["response_schema_changes"]
        assert len(sc) == 1
        assert sc[0]["field"] == "id"
        assert sc[0]["change"] == "type_changed"
        assert sc[0]["from_type"] == "string"
        assert sc[0]["to_type"] == "integer"

    def test_became_required_in_response_schema_changes(self):
        v1_op = self._resp_op({"id": {"type": "string"}, "email": {"type": "string"}})
        v2_op = self._resp_op({"id": {"type": "string"}, "email": {"type": "string"}},
                               required=["email"])
        v1 = extract_contracts(_make_spec({"/users": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        sc = findings[0]["response_schema_changes"]
        assert any(c["field"] == "email" and c["change"] == "became_required" for c in sc)

    def test_became_optional_in_response_schema_changes(self):
        v1_op = self._resp_op({"id": {"type": "string"}}, required=["id"])
        v2_op = self._resp_op({"id": {"type": "string"}})
        v1 = extract_contracts(_make_spec({"/users": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        sc = findings[0]["response_schema_changes"]
        assert any(c["field"] == "id" and c["change"] == "became_optional" for c in sc)

    def test_request_body_field_removed_in_schema_changes(self):
        v1_op = self._req_op({"name": {"type": "string"}, "email": {"type": "string"}})
        v2_op = self._req_op({"name": {"type": "string"}})
        v1 = extract_contracts(_make_spec({"/users": {"post": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"post": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        rb = findings[0]["request_body_schema_changes"]
        assert any(c["field"] == "email" and c["change"] == "field_removed" for c in rb)

    def test_no_properties_gives_empty_schema_changes(self):
        v1_op = {"responses": {"200": {"content": {"application/json":
                     {"schema": {"type": "string"}}}}}}
        v2_op = {"responses": {"200": {"content": {"application/json":
                     {"schema": {"type": "integer"}}}}}}
        v1 = extract_contracts(_make_spec({"/ping": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/ping": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        assert findings[0]["change_type"] == "SCHEMA_DRIFT"
        assert findings[0]["response_schema_changes"] == []

    def test_schema_drift_finding_always_has_both_change_keys(self):
        v1_op = self._resp_op({"id": {"type": "string"}})
        v2_op = self._resp_op({"id": {"type": "integer"}})
        v1 = extract_contracts(_make_spec({"/users": {"get": v1_op}}))
        v2 = extract_contracts(_make_spec({"/users": {"get": v2_op}}))
        findings = _find_modified_endpoints(v1, v2)
        assert "response_schema_changes" in findings[0]
        assert "request_body_schema_changes" in findings[0]
