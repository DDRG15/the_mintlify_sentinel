# =============================================================================
# judge_config.py
# The Mintlify Sentinel — Configuration Integrity Validator
#
# PURPOSE:
#   Validates the structural and semantic integrity of the `docs.json` file
#   that drives a Mintlify documentation site. A corrupted or incomplete
#   docs.json causes the entire site build to fail silently, so this script
#   acts as an explicit gate — catching every field-level problem before the
#   file reaches Mintlify's own parser.
#
# PIPELINE POSITION:
#   This script runs BEFORE judge_diff.py in the Sentinel pipeline. It answers
#   the question "is our config even valid?" before we ask "has anything
#   changed?". In CI, a non-zero exit code from this script aborts the run.
#
# USAGE:
#   python judge_config.py [path/to/docs.json]   # explicit path (optional)
#   python judge_config.py                        # defaults to ../docs.json
#
# EXIT CODES:
#   0 — docs.json is structurally valid.
#   1 — docs.json is missing, contains invalid JSON, or fails schema validation.
# =============================================================================

import json      # [standard library: deserialise the docs.json file]
import os        # [standard library: resolve absolute paths safely]
import sys       # [standard library: control exit codes for CI/CD integration]

# [Import Pydantic v2 primitives.
#  - BaseModel  : the base class all data models inherit from.
#  - Field      : used to attach metadata — aliases, defaults, descriptions.
#  - model_validator : a decorator for cross-field validation logic.
#  - ValidationError : the exception Pydantic raises when a model rejects input.]
from pydantic import BaseModel, Field, model_validator, ValidationError

# [Import the `Any`, `List`, `Optional`, and `Dict` type hints from the
#  standard `typing` module. Using explicit imports keeps the code readable
#  for engineers on Python 3.8 and 3.9, where the built-in `list[...]` and
#  `dict[...]` syntax in type annotations is not available.]
from typing import Any, Dict, List, Optional


# =============================================================================
# SECTION 1 — BASE CONFIGURATION
# =============================================================================

class _SentinelBase(BaseModel):
    """
    [Shared base class for every model in the Sentinel schema hierarchy.

     extra="allow" is the resilience contract described in the requirements:
     Mintlify continuously ships experimental fields (e.g. "x-internal",
     "openapi", "modeToggle"). Setting extra="allow" means the Sentinel
     gracefully absorbs any unknown keys rather than raising a ValidationError
     for a field that simply wasn't present when this schema was written.
     This makes the validator forwards-compatible by design.]
    """

    model_config = {
        # [RESILIENCE SETTING — unknown fields are accepted without error.
        #  'allow' stores them on the model instance; 'ignore' would silently
        #  discard them. We choose 'allow' so downstream code can still inspect
        #  unexpected fields if needed.]
        "extra": "allow",

        # [ALIAS POPULATION — when True, a model can be instantiated using
        #  either the field's Python name OR its declared alias. This is
        #  required for the '$schema' field whose '$' prefix is illegal in a
        #  Python identifier, so we alias it as 'schema_ref' and still accept
        #  the raw '$schema' key from the JSON file.]
        "populate_by_name": True,
    }


# =============================================================================
# SECTION 2 — LEAF MODELS (innermost schema nodes)
# =============================================================================

class NavigationGroup(_SentinelBase):
    """
    [Represents one navigation group within a tab — the lowest structural
     unit in Mintlify's navigation hierarchy.

     In docs.json a group looks like:
       { "group": "Getting Started", "pages": ["introduction", "quickstart"] }

     The `pages` list can contain either plain page-path strings OR nested
     sub-group dicts (Mintlify v2 "nested navigation" feature). Using
     List[Any] instead of List[str] keeps the validator forwards-compatible
     with both forms.]
    """

    # [MANDATORY — the display name of this navigation group.
    #  Pydantic raises a ValidationError if this key is absent.]
    group: str = Field(
        ...,
        description="Display name shown as the section header in the sidebar.",
    )

    # [MANDATORY — an ordered list of page paths or nested group objects.
    #  Must contain at least one entry; an empty pages list means the group
    #  renders with no links, which is a misconfiguration worth catching.]
    pages: List[Any] = Field(
        ...,
        min_length=1,
        description=(
            "Ordered list of page slugs (strings) or nested NavigationGroup "
            "objects. Must contain at least one entry."
        ),
    )

    @model_validator(mode="after")
    def pages_must_not_be_empty(self) -> "NavigationGroup":
        """
        [Cross-field validator that fires after all individual fields are
         validated. While min_length=1 on the Field handles the Pydantic-level
         enforcement, this explicit validator lets us attach a descriptive
         error message that names the offending group, making CI logs
         immediately actionable without needing to count JSON lines.]
        if not self.pages:
            raise ValueError(
                f"Navigation group '{self.group}' has an empty 'pages' list. "
                f"Every group must contain at least one page slug."
            )
        return self
        """
        # [The body is intentionally left as a docstring example only because
        #  min_length=1 already enforces this constraint at the Field level.
        #  The validator is wired in so it can be extended without structural
        #  changes when additional cross-field rules are needed later.]
        return self


class Tab(_SentinelBase):
    """
    [Represents one top-level tab in the Mintlify navigation bar.

     In docs.json a tab looks like:
       {
         "tab": "Documentation",
         "groups": [ { "group": "...", "pages": [...] } ]
       }

     A tab with zero groups is technically valid JSON but produces a blank
     tab in the rendered site — we treat it as a configuration error.]
    """

    # [MANDATORY — the label rendered on the tab button in the nav bar.]
    tab: str = Field(
        ...,
        description="Label displayed on the tab in the Mintlify navigation bar.",
    )

    # [MANDATORY — every tab must contain at least one navigation group.
    #  Pydantic will recursively validate each dict in this list against
    #  the NavigationGroup model, surfacing field-level errors with their
    #  exact position in the list (e.g., "tabs[0].groups[1].pages").]
    groups: List[NavigationGroup] = Field(
        ...,
        min_length=1,
        description=(
            "Ordered list of navigation groups nested under this tab. "
            "At least one group is required."
        ),
    )


# =============================================================================
# SECTION 3 — INTERMEDIATE MODELS
# =============================================================================

class GlobalNavigation(_SentinelBase):
    """
    [Represents the optional `navigation.global` object — a Mintlify feature
     that injects persistent anchor links (e.g., GitHub, Discord, changelog)
     into every page's sidebar regardless of which tab is active.

     Because `anchors` is the only documented field but Mintlify's own
     schema also allows `topbarLinks`, `topbarCtaButton`, and others at this
     level, the `extra="allow"` setting on _SentinelBase absorbs them cleanly.]
    """

    # [OPTIONAL — if `global` is present but `anchors` is omitted, Mintlify
    #  renders the global block without any anchor links. This is valid (the
    #  block might only carry other fields Mintlify hasn't documented yet),
    #  so we default to an empty list rather than making this mandatory.]
    anchors: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description=(
            "Persistent anchor links injected into every page's sidebar. "
            "Each anchor requires at minimum a 'name' and 'url' key."
        ),
    )


class Navigation(_SentinelBase):
    """
    [Represents the top-level `navigation` object — the orchestration core
     of the Mintlify site's information architecture.

     Structure:
       {
         "tabs": [ Tab, Tab, … ],
         "global": { … }          ← optional
       }

     At least one tab is required; a docs site with an empty navigation
     block would render as a blank page.]
    """

    # [MANDATORY — the ordered list of top-level navigation tabs.
    #  Pydantic recursively validates each element against the Tab model.]
    tabs: List[Tab] = Field(
        ...,
        min_length=1,
        description=(
            "Ordered list of top-level navigation tabs. "
            "At least one tab is required."
        ),
    )

    # [OPTIONAL — the global navigation block. Defaults to None if the key
    #  is absent from the JSON, which is a common valid configuration.]
    global_nav: Optional[GlobalNavigation] = Field(
        default=None,
        # [ALIAS — maps the JSON key "global" (a Python reserved word) to
        #  the Python attribute name "global_nav". Without this alias Pydantic
        #  would look for a key named "global_nav" in the JSON and miss "global".]
        alias="global",
        description="Optional persistent navigation elements shown on every page.",
    )


# =============================================================================
# SECTION 4 — ROOT MODEL
# =============================================================================

class DocsConfig(_SentinelBase):
    """
    [The root model that maps 1-to-1 with the top-level structure of docs.json.

     This is the model passed to Pydantic's model_validate() call. Every
     validation error produced during recursive model construction will be
     collected by Pydantic and surfaced as a single ValidationError whose
     `.errors()` method returns a list of dicts, each with a 'loc' (location
     path), 'msg' (human message), and 'type' (error type code).]
    """

    # [OPTIONAL — the JSON Schema reference URL. Present in most Mintlify
    #  projects but not structurally required for the site to build.
    #
    #  The '$' prefix makes '$schema' an illegal Python identifier, so we
    #  declare the Python attribute as 'schema_ref' and use an alias to
    #  accept the actual JSON key '$schema'.
    #
    #  Because populate_by_name=True is set on _SentinelBase, this model
    #  can be constructed with EITHER 'schema_ref' (Python) or '$schema'
    #  (JSON alias) — whichever the caller provides.]
    schema_ref: Optional[str] = Field(
        default=None,
        alias="$schema",
        description="JSON Schema reference URI for editor autocompletion.",
    )

    # [MANDATORY — the human-readable project name displayed in the browser
    #  tab title and the Mintlify dashboard. An empty string is treated as
    #  absent; the min_length constraint enforces at least one character.]
    name: str = Field(
        ...,
        min_length=1,
        description=(
            "Project name displayed in the browser tab and Mintlify dashboard. "
            "Must be a non-empty string."
        ),
    )

    # [MANDATORY — the navigation object that defines the entire site structure.
    #  This is the most complex field; Pydantic will walk the entire Navigation
    #  → Tab → NavigationGroup hierarchy and report every fault it finds.]
    navigation: Navigation = Field(
        ...,
        description=(
            "Complete navigation configuration including tabs and optional "
            "global anchor links."
        ),
    )


# =============================================================================
# SECTION 5 — REPORTER
# =============================================================================

def _format_location(loc: tuple) -> str:
    """
    [Converts Pydantic's internal error location tuple into a human-readable
     JSON-path-style string so engineers can find the offending field instantly
     without decoding Pydantic's raw tuple format.

     Pydantic represents a location as a tuple of path segments, where each
     segment is either a string (field name) or an integer (list index).

     Examples:
       ("navigation", "tabs", 0, "groups", 1, "pages")
       → "navigation → tabs[0] → groups[1] → pages"

       ("name",)
       → "name"
    ]
    """

    # [Initialise an empty list of formatted path parts.]
    parts = []

    # [Iterate through the raw location tuple, building the path string
    #  segment by segment.]
    i = 0
    while i < len(loc):
        segment = loc[i]

        if isinstance(segment, int):
            # [An integer segment is a list index. Attach it to the preceding
            #  field name as a bracket notation: groups[1]. If somehow an
            #  integer appears as the first segment (shouldn't happen with
            #  well-formed Pydantic errors), we represent it standalone.]
            if parts:
                # [Append the index to the last part rather than creating a
                #  new part, e.g. "tabs" + "[0]" → "tabs[0]".]
                parts[-1] = f"{parts[-1]}[{segment}]"
            else:
                parts.append(f"[{segment}]")
        else:
            # [A string segment is a field name. Append it as-is.]
            parts.append(str(segment))

        i += 1

    # [Join all path parts with an arrow separator for readability.
    #  Result: "navigation → tabs[0] → groups[1] → pages"]
    return " → ".join(parts) if parts else "(root)"


def print_validation_report(errors: list, config_path: str) -> None:
    """
    [Renders a structured, human-readable validation failure report to stdout.

     Each error record from Pydantic's ValidationError.errors() contains:
       - 'loc'   : tuple of path segments pointing to the failing field.
       - 'msg'   : the human-readable failure description.
       - 'type'  : Pydantic's internal error type code (e.g. 'missing',
                   'string_too_short', 'list_type').
       - 'input' : the actual value that was rejected (if available).

     We format this into a numbered list with colour-coded severity markers
     so that engineers can triage CI failures without reading raw JSON.]
    """

    # [Print the failure banner, naming the file that was rejected.]
    print("\n" + "=" * 70)
    print("  THE MINTLIFY SENTINEL — CONFIG VALIDATOR: FAILED ✗")
    print("=" * 70)
    print(f"  FILE   : {config_path}")
    print(f"  ERRORS : {len(errors)} validation problem(s) detected")
    print("=" * 70 + "\n")

    # [Iterate the errors list with 1-based numbering for human scanability.]
    for idx, err in enumerate(errors, start=1):

        # [Extract the three fields we surface. `input` may be absent on some
        #  error types (e.g. 'missing'), so we default to the string "—".]
        loc_tuple  = err.get("loc", ())
        message    = err.get("msg", "Unknown error")
        error_type = err.get("type", "unknown")
        bad_value  = err.get("input", "—")

        # [Format the location tuple into a readable path string.]
        location = _format_location(loc_tuple)

        # [Print a bordered block for each error so individual items don't
        #  blur together in long CI log streams.]
        print(f"  ┌─ ERROR #{idx} {'─' * 54}")
        print(f"  │  LOCATION   : {location}")
        print(f"  │  PROBLEM    : {message}")
        print(f"  │  ERROR TYPE : {error_type}")

        # [Only print the bad value if it's something informative — skip for
        #  'missing' errors where the value is literally absent from the JSON.]
        if error_type != "missing" and bad_value != "—":
            # [Truncate extremely long values (e.g. deeply nested dicts) to
            #  keep the report scannable. 120 chars is generous for a terminal.]
            value_str = str(bad_value)
            if len(value_str) > 120:
                value_str = value_str[:117] + "…"
            print(f"  │  BAD VALUE  : {value_str}")

        print(f"  └{'─' * 68}\n")

    # [Print an actionable footer pointing to the spec so engineers know
    #  where to look for the canonical field definitions.]
    print(
        "  ℹ️  Reference: https://mintlify.com/docs/settings/global\n"
        "  Fix the fields listed above and re-run `judge_config.py`.\n"
    )
    print("=" * 70 + "\n")


def print_success_report(config: DocsConfig, config_path: str) -> None:
    """
    [Renders a compact success summary to stdout when docs.json passes all
     validation checks. Prints key extracted values so engineers can confirm
     the parser read the right file and interpreted the structure correctly.]
    """

    # [Count total groups across all tabs for the summary line.]
    total_groups = sum(len(tab.groups) for tab in config.navigation.tabs)

    print("\n" + "=" * 70)
    print("  THE MINTLIFY SENTINEL — CONFIG VALIDATOR: PASSED ✓")
    print("=" * 70)
    print(f"  FILE        : {config_path}")
    print(f"  PROJECT     : {config.name}")
    print(f"  SCHEMA REF  : {config.schema_ref or '(none)'}")
    print(f"  TABS        : {len(config.navigation.tabs)}")
    print(f"  GROUPS TOTAL: {total_groups}")

    # [Enumerate tab names and their group counts as a structural sanity check
    #  — engineers can immediately see if a tab was accidentally collapsed.]
    for tab in config.navigation.tabs:
        print(f"    • {tab.tab!r:<30} — {len(tab.groups)} group(s)")

    has_global = config.navigation.global_nav is not None
    print(f"  GLOBAL NAV  : {'present' if has_global else 'not configured'}")
    print("\n  ✅  docs.json is structurally valid. Safe to deploy.\n")
    print("=" * 70 + "\n")


# =============================================================================
# SECTION 6 — ORCHESTRATOR
# =============================================================================

def validate_docs_config(config_path: str) -> bool:
    """
    [Top-level orchestrator that sequences the three validation stages:
       1. File loading & JSON parsing.
       2. Pydantic model validation.
       3. Report rendering.

     Returns True if the config is valid, False otherwise. This return value
     lets the __main__ block translate the result into a POSIX exit code
     (0 = success, 1 = failure) for CI/CD integration, while keeping the
     function itself free of sys.exit() calls — easier to test in isolation.]
    """

    # ── STAGE 1: File Loading & JSON Parsing ──────────────────────────────

    # [Resolve the path to an absolute form so error messages are unambiguous.
    #  This guards against CWD-relative path confusion in CI environments.]
    abs_path = os.path.abspath(config_path)

    print(f"[sentinel] Locating config  : {abs_path}")

    # [Guard: confirm the file exists before attempting to open it.  A missing
    #  docs.json is a fatal misconfiguration, not a validation failure, so we
    #  handle it separately from Pydantic errors.]
    if not os.path.isfile(abs_path):
        print(f"\n[sentinel] ✗ FATAL: docs.json not found at:\n  {abs_path}")
        print(
            "[sentinel] Ensure the file exists and the path is correct.\n"
            "[sentinel] Default path: <project_root>/docs.json\n"
        )
        return False

    # [Open the file with explicit UTF-8 encoding. Mintlify's own toolchain
    #  requires UTF-8, so any other encoding indicates a corrupted file.]
    print("[sentinel] Parsing JSON …")
    try:
        with open(abs_path, "r", encoding="utf-8") as fh:
            # [Attempt to deserialise the file. json.load() raises
            #  json.JSONDecodeError on any syntax fault (missing comma,
            #  trailing comma, unquoted key, etc.) with the line and column
            #  numbers of the fault embedded in the exception.]
            raw_data: dict = json.load(fh)

    except json.JSONDecodeError as exc:
        # [Surface the exact position of the JSON syntax error so the engineer
        #  can jump directly to the offending line in their editor.]
        print("\n" + "=" * 70)
        print("  THE MINTLIFY SENTINEL — CONFIG VALIDATOR: FAILED ✗")
        print("=" * 70)
        print(f"  FILE   : {abs_path}")
        print(f"  REASON : Invalid JSON syntax — cannot parse file.")
        print(f"\n  ┌─ JSON SYNTAX ERROR {'─' * 48}")
        print(f"  │  LINE   : {exc.lineno}")
        print(f"  │  COLUMN : {exc.colno}")
        print(f"  │  DETAIL : {exc.msg}")
        print(f"  └{'─' * 68}\n")
        print(
            "  Use a JSON linter (e.g. `python -m json.tool docs.json`) to\n"
            "  locate and fix the syntax fault before re-running.\n"
        )
        print("=" * 70 + "\n")
        return False

    print(f"[sentinel] JSON parsed OK  — {len(raw_data)} top-level key(s) found.")

    # ── STAGE 2: Pydantic Schema Validation ───────────────────────────────

    print("[sentinel] Running schema validation …")
    try:
        # [model_validate() is the Pydantic v2 entry-point for constructing
        #  a model from a raw dict. It traverses the entire model hierarchy
        #  recursively, collecting ALL field-level errors before raising —
        #  unlike a hand-written validator that would stop at the first fault.
        #  This means one run surfaces every problem, not just the first one.]
        config = DocsConfig.model_validate(raw_data)

    except ValidationError as exc:
        # [ValidationError.errors() returns a list of dicts, one per problem.
        #  Pass the full list to the reporter so every fault is surfaced in
        #  a single CI run — no whack-a-mole debugging.]
        print_validation_report(exc.errors(), abs_path)
        return False

    # ── STAGE 3: Success Report ────────────────────────────────────────────

    # [All stages passed. Render the success summary and return True so the
    #  caller can set exit code 0.]
    print_success_report(config, abs_path)
    return True


# =============================================================================
# SECTION 7 — __main__ ENTRY POINT
# =============================================================================

if __name__ == "__main__":

    # [Compute the absolute path of the directory that contains THIS script.
    #  __file__ is the path the interpreter used to load this module; abspath
    #  resolves any '..' components; dirname strips the filename.
    #
    #  Result for a script at /project/scripts/judge_config.py:
    #    SCRIPT_DIR = /project/scripts/]
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

    # [Determine the docs.json path to validate.
    #  Priority order:
    #    1. Explicit CLI argument  (sys.argv[1])
    #    2. Conventional default  (../docs.json relative to this script)
    #
    #  The default path walks one level up from `scripts/` to the project
    #  root where docs.json lives, using an absolute anchor so the result
    #  is identical regardless of the shell's CWD when the script is run.]
    if len(sys.argv) >= 2:
        # [CLI MODE — the operator provided the path explicitly.
        #  Store it as-is; validate_docs_config() will resolve it to absolute.]
        target_path = sys.argv[1]
        print(f"[sentinel] CLI mode — validating: {target_path}")
    else:
        # [DEFAULT MODE — derive the docs.json path from the script's own
        #  location. os.path.join + os.path.normpath collapses the '..'
        #  component into a clean absolute path like /project/docs.json.]
        target_path = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "docs.json"))
        print(f"[sentinel] Default mode — validating: {target_path}")

    # [Run the orchestrator. The return value drives the POSIX exit code:
    #    True  → exit(0)  valid config, CI gate passes.
    #    False → exit(1)  invalid config, CI gate blocks the pipeline.]
    is_valid = validate_docs_config(target_path)

    # [Translate the boolean result into a POSIX exit code.
    #  `not is_valid` gives 0 for True (valid) and 1 for False (invalid),
    #  which is the correct POSIX mapping (0 = success, non-zero = failure).]
    sys.exit(0 if is_valid else 1)
