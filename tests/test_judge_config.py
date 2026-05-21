import os
import sys
import json
import tempfile
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from judge_config import validate_docs_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_temp_json(data: dict) -> str:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(data, tmp)
    tmp.close()
    return tmp.name


def _write_temp_text(text: str) -> str:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    tmp.write(text)
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# Valid configurations
# ---------------------------------------------------------------------------

class TestValidConfig:

    def test_minimal_valid_config_returns_true(self):
        data = {
            "name": "Test Docs",
            "navigation": {
                "tabs": [
                    {
                        "tab": "Getting Started",
                        "groups": [
                            {"group": "Intro", "pages": ["index"]}
                        ],
                    }
                ]
            },
        }
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is True
        finally:
            os.unlink(path)

    def test_full_config_with_schema_ref_and_global_nav(self):
        data = {
            "$schema": "https://mintlify.com/docs.json",
            "name": "My Project",
            "navigation": {
                "tabs": [
                    {
                        "tab": "Guides",
                        "groups": [
                            {"group": "Quickstart", "pages": ["intro", "setup"]}
                        ],
                    }
                ],
                "global": {
                    "anchors": [
                        {"anchor": "GitHub", "href": "https://github.com/example"}
                    ]
                },
            },
        }
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is True
        finally:
            os.unlink(path)

    def test_unknown_extra_fields_are_accepted(self):
        data = {
            "name": "Test",
            "theme": "mint",
            "colors": {"primary": "#16A34A"},
            "favicon": "/favicon.svg",
            "navigation": {
                "tabs": [
                    {"tab": "Home", "groups": [{"group": "G", "pages": ["p"]}]}
                ]
            },
        }
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is True
        finally:
            os.unlink(path)

    def test_actual_project_docs_json_is_valid(self):
        real_path = os.path.join(ROOT_DIR, "docs.json")
        assert validate_docs_config(real_path) is True


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

class TestMissingRequiredFields:

    def test_missing_name_field_returns_false(self):
        data = {
            "navigation": {
                "tabs": [
                    {"tab": "T", "groups": [{"group": "G", "pages": ["p"]}]}
                ]
            }
        }
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is False
        finally:
            os.unlink(path)

    def test_missing_navigation_field_returns_false(self):
        data = {"name": "Test"}
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is False
        finally:
            os.unlink(path)

    def test_empty_name_string_returns_false(self):
        data = {
            "name": "",
            "navigation": {
                "tabs": [
                    {"tab": "T", "groups": [{"group": "G", "pages": ["p"]}]}
                ]
            },
        }
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is False
        finally:
            os.unlink(path)

    def test_empty_tabs_list_returns_false(self):
        data = {"name": "Test", "navigation": {"tabs": []}}
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is False
        finally:
            os.unlink(path)

    def test_empty_groups_in_tab_returns_false(self):
        data = {
            "name": "Test",
            "navigation": {
                "tabs": [{"tab": "T", "groups": []}]
            },
        }
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is False
        finally:
            os.unlink(path)

    def test_empty_pages_in_group_returns_false(self):
        data = {
            "name": "Test",
            "navigation": {
                "tabs": [
                    {"tab": "T", "groups": [{"group": "G", "pages": []}]}
                ]
            },
        }
        path = _write_temp_json(data)
        try:
            assert validate_docs_config(path) is False
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Invalid file inputs
# ---------------------------------------------------------------------------

class TestInvalidInputs:

    def test_file_not_found_returns_false(self):
        assert validate_docs_config("/nonexistent/path/to/docs.json") is False

    def test_malformed_json_syntax_returns_false(self):
        path = _write_temp_text('{"name": "Test", "navigation": }')
        try:
            assert validate_docs_config(path) is False
        finally:
            os.unlink(path)

    def test_empty_file_returns_false(self):
        path = _write_temp_text("")
        try:
            assert validate_docs_config(path) is False
        finally:
            os.unlink(path)
