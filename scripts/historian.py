# =============================================================================
# historian.py — Version History Store
# The Mintlify Sentinel
#
# PURPOSE:
#   Appends each pipeline run to output/history.json so that findings can be
#   reviewed across multiple releases. No database required — a flat JSON array
#   keyed by timestamp is sufficient until the product scales.
#
# PUBLIC API:
#   append_run(findings, baseline_path, target_path) → list
#     Appends a run record and returns the updated history.
#
#   load_history() → list
#     Returns the full history list, newest first. Empty list if no history.
#
# RECORD SCHEMA:
#   {
#     "id":        "20260521_143015",          # sortable run identifier
#     "timestamp": "2026-05-21T14:30:15",      # ISO 8601
#     "baseline":  "admin-openapi.json",       # filename only (portable)
#     "target":    "analytics.openapi.json",
#     "total":     6,
#     "critical":  6,
#     "medium":    0,
#     "low":       0,
#     "findings":  [ ... ]                     # full finding dicts
#   }
# =============================================================================

import json
import os
from datetime import datetime

_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR    = os.path.dirname(_SCRIPT_DIR)
HISTORY_FILE = os.path.join(_ROOT_DIR, "output", "history.json")


# =============================================================================
# PUBLIC API
# =============================================================================

def append_run(
    findings: list,
    baseline_path: str,
    target_path: str,
) -> list:
    """Append a run record and persist. Returns the updated history list."""
    now = datetime.now()
    record = {
        "id":        now.strftime("%Y%m%d_%H%M%S"),
        "timestamp": now.isoformat(timespec="seconds"),
        "baseline":  os.path.basename(baseline_path),
        "target":    os.path.basename(target_path),
        "total":     len(findings),
        "critical":  sum(1 for f in findings if f.get("severity") == "CRITICAL"),
        "medium":    sum(1 for f in findings if f.get("severity") == "MEDIUM"),
        "low":       sum(1 for f in findings if f.get("severity") == "LOW"),
        "findings":  findings,
    }
    history = load_history()
    history.insert(0, record)
    _save(history)
    return history


def load_history() -> list:
    """Return the full history list (newest first). Empty list if no history yet."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception:
        return []


# =============================================================================
# PRIVATE
# =============================================================================

def _save(history: list) -> None:
    """Atomic write — use a .tmp file then os.replace() to avoid partial writes."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    tmp_path = HISTORY_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2)
    os.replace(tmp_path, HISTORY_FILE)
