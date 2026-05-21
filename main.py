# =============================================================================
# main.py
# The Mintlify Sentinel — Master Orchestrator
#
# PURPOSE:
#   Single entry point for the entire Sentinel pipeline. This script is a
#   traffic controller — it owns sequencing, path resolution, and exit codes.
#   It contains no business logic of its own; all intelligence lives in the
#   three engine modules it orchestrates.
#
# PIPELINE STAGES:
#   STEP 1 — Gatekeeper  : Validate docs.json structural integrity.
#                          Hard gate: exits 1 on failure. A broken config
#                          destroys the entire Mintlify site build and makes
#                          all downstream steps meaningless.
#   STEP 2 — Diff Engine : Detect API contract changes across severity tiers
#                          (CRITICAL, MEDIUM, LOW) using semantic diffing.
#   STEP 3 — Renderer    : Emit a structured MDX changelog from diff results.
#   STEP 4 — Audit Gate  : Report findings and exit. Always exits 0 for API
#                          changes — the Sentinel is an audit tool, not a
#                          deployment blocker. Developers retain free will.
#
# EXIT CODE CONTRACT:
#   0 — Always, unless docs.json is structurally invalid (STEP 1 only).
#   1 — Only when docs.json fails validation in STEP 1.
#
#   Rationale: API contract changes (CRITICAL, MEDIUM, LOW findings from
#   judge_diff.py) are surfaced as informational audit output. Blocking a
#   deployment based on diff findings is a policy decision that belongs to
#   the developer and their team — not to the Sentinel. The rendered
#   changelog produced in STEP 3 gives all the context needed to make that
#   call consciously.
#
# USAGE:
#   python main.py                                        # uses default paths
#   python main.py --baseline V1.json --target V2.json   # explicit paths
#   python main.py --help                                 # show all flags
# =============================================================================

import os       # [standard library: build CWD-independent absolute paths]
import sys      # [standard library: mutate sys.path and control exit codes]
import argparse # [standard library: parse CLI flags --baseline, --target, --config]

# Force UTF-8 output on Windows where the default console encoding (cp1252)
# cannot encode the Unicode symbols used in pipeline banners (✓, ✗, ─, etc.).
from io import TextIOWrapper
if isinstance(sys.stdout, TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if isinstance(sys.stderr, TextIOWrapper):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# =============================================================================
# SECTION 1 — PATH RESOLUTION
# =============================================================================

# [Anchor every path to the directory that contains THIS file so that the
#  pipeline produces identical results regardless of where the operator
#  invokes it from — project root, scripts/, a CI runner working directory,
#  or any other location the shell happens to be in at invocation time.]
ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))

# [The scripts/ directory that houses the three engine modules.
#  Injected into sys.path below so they can be imported as top-level modules
#  without requiring an installed package or a relative-import hack.]
SCRIPTS_DIR: str = os.path.join(ROOT_DIR, "scripts")

# [DEFAULT input paths — used when the operator does not supply CLI flags.
#  Preserves backward compatibility: `python main.py` with no arguments
#  behaves identically to the original hardcoded behaviour.]
_DEFAULT_DOCS_CONFIG:  str = os.path.join(ROOT_DIR, "docs.json")
_DEFAULT_BASELINE_API: str = os.path.join(ROOT_DIR, "input", "admin-openapi.json")
_DEFAULT_TARGET_API:   str = os.path.join(ROOT_DIR, "input", "analytics.openapi.json")


# =============================================================================
# SECTION 2 — sys.path INJECTION & MODULE IMPORTS
# =============================================================================

# [Prepend scripts/ to sys.path so Python resolves `import judge_config` to
#  scripts/judge_config.py. Inserting at index 0 (rather than appending)
#  ensures our modules take precedence over any identically-named third-party
#  packages that might exist in the environment — an unlikely but real
#  collision risk in shared CI runner environments.]
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

# [Import all three engine modules inside a single try/except block so that
#  a missing script file surfaces as a clear, actionable error message rather
#  than a raw Python traceback that obscures which file is absent.
#
#  ModuleNotFoundError is a subclass of ImportError (Python 3.6+). Catching
#  the parent class covers both so the handler works on older patch releases.]
try:
    from judge_config     import validate_docs_config  # STEP 1 — returns bool
    from judge_diff       import run_diff              # STEP 2 — returns list
    from architect_render import render_changelog      # STEP 3 — returns None
    from notifier         import notify                # STEP 4b — optional notifications
except ImportError as exc:
    # [Surface the exact Python error message so the engineer can distinguish
    #  between a file that is simply absent and a file that exists but fails
    #  to import due to a syntax error or a missing dependency inside it.]
    print(f"\n[orchestrator] ✗ FATAL: Could not import a required engine module.")
    print(f"[orchestrator]   Detail  : {exc}")
    print(f"[orchestrator]   Verify that all three engine scripts exist in:")
    print(f"[orchestrator]     {SCRIPTS_DIR}")
    print(f"[orchestrator]     • judge_config.py")
    print(f"[orchestrator]     • judge_diff.py")
    print(f"[orchestrator]     • architect_render.py")
    sys.exit(1)


# =============================================================================
# SECTION 3 — PIPELINE ORCHESTRATOR
# =============================================================================

def run_pipeline(
    docs_config_path: str = _DEFAULT_DOCS_CONFIG,
    baseline_api_path: str = _DEFAULT_BASELINE_API,
    target_api_path: str = _DEFAULT_TARGET_API,
    slack_webhook: str = "",
    discord_webhook: str = "",
) -> int:
    """
    [Executes the four-stage Sentinel pipeline in strict sequence and returns
     an integer exit code for the __main__ block to pass to sys.exit().

     Keeping the exit code as a return value (rather than calling sys.exit()
     inside this function) means run_pipeline() can be imported and tested
     in isolation without the test runner process being terminated.]
    """

    # ── BANNER ────────────────────────────────────────────────────────────

    # [Print a structured header that identifies the pipeline run, all input
    #  paths, and the resolved project root. This gives CI log readers enough
    #  context to reproduce the run locally without hunting for config values.]
    print("\n" + "=" * 70)
    print("  THE MINTLIFY SENTINEL — MASTER ORCHESTRATOR")
    print("=" * 70)
    print(f"  ROOT      : {ROOT_DIR}")
    print(f"  CONFIG    : {docs_config_path}")
    print(f"  BASELINE  : {baseline_api_path}")
    print(f"  TARGET    : {target_api_path}")
    print("=" * 70 + "\n")

    # ── STEP 1 — GATEKEEPER ───────────────────────────────────────────────

    print("[orchestrator] -- STEP 1 / 4 : Config Validation (Gatekeeper) -----")

    # [Delegate entirely to validate_docs_config(). That function owns all
    #  field-level error formatting and reporting; the orchestrator only
    #  inspects the boolean return value to decide whether to continue.
    #
    #  This is the ONLY step in the pipeline that can return exit code 1.
    #  A structurally invalid docs.json causes the Mintlify site build to
    #  fail completely, making all downstream steps produce meaningless or
    #  misleading output. Stopping here protects the integrity of STEP 2
    #  and STEP 3 results.]
    config_is_valid: bool = validate_docs_config(docs_config_path)

    if not config_is_valid:
        # [Hard gate — the only true pipeline failure in this orchestrator.
        #  Print a focused message (validate_docs_config already printed the
        #  detailed field-level report) and return 1 immediately.]
        print("[orchestrator] ✗ CRITICAL: docs.json failed structural validation.")
        print("[orchestrator]   The pipeline cannot continue with an invalid config.")
        print("[orchestrator]   Fix all reported field errors and re-run.\n")
        return 1

    print("[orchestrator] ✓ STEP 1 PASSED — docs.json is structurally valid.\n")

    # ── STEP 2 — DIFF ENGINE ──────────────────────────────────────────────

    print("[orchestrator] -- STEP 2 / 4 : Diff Engine (Semantic Diffing) ------")

    # [Delegate all file loading, contract extraction, set-difference, and
    #  intersection logic to run_diff(). The return value is a structured
    #  list of finding dicts — one per detected change — sorted by severity
    #  (CRITICAL → MEDIUM → LOW) and then alphabetically by signature.
    #
    #  An empty list means a clean diff. A non-empty list carries findings
    #  of one or more severity tiers. Either way, the pipeline continues:
    #  findings are informational, not blocking.]
    contract_findings: list = run_diff(baseline_api_path, target_api_path)

    # [Tally findings per severity tier for the STEP 2 completion line so
    #  the CI log gives an at-a-glance breakdown before the renderer runs.]
    critical_count: int = sum(
        1 for f in contract_findings if f.get("severity") == "CRITICAL"
    )
    medium_count: int = sum(
        1 for f in contract_findings if f.get("severity") == "MEDIUM"
    )
    low_count: int = sum(
        1 for f in contract_findings if f.get("severity") == "LOW"
    )

    print(
        f"[orchestrator] ✓ STEP 2 COMPLETE — "
        f"{len(contract_findings)} finding(s) : "
        f"{critical_count} CRITICAL, {medium_count} MEDIUM, {low_count} LOW.\n"
    )

    # ── STEP 3 — RENDERER ─────────────────────────────────────────────────

    print("[orchestrator] -- STEP 3 / 4 : Changelog Renderer ----------------")

    # [Pass the findings list directly into render_changelog(). That function
    #  owns all MDX generation, Jinja2 template rendering, and file I/O.
    #
    #  An empty list is a valid and expected input — the renderer must handle
    #  a clean diff gracefully (e.g. emit a "no changes this release" notice
    #  or write nothing). The orchestrator does not gate on list length here.]
    render_changelog(contract_findings)

    print("[orchestrator] ✓ STEP 3 COMPLETE — Changelog rendered.\n")

    # ── STEP 4 — AUDIT GATE ───────────────────────────────────────────────

    print("[orchestrator] -- STEP 4 / 4 : Audit Gate --------------------------")

    # [AUDIT MODE — the Sentinel is a reporting and documentation tool.
    #  Its role is to surface contract changes clearly and completely so that
    #  developers can make an informed, conscious decision about whether to
    #  proceed. That decision is the developer's to make, not the pipeline's.
    #
    #  Returning 0 in both branches below means CI never blocks a deployment
    #  solely because API findings were detected. The rendered changelog from
    #  STEP 3 provides all the context the developer needs to act.]

    if contract_findings:
        # [Findings were detected. Summarise them by tier and direct the
        #  developer to the rendered changelog for the full picture.
        #  The ⚠ symbol signals "attention required" without implying failure.]
        print(
            f"[orchestrator] ⚠ AUDIT COMPLETE — "
            f"{len(contract_findings)} contract change(s) detected "
            f"({critical_count} CRITICAL, {medium_count} MEDIUM, {low_count} LOW)."
        )
        print(
            "[orchestrator]   Review the rendered changelog before proceeding. "
            "Deployment decision is yours.\n"
        )
    else:
        # [Clean diff — no changes across any severity tier. The API surface
        #  is stable relative to the baseline. Safe to proceed.]
        print(
            "[orchestrator] ✓ PIPELINE PASSED — "
            "No contract changes detected. API surface is stable.\n"
        )

    # ── NOTIFICATIONS ─────────────────────────────────────────────────────

    # [Fire notifications after the audit summary so the console output is
    #  fully written before any network call can block or fail.
    #  notify() never raises — a failed webhook is a warning, not a crash.]
    notify(
        contract_findings,
        slack_url=slack_webhook,
        discord_url=discord_webhook,
    )

    # [Always return 0 from this step. Exit code 1 is reserved exclusively
    #  for the docs.json structural failure handled in STEP 1 above.]
    return 0


# =============================================================================
# SECTION 4 — ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # [Parse CLI arguments. All three paths are optional — omitting any of
    #  them falls back to the hardcoded default so that `python main.py` with
    #  no arguments produces identical behaviour to the original script.]
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="The Mintlify Sentinel — API contract change detector.",
    )
    parser.add_argument(
        "--baseline",
        default=_DEFAULT_BASELINE_API,
        metavar="PATH",
        help=(
            "Path to the baseline OpenAPI spec (V1 — last known-good contract). "
            f"Default: {_DEFAULT_BASELINE_API}"
        ),
    )
    parser.add_argument(
        "--target",
        default=_DEFAULT_TARGET_API,
        metavar="PATH",
        help=(
            "Path to the target OpenAPI spec (V2 — candidate being promoted). "
            f"Default: {_DEFAULT_TARGET_API}"
        ),
    )
    parser.add_argument(
        "--config",
        default=_DEFAULT_DOCS_CONFIG,
        metavar="PATH",
        help=(
            "Path to the Mintlify docs.json configuration file. "
            f"Default: {_DEFAULT_DOCS_CONFIG}"
        ),
    )
    parser.add_argument(
        "--slack-webhook",
        default="",
        metavar="URL",
        help=(
            "Slack Incoming Webhook URL. "
            "Sends a findings summary to Slack after the pipeline completes. "
            "Can also be set via the SLACK_WEBHOOK_URL environment variable."
        ),
    )
    parser.add_argument(
        "--discord-webhook",
        default="",
        metavar="URL",
        help=(
            "Discord Webhook URL. "
            "Sends a findings summary to Discord after the pipeline completes. "
            "Can also be set via the DISCORD_WEBHOOK_URL environment variable. "
            # ----------------------------------------------------------------
            # REPLACE THE PLACEHOLDER IN .env.example WITH YOUR ACTUAL URL.
            # Create one in: Discord Server > Channel Settings >
            #   Integrations > Webhooks > New Webhook > Copy Webhook URL
            # ----------------------------------------------------------------
        ),
    )
    args = parser.parse_args()

    # [Execute the pipeline with resolved paths and forward its integer return
    #  value directly to sys.exit(). __main__ is solely responsible for the
    #  POSIX exit code; all sequencing and logic live inside run_pipeline()
    #  where they are testable without subprocesses.]
    sys.exit(run_pipeline(
        docs_config_path=args.config,
        baseline_api_path=args.baseline,
        target_api_path=args.target,
        slack_webhook=args.slack_webhook,
        discord_webhook=args.discord_webhook,
    ))
