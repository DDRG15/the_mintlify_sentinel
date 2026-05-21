# =============================================================================
# judge_diff.py  ·  VERSION 3.0  —  "Schema Drift Detection"
# The Mintlify Sentinel — Diff Engine
#
# CHANGELOG (v2 → v3):
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  WHAT CHANGED                          WHY                             │
# ├─────────────────────────────────────────────────────────────────────────┤
# │  load_openapi() now parses YAML        Real-world specs are frequently │
# │  in addition to JSON (pyyaml).         written in YAML. JSON is tried  │
# │  Auto-detects format by content.       first; YAML is the fallback.    │
# ├─────────────────────────────────────────────────────────────────────────┤
# │  Phase 2: Rule C added                 Catches response body and       │
# │  → SCHEMA_DRIFT (MEDIUM)               request body schema changes     │
# │  Fires between Rule B (MEDIUM) and     that survive the endpoint-level │
# │  Rule A (LOW). Checks `responses`      diff. An endpoint can exist and │
# │  and `requestBody` serialised diffs.   have identical parameters but a │
# │                                        silently changed response shape. │
# └─────────────────────────────────────────────────────────────────────────┘
#
# CHANGELOG (v1 → v2):
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  extract_contracts() → returns dict    Phase 2 needs the operation     │
# │  instead of set                        body, not just the signature.   │
# ├─────────────────────────────────────────────────────────────────────────┤
# │  Phase 1 (set difference) preserved    CRITICAL removals still the     │
# │  but operates on dict.keys()           most important signal.          │
# ├─────────────────────────────────────────────────────────────────────────┤
# │  Phase 2 added (intersection diff)     Catches subtler contract drift  │
# │  → Rule A: DOCS_UPDATED      (LOW)     before it reaches production.   │
# │  → Rule B: PARAMETERS_MODIFIED (MEDIUM)                                │
# ├─────────────────────────────────────────────────────────────────────────┤
# │  Exit code: always 0                   Sentinel is an audit tool.      │
# │  (was: 1 on any finding)               Developers retain free will.    │
# └─────────────────────────────────────────────────────────────────────────┘
#
# SEVERITY LADDER:
#   CRITICAL  Endpoint deleted. All existing clients break on next deploy.
#   MEDIUM    Parameters changed, or request/response body schema changed.
#   LOW       Only docs/description text changed. Zero runtime impact.
#
# PIPELINE POSITION:
#   Sits between judge_config.py (gatekeeper) and architect_render.py
#   (MDX generator). main.py calls run_diff() and passes its return value
#   directly into render_changelog().
#
# USAGE:
#   python judge_diff.py <baseline.json> <target.json>   # explicit files
#   python judge_diff.py                                  # test harness mode
#
# EXIT CODE:
#   Always 0. The Sentinel reports; it does not block.
# =============================================================================

import json    # [standard library: deserialise JSON OpenAPI files; pretty-print output]
import sys     # [standard library: read CLI arguments; emit the final exit code]
import os      # [standard library: resolve CWD-independent absolute file paths]

try:
    import yaml as _yaml  # [pyyaml: YAML-format OpenAPI spec support (pip install pyyaml)]
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# =============================================================================
# SECTION 1 — FILE LOADER
# =============================================================================

def load_openapi(filepath: str) -> dict:
    """
    [Resolves `filepath` to an absolute path, confirms the file exists, then
     deserialises its JSON content into a Python dict. Raises a descriptive
     RuntimeError for the two most common failure modes — file-not-found and
     invalid JSON syntax — so callers never receive a raw interpreter traceback
     that obscures which file caused the problem.]
    """

    # [Resolve to absolute path. This makes every downstream error message
    #  unambiguous regardless of the shell's current working directory at
    #  invocation time — a common source of "works on my machine" CI failures.]
    abs_path = os.path.abspath(filepath)

    # [Guard: stat the path before opening. A missing file raises RuntimeError
    #  with the full path, not Python's default FileNotFoundError boilerplate.]
    if not os.path.isfile(abs_path):
        raise RuntimeError(f"[FILE NOT FOUND] No file at path: {abs_path}")

    # [Read the raw content once. Format is auto-detected from the content
    #  itself, not the file extension — Streamlit writes uploaded files to
    #  temp paths with .json suffixes regardless of the original format.]
    with open(abs_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    # [Try JSON first. It is the most common format for machine-generated
    #  OpenAPI specs and requires no third-party dependency.]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # [JSON failed — try YAML. Many hand-authored specs use YAML.
    #  yaml.safe_load() never executes arbitrary Python, making it safe for
    #  untrusted input. If pyyaml is not installed, surface a clear install
    #  instruction rather than a cryptic ImportError traceback.]
    if not _YAML_AVAILABLE:
        raise RuntimeError(
            f"[INVALID JSON] Could not parse: {abs_path}\n"
            f"  The file does not appear to be valid JSON.\n"
            f"  To support YAML format: pip install pyyaml"
        )

    try:
        data = _yaml.safe_load(content)
    except Exception as exc:
        raise RuntimeError(
            f"[INVALID FORMAT] Could not parse as JSON or YAML: {abs_path}\n"
            f"  Error: {exc}"
        )

    if not isinstance(data, dict):
        raise RuntimeError(
            f"[INVALID FORMAT] Parsed YAML did not produce a dict: {abs_path}"
        )

    return data


# =============================================================================
# SECTION 2 — CONTRACT EXTRACTOR  (upgraded: returns dict, not set)
# =============================================================================

# [Canonical HTTP methods recognised by the OpenAPI 3.x specification at
#  the path-item level. frozenset: O(1) membership checks, immutable signal.]
HTTP_METHODS: frozenset = frozenset({
    "get", "post", "put", "delete", "patch", "options", "head", "trace"
})


def extract_contracts(openapi_doc: dict) -> dict:
    """
    [Walks the `paths` object of an OpenAPI document and returns a dict that
     maps each contract signature to its full Operation Object.

     Return type:  dict[str, dict]
       Key   →  normalised signature string, e.g. "GET /v1/users"
       Value →  the raw OpenAPI Operation Object dict at paths[path][method],
                containing summary, description, parameters, responses, etc.

     WHY A DICT INSTEAD OF A SET (v1 → v2 rationale):
       v1 only needed to answer "does this signature exist?" — a set sufficed.
       v2 must also answer "what does this endpoint look like?" so Phase 2 can
       compare the operation bodies of shared endpoints. Storing the operation
       object as the dict value lets callers do both without a second traversal:

         set arithmetic  →  dict.keys() - dict.keys()   (Phase 1)
         body lookup     →  dict[signature]               (Phase 2)

       Python's dict_keys objects fully support the set operators (-, &, |),
       so the Phase 1 subtraction syntax is identical to the v1 set approach.]
    """

    # [Pull the `paths` map. Default to {} so a malformed or empty spec
    #  degrades to zero contracts without raising a KeyError.]
    paths: dict = openapi_doc.get("paths", {})

    # [Accumulator: signature string → operation object dict.]
    contracts: dict = {}

    # [Outer loop: each `path` is a URL template string, e.g. "/v1/users/{id}".
    #  `path_item` is the dict of HTTP methods (and optional structural keys)
    #  defined at that path.]
    for path, path_item in paths.items():

        # [Guard: path_item must be a dict. A null or scalar value is an
        #  invalid spec; skip silently rather than crashing the entire run.]
        if not isinstance(path_item, dict):
            continue

        # [Inner loop: inspect every key in the path item.]
        for key in path_item.keys():

            # [FILTER 1 — Vendor extensions. Any key prefixed with "x-" is a
            #  vendor extension by OpenAPI convention (e.g. "x-internal: true",
            #  "x-rate-limit-tier: gold"). They carry no callable contract
            #  semantics and must never produce diff findings.]
            if key.startswith("x-"):
                continue

            # [FILTER 2 — Path-level structural keys. The OpenAPI spec permits
            #  keys like "summary", "description", "parameters", "$ref", and
            #  "servers" directly on the path item object. Only keys that match
            #  a recognised HTTP verb define an actual callable endpoint.]
            if key.lower() not in HTTP_METHODS:
                continue

            # [Normalise the method to uppercase so that "get" in one spec and
            #  "GET" in another produce the same signature string and collide
            #  correctly during set arithmetic and dict lookup.]
            signature: str = f"{key.upper()} {path}"

            # [Extract the operation object. If the value at this key is not
            #  a dict (spec violation), substitute an empty dict so downstream
            #  comparisons receive a consistent type without special-casing.]
            operation: dict = path_item[key] if isinstance(path_item[key], dict) else {}

            # [Store the mapping. The set deduplication property of v1 is
            #  preserved here: if a malformed spec declares the same
            #  method+path twice, the second write wins — no false positives.]
            contracts[signature] = operation

    return contracts


# =============================================================================
# SECTION 3 — PHASE 1: REMOVED ENDPOINTS  (CRITICAL)
# =============================================================================

def _find_removed_endpoints(v1_contracts: dict, v2_contracts: dict) -> list:
    """
    [Phase 1 — set difference on the two contract key-sets.

     Computes:  removed = keys(V1) − keys(V2)

     A signature present in V1 but absent from V2 means the endpoint was
     deleted between versions. Any client that calls it will receive a 404
     (or a routing error, depending on the gateway) immediately upon V2
     deployment. This is always CRITICAL: no graceful degradation is possible
     when the route no longer exists.

     dict_keys objects in Python 3 behave like sets for the purpose of the
     difference operator ( - ), so the subtraction reads identically to v1's
     plain-set approach. The result is a new plain set of signature strings.]
    """

    # [SET DIFFERENCE — produces a plain set of signature strings that exist
    #  in the baseline key-view but not in the target key-view.]
    removed_signatures: set = v1_contracts.keys() - v2_contracts.keys()

    findings: list = []

    # [Sort for deterministic output. Python set iteration order is randomised
    #  by hash seed; sorted() gives a stable, alphabetical sequence so the
    #  findings list is identical across runs against the same input files.]
    for signature in sorted(removed_signatures):

        # [Split the signature back into method + path. maxsplit=1 ensures
        #  a path string that somehow contains spaces is not fragmented.]
        method, path = signature.split(" ", 1)

        findings.append({
            "signature":   signature,
            "method":      method,
            "path":        path,
            "severity":    "CRITICAL",
            "change_type": "ENDPOINT_REMOVED",
            "description": (
                "Endpoint existed in baseline but is absent in target. "
                "All clients calling this route will break on next deployment."
            ),
        })

    return findings


# =============================================================================
# SECTION 4 — PHASE 2: MODIFIED ENDPOINTS  (MEDIUM / LOW)
# =============================================================================

def _serialise_params(params: list) -> str:
    """
    [Produces a canonical JSON string representation of a `parameters` list
     so that two lists can be compared with a simple string equality check,
     regardless of key-ordering variation between spec authors or tooling.

     json.dumps with sort_keys=True is deterministic: two structurally
     identical parameter objects whose keys happen to be ordered differently
     will serialise to the same string and correctly compare as equal.
     Without sort_keys, the same logical list could produce different strings
     and create false-positive MEDIUM findings.]
    """

    # [sort_keys=True: normalise key order within each parameter object.
    #  separators=(',',':'): compact output — no spaces — makes the string
    #  cheaper to compare for endpoints with large parameter lists.]
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def _find_modified_endpoints(v1_contracts: dict, v2_contracts: dict) -> list:
    """
    [Phase 2 — intersection analysis on shared contracts.

     ─── STEP A: COMPUTE THE INTERSECTION ────────────────────────────────

     [The & operator on dict_keys returns a plain set of strings: every
      signature that appears as a key in BOTH v1_contracts AND v2_contracts.

      Mathematical form:   shared = keys(V1) ∩ keys(V2)

      These are the "surviving" endpoints — they were not deleted, so Phase 1
      produced no CRITICAL finding for them. Phase 2 now inspects their
      operation bodies to detect subtler contract drift.]

     ─── STEP B: RULE EVALUATION ORDER AND PRIORITY ──────────────────────

     Two rules are evaluated for each shared endpoint:

       Rule B → PARAMETERS_MODIFIED (MEDIUM)
         Checked first. A parameters change is higher severity than a docs
         change: it has a direct runtime impact on any client that sends or
         depends on the removed/renamed parameter.

       Rule A → DOCS_UPDATED (LOW)
         Checked only if Rule B did not fire. A docs-only change (summary or
         description text) carries zero runtime impact but is still worth
         flagging so the documentation team can review the new wording.

     SINGLE FINDING PER ENDPOINT:
       If both rules would fire for the same endpoint (parameters changed AND
       docs changed), only the MEDIUM finding is emitted. The MEDIUM record's
       description notes that docs were also updated, so no information is
       lost but the finding count is not artificially inflated. One card per
       endpoint keeps the downstream Jinja2 renderer output clean.]
    """

    # [STEP A — COMPUTE INTERSECTION.
    #  dict_keys supports the & operator; the result is a plain set of the
    #  signature strings common to both contract maps.]
    shared_signatures: set = v1_contracts.keys() & v2_contracts.keys()

    findings: list = []

    # [Iterate in sorted order for deterministic, alphabetical output.]
    for signature in sorted(shared_signatures):

        # [Retrieve the full Operation Object dicts stored by extract_contracts.
        #  These are the raw OpenAPI operation bodies — summary, description,
        #  parameters, requestBody, responses, etc. — for this specific
        #  method+path combination in each version.]
        v1_op: dict = v1_contracts[signature]
        v2_op: dict = v2_contracts[signature]

        method, path = signature.split(" ", 1)

        # ── RULE B — PARAMETERS_MODIFIED (MEDIUM) ─────────────────────────

        # [Extract the `parameters` list from each operation object.
        #  Defaulting to [] handles the valid case where an endpoint declares
        #  no parameters at all. This also means:
        #   - V1 has params, V2 omits the key entirely → [] vs [..] → MEDIUM
        #   - Both omit the key → [] vs [] → no finding (correct)]
        v1_params: list = v1_op.get("parameters", [])
        v2_params: list = v2_op.get("parameters", [])

        # [Delegate to _serialise_params() for a key-order-normalised
        #  comparison. Direct list equality (v1_params != v2_params) would
        #  produce false positives if two spec authors ordered the same
        #  parameter's keys differently (e.g. "name" before "in" vs after).]
        params_changed: bool = _serialise_params(v1_params) != _serialise_params(v2_params)

        if params_changed:
            # [Before building the MEDIUM record, also check whether docs
            #  changed simultaneously. If they did, the single MEDIUM record
            #  will mention both — honouring the single-finding-per-endpoint
            #  policy while preserving the complete picture for reviewers.]
            v1_summary:     str = v1_op.get("summary", "")
            v2_summary:     str = v2_op.get("summary", "")
            v1_description: str = v1_op.get("description", "")
            v2_description: str = v2_op.get("description", "")
            docs_also_changed: bool = (
                v1_summary != v2_summary or v1_description != v2_description
            )

            description = "Endpoint parameters were altered."
            if docs_also_changed:
                # [Annotate — the renderer can surface this as a sub-note
                #  inside the <Warning> callout without a separate <Info> card.]
                description += (
                    " Documentation text (summary or description) was also "
                    "updated in this version."
                )

            findings.append({
                "signature":       signature,
                "method":          method,
                "path":            path,
                "severity":        "MEDIUM",
                "change_type":     "PARAMETERS_MODIFIED",
                "description":     description,
                # [Attach parameter counts so the renderer can display a
                #  concise before/after delta without re-parsing the spec.]
                "params_v1_count": len(v1_params),
                "params_v2_count": len(v2_params),
            })

            # [PRIORITY GUARD — Rule B fired. Skip Rule A for this endpoint
            #  to enforce the single-finding-per-endpoint contract.]
            continue

        # ── RULE C — SCHEMA_DRIFT (MEDIUM) ────────────────────────────────────

        # [Compare the serialised `responses` and `requestBody` objects between
        #  V1 and V2. These hold the actual data shapes the endpoint exchanges
        #  with clients — a change here is a contract break even when the
        #  endpoint URL and parameters are unchanged.
        #
        #  json.dumps with sort_keys=True gives a canonical string that is
        #  independent of key-ordering variation between spec authors or tooling,
        #  preventing false positives from cosmetic reformatting.]
        v1_responses    = json.dumps(v1_op.get("responses",    {}), sort_keys=True)
        v2_responses    = json.dumps(v2_op.get("responses",    {}), sort_keys=True)
        v1_request_body = json.dumps(v1_op.get("requestBody",  {}), sort_keys=True)
        v2_request_body = json.dumps(v2_op.get("requestBody",  {}), sort_keys=True)

        responses_drifted    = v1_responses    != v2_responses
        request_body_drifted = v1_request_body != v2_request_body

        if responses_drifted or request_body_drifted:
            drifted_parts = []
            if request_body_drifted:
                drifted_parts.append("request body schema")
            if responses_drifted:
                drifted_parts.append("response schema")
            drifted_str = " and ".join(drifted_parts)

            findings.append({
                "signature":   signature,
                "method":      method,
                "path":        path,
                "severity":    "MEDIUM",
                "change_type": "SCHEMA_DRIFT",
                "description": (
                    f"The {drifted_str} changed between versions. "
                    "Clients that depend on the previous data shape may break."
                ),
            })
            continue

        # ── RULE A — DOCS_UPDATED (LOW) ────────────────────────────────────

        # [Extract the two documentation text fields from each operation.
        #  Both default to "" so that a key absent in one spec and set to ""
        #  in the other does NOT produce a spurious LOW finding.]
        v1_summary:     str = v1_op.get("summary", "")
        v2_summary:     str = v2_op.get("summary", "")
        v1_description: str = v1_op.get("description", "")
        v2_description: str = v2_op.get("description", "")

        # [Single boolean: either field changing qualifies as DOCS_UPDATED.
        #  String comparison is exact and case-sensitive — an author changing
        #  "Returns a list" to "returns a list" is a real edit worth noting.]
        docs_changed: bool = (
            v1_summary != v2_summary or v1_description != v2_description
        )

        if docs_changed:
            # [Identify which specific sub-fields changed so the reviewer
            #  knows exactly where to look without opening both spec files.]
            changed_fields = []
            if v1_summary != v2_summary:
                changed_fields.append("`summary`")
            if v1_description != v2_description:
                changed_fields.append("`description`")

            fields_str = " and ".join(changed_fields)

            findings.append({
                "signature":      signature,
                "method":         method,
                "path":           path,
                "severity":       "LOW",
                "change_type":    "DOCS_UPDATED",
                "description":    (
                    f"Documentation or description was modified "
                    f"({fields_str} changed). No runtime impact expected."
                ),
            })

        # [No `continue` here — if neither rule fires, the endpoint is clean
        #  and produces no finding. The loop simply moves to the next signature.]

    return findings


# =============================================================================
# SECTION 5 — COMBINER & SORTER
# =============================================================================

# [Severity rank table used as the primary sort key. Lower integer = higher
#  priority = appears earlier in the combined output list. CRITICAL issues
#  appear before MEDIUM, which appear before LOW — matching the natural
#  triage order an engineer scanning the report would use.
#  .get(…, 99) future-proofs the sort against any new severity level added
#  later: unknown levels are appended to the tail rather than crashing.]
_SEVERITY_RANK: dict = {"CRITICAL": 0, "MEDIUM": 1, "LOW": 2}


def _combine_and_sort(phase1: list, phase2: list) -> list:
    """
    [Merges Phase 1 (CRITICAL) and Phase 2 (MEDIUM/LOW) finding lists into
     one deterministic output list, sorted by:
       1. Severity rank  (CRITICAL → MEDIUM → LOW)
       2. Signature string  (alphabetical within the same severity tier)

     The secondary sort on signature guarantees byte-for-byte identical output
     across multiple runs against the same input files, which matters when the
     combined list is written to a version-controlled changelog: a purely
     semantic re-run produces no diff in git.]
    """

    combined: list = phase1 + phase2

    # [Sort in-place using a two-element tuple key. Python sorts tuples
    #  lexicographically: the severity rank is compared first; the signature
    #  string breaks ties within the same severity tier.]
    combined.sort(key=lambda finding: (
        _SEVERITY_RANK.get(finding["severity"], 99),
        finding["signature"],
    ))

    return combined


# =============================================================================
# SECTION 6 — CONSOLE REPORTER
# =============================================================================

# [Human-readable labels and Mintlify component hints for each severity tier.
#  The component hint is printed so any engineer reading the CI log
#  immediately knows which callout type the Jinja2 renderer will emit.]
_SEVERITY_LABEL: dict = {
    "CRITICAL": "✗ CRITICAL",
    "MEDIUM":   "⚠ MEDIUM  ",
    "LOW":      "ℹ LOW     ",
}

_MINTLIFY_COMPONENT: dict = {
    "CRITICAL": "<Danger>   (templates/callouts.mdx)",
    "MEDIUM":   "<Warning>  (templates/callouts.mdx)",
    "LOW":      "<Info>     (templates/callouts.mdx)",
}


def print_report(
    all_findings: list,
    baseline_path: str,
    target_path: str,
) -> None:
    """
    [Renders a severity-stratified diff report to stdout.

     The summary header shows per-tier counts so an engineer can assess the
     blast radius at a glance before reading individual finding blocks.
     Each finding block names the Mintlify callout component the downstream
     renderer will wrap it in, maintaining the full pipeline narrative in
     the CI log.]
    """

    # [Tally findings per severity tier for the summary header.]
    counts: dict = {"CRITICAL": 0, "MEDIUM": 0, "LOW": 0}
    for finding in all_findings:
        tier = finding.get("severity", "LOW")
        counts[tier] = counts.get(tier, 0) + 1

    total = len(all_findings)

    print("\n" + "=" * 70)
    print("  THE MINTLIFY SENTINEL — DIFF ENGINE v2.0 REPORT")
    print("=" * 70)
    print(f"  BASELINE (V1) : {os.path.abspath(baseline_path)}")
    print(f"  TARGET   (V2) : {os.path.abspath(target_path)}")
    print(f"  TOTAL FINDINGS: {total}")
    print(f"    ✗ CRITICAL   : {counts['CRITICAL']}  (ENDPOINT_REMOVED)")
    print(f"    ⚠ MEDIUM     : {counts['MEDIUM']}  (PARAMETERS_MODIFIED | SCHEMA_DRIFT)")
    print(f"    ℹ LOW        : {counts['LOW']}  (DOCS_UPDATED)")
    print("=" * 70 + "\n")

    # [Short-circuit: a clean diff is the desired steady state and deserves
    #  an explicit positive signal, not just an absence of output.]
    if not all_findings:
        print("  ✅  No changes detected. Diff is clean.\n")
        return

    # [Print one bordered block per finding so individual items don't blur
    #  together in long CI log streams.]
    for idx, finding in enumerate(all_findings, start=1):
        sev    = finding["severity"]
        label  = _SEVERITY_LABEL.get(sev, sev)
        comp   = _MINTLIFY_COMPONENT.get(sev, "")

        print(f"  [{idx:>2}]  {label}")
        print(f"         CHANGE TYPE  : {finding['change_type']}")
        print(f"         SIGNATURE    : {finding['signature']}")
        print(f"         DESCRIPTION  : {finding['description']}")

        # [For MEDIUM findings, show a concise parameter-count delta so the
        #  engineer can judge impact without opening the spec files.]
        if sev == "MEDIUM" and "params_v1_count" in finding:
            delta = finding["params_v2_count"] - finding["params_v1_count"]
            sign  = "+" if delta >= 0 else ""
            print(
                f"         PARAMS DELTA  : "
                f"V1={finding['params_v1_count']} → "
                f"V2={finding['params_v2_count']}  "
                f"({sign}{delta})"
            )

        print(f"         → Renders as  : {comp}\n")

    print("=" * 70 + "\n")


# =============================================================================
# SECTION 7 — PUBLIC API: run_diff()
# =============================================================================

def run_diff(baseline_path: str, target_path: str) -> list:
    """
    [Primary public interface — called by main.py (the Master Orchestrator).

     Sequences all pipeline stages and returns the combined, sorted findings
     list. This list is the data contract between the Diff Engine and the
     downstream Jinja2 renderer (architect_render.py):

       []                → clean diff, nothing to render.
       [finding, ...]    → one dict per detected change, any severity.

     The caller (main.py) owns the exit code decision. run_diff() is pure
     data: it produces and returns findings, never calls sys.exit().]
    """

    # ── Stage 1: Load ──────────────────────────────────────────────────────

    print(f"\n[sentinel] Loading baseline : {baseline_path}")
    baseline_doc: dict = load_openapi(baseline_path)

    print(f"[sentinel] Loading target   : {target_path}")
    target_doc: dict = load_openapi(target_path)

    # ── Stage 2: Extract ───────────────────────────────────────────────────

    # [extract_contracts returns dict[signature → operation_object].
    #  .keys() is used for set arithmetic; direct key access for Phase 2.]
    print("[sentinel] Extracting contracts from baseline …")
    v1_contracts: dict = extract_contracts(baseline_doc)
    print(f"           → {len(v1_contracts)} contract(s) found in baseline.")

    print("[sentinel] Extracting contracts from target …")
    v2_contracts: dict = extract_contracts(target_doc)
    print(f"           → {len(v2_contracts)} contract(s) found in target.")

    # ── Stage 3: Phase 1 — Removed Endpoints (CRITICAL) ───────────────────

    print("[sentinel] Phase 1 : computing set difference (removed endpoints) …")
    phase1_findings: list = _find_removed_endpoints(v1_contracts, v2_contracts)
    print(f"           → {len(phase1_findings)} CRITICAL finding(s).")

    # ── Stage 4: Phase 2 — Modified Endpoints (MEDIUM / LOW) ──────────────

    print("[sentinel] Phase 2 : computing intersection (modified endpoints) …")
    phase2_findings: list = _find_modified_endpoints(v1_contracts, v2_contracts)

    medium_count = sum(1 for f in phase2_findings if f["severity"] == "MEDIUM")
    low_count    = sum(1 for f in phase2_findings if f["severity"] == "LOW")
    print(f"           → {medium_count} MEDIUM finding(s),  {low_count} LOW finding(s).")

    # ── Stage 5: Combine, Sort, Report ────────────────────────────────────

    all_findings: list = _combine_and_sort(phase1_findings, phase2_findings)
    print_report(all_findings, baseline_path, target_path)

    return all_findings


# =============================================================================
# SECTION 8 — __main__ TEST HARNESS
# =============================================================================

if __name__ == "__main__":

    # [Anchor all default paths to the directory containing this script file,
    #  not the shell's CWD — so `python scripts/judge_diff.py` and
    #  `cd scripts && python judge_diff.py` resolve identical paths.]
    SCRIPT_DIR: str = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) == 3:
        # ── CLI MODE ──────────────────────────────────────────────────────
        # [Two explicit file paths provided. Use them directly; path
        #  resolution and validation happen inside load_openapi().]
        baseline_path = sys.argv[1]
        target_path   = sys.argv[2]
        print("[sentinel] CLI mode.")

    else:
        # ── TEST HARNESS MODE ─────────────────────────────────────────────
        # [No arguments (or an incomplete pair): fall back to the canonical
        #  test fixtures located in ../input/ relative to this script.
        #
        #  The test fixtures are designed so that:
        #    DELETE /v1/admin/users  → absent from V2  → CRITICAL
        #    GET    /v1/products     → parameters differ → MEDIUM
        #    GET    /v1/orders       → description differs → LOW
        #    POST   /v1/payments     → identical in V1 and V2 → no finding
        #
        #  This exercises all three severity tiers and the clean-endpoint
        #  path in a single run.]

        if len(sys.argv) == 2:
            print(
                f"[sentinel] WARNING: Expected 0 or 2 arguments; "
                f"got 1 ('{sys.argv[1]}'). Falling back to test harness.\n"
            )

        baseline_path = os.path.normpath(
            os.path.join(SCRIPT_DIR, "..", "input", "admin-openapi.json")
        )
        target_path = os.path.normpath(
            os.path.join(SCRIPT_DIR, "..", "input", "analytics.openapi.json")
        )

        print("[sentinel] Test harness mode.")
        print(f"           Baseline : {baseline_path}")
        print(f"           Target   : {target_path}\n")

    # ── Execute ───────────────────────────────────────────────────────────

    all_findings: list = run_diff(baseline_path, target_path)

    # ── Structured Data Output ────────────────────────────────────────────

    # [Pretty-print the findings list exactly as the Jinja2 renderer will
    #  receive it. This makes the CI log a complete audit trail: an engineer
    #  can reproduce the rendering step manually if needed.]
    print("[sentinel] Structured data payload (Jinja2 renderer input):")
    print("-" * 70)
    print(json.dumps(all_findings, indent=2))
    print("-" * 70 + "\n")

    # ── Summary Line ──────────────────────────────────────────────────────

    if not all_findings:
        print("[sentinel] Result : CLEAN — no changes detected.\n")
    else:
        critical = sum(1 for f in all_findings if f["severity"] == "CRITICAL")
        medium   = sum(1 for f in all_findings if f["severity"] == "MEDIUM")
        low      = sum(1 for f in all_findings if f["severity"] == "LOW")
        print(
            f"[sentinel] Result : {len(all_findings)} finding(s) — "
            f"{critical} CRITICAL, {medium} MEDIUM, {low} LOW.\n"
        )

    # ── Exit Code ─────────────────────────────────────────────────────────

    # [The Sentinel is an auditing and reporting tool, not a blocking gate.
    #  It always exits with code 0 so that developers retain the freedom to
    #  deploy intentional breaking changes after reviewing the findings.
    #  main.py is responsible for any higher-level pipeline gate decisions.]
    print("[sentinel] Exiting with code 0 (audit mode — non-blocking).\n")
    sys.exit(0)
