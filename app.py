import contextlib
import io
import os
import sys
import tempfile
from datetime import datetime

import streamlit as st

ROOT_DIR  = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
OUTPUT_FILE = os.path.join(ROOT_DIR, "output", "changelog.mdx")

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from judge_diff       import run_diff
from architect_render import render_changelog
from judge_config     import validate_docs_config
from notifier         import notify


# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="The Mintlify Sentinel",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Mintlify green primary button */
    div.stButton > button[kind="primary"] {
        background-color: #16A34A;
        border-color: #16A34A;
        color: white;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #15803D;
        border-color: #15803D;
    }
    div.stButton > button[kind="primary"]:disabled {
        background-color: #4B5563;
        border-color: #4B5563;
    }
    /* Tighten finding cards */
    div[data-testid="stAlert"] p { margin-bottom: 0.25rem; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.markdown("## 🛡️ The Mintlify Sentinel")
    st.markdown(
        "API contract change detector for "
        "[Mintlify](https://mintlify.com) documentation sites."
    )
    st.divider()

    st.markdown("### Notifications")
    st.caption("Fire Slack or Discord alerts after the pipeline runs.")
    slack_url   = st.text_input(
        "Slack Webhook URL",
        placeholder="https://hooks.slack.com/services/...",
        type="password",
        key="slack_url",
    )
    discord_url = st.text_input(
        "Discord Webhook URL",
        placeholder="https://discord.com/api/webhooks/...",
        type="password",
        key="discord_url",
    )

    st.divider()
    st.markdown("### Pipeline")
    st.markdown(
        "| Stage | Module |\n"
        "|-------|--------|\n"
        "| 1 — Config gate | `judge_config.py` |\n"
        "| 2 — Diff engine | `judge_diff.py` |\n"
        "| 3 — MDX renderer | `architect_render.py` |\n"
        "| 4 — Audit gate | `main.py` |"
    )


# =============================================================================
# HEADER
# =============================================================================

st.title("🛡️ The Mintlify Sentinel")
st.markdown(
    "Upload two OpenAPI specs and detect breaking API contract changes "
    "before they reach production."
)
st.divider()


# =============================================================================
# TABS
# =============================================================================

tab_run, tab_validate = st.tabs(["Run Sentinel", "Validate Config"])


# =============================================================================
# TAB 1 — RUN SENTINEL
# =============================================================================

with tab_run:

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Baseline spec — V1")
        st.caption("The last known-good API contract.")
        baseline_file = st.file_uploader(
            "Baseline",
            type=["json"],
            label_visibility="collapsed",
            key="baseline_upload",
        )
        if baseline_file:
            st.caption(f"✓ {baseline_file.name}")

    with col2:
        st.markdown("#### Target spec — V2")
        st.caption("The candidate being promoted to production.")
        target_file = st.file_uploader(
            "Target",
            type=["json"],
            label_visibility="collapsed",
            key="target_upload",
        )
        if target_file:
            st.caption(f"✓ {target_file.name}")

    st.markdown("")

    run_clicked = st.button(
        "Run Sentinel",
        type="primary",
        disabled=not (baseline_file and target_file),
        use_container_width=True,
    )

    # ── RUN PIPELINE ─────────────────────────────────────────────────────────

    if run_clicked and baseline_file and target_file:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="wb") as f1:
            f1.write(baseline_file.getvalue())
            baseline_path = f1.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="wb") as f2:
            f2.write(target_file.getvalue())
            target_path = f2.name

        try:
            log_buf = io.StringIO()
            with st.spinner("Running Sentinel..."):
                with contextlib.redirect_stdout(log_buf):
                    findings = run_diff(baseline_path, target_path)
                    render_changelog(findings)

                notif_result = None
                if slack_url or discord_url:
                    notif_result = notify(
                        findings,
                        slack_url=slack_url,
                        discord_url=discord_url,
                    )

            st.session_state["findings"]     = findings
            st.session_state["last_run"]     = datetime.now().strftime("%H:%M:%S")
            st.session_state["notif_result"] = notif_result
            st.session_state["pipeline_log"] = log_buf.getvalue()

        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
        finally:
            os.unlink(baseline_path)
            os.unlink(target_path)

    # ── RESULTS ──────────────────────────────────────────────────────────────

    if "findings" in st.session_state:
        findings  = st.session_state["findings"]
        last_run  = st.session_state.get("last_run", "")

        critical = sum(1 for f in findings if f.get("severity") == "CRITICAL")
        medium   = sum(1 for f in findings if f.get("severity") == "MEDIUM")
        low      = sum(1 for f in findings if f.get("severity") == "LOW")

        st.divider()
        st.caption(f"Last run: {last_run}")

        # Summary bar
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total findings", len(findings))
        c2.metric("🔴 CRITICAL",    critical)
        c3.metric("🟡 MEDIUM",      medium)
        c4.metric("🔵 LOW",         low)

        st.markdown("")

        # Finding cards
        if not findings:
            st.success(
                "No breaking changes detected. The API surface is stable. "
                "Safe to deploy."
            )
        else:
            for f in findings:
                sev       = f.get("severity", "LOW")
                sig       = f.get("signature", "")
                ctype     = f.get("change_type", "")
                desc      = f.get("description", "")
                card_body = f"**{ctype}** — `{sig}`\n\n{desc}"

                if sev == "CRITICAL":
                    st.error(f"🔴 {card_body}")
                elif sev == "MEDIUM":
                    st.warning(f"🟡 {card_body}")
                else:
                    st.info(f"🔵 {card_body}")

        # Download changelog.mdx
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "r", encoding="utf-8") as fh:
                mdx_bytes = fh.read()
            st.download_button(
                label="Download changelog.mdx",
                data=mdx_bytes,
                file_name="changelog.mdx",
                mime="text/plain",
                use_container_width=True,
            )

        # Pipeline log (developer view)
        pipeline_log = st.session_state.get("pipeline_log", "")
        if pipeline_log:
            with st.expander("Pipeline log"):
                st.code(pipeline_log, language="text")

        # Raw JSON findings (developer view)
        with st.expander("Raw JSON findings"):
            st.json(findings if findings else [])

        # Notification status
        notif_result = st.session_state.get("notif_result")
        if notif_result:
            st.markdown("**Notification status**")
            slack_res   = notif_result.get("slack",   {})
            discord_res = notif_result.get("discord", {})

            if slack_url:
                if slack_res.get("sent"):
                    st.success(f"✅ Slack — sent (HTTP {slack_res.get('status')})")
                else:
                    st.error(f"❌ Slack — failed: {slack_res.get('error')}")

            if discord_url:
                if discord_res.get("sent"):
                    st.success(f"✅ Discord — sent (HTTP {discord_res.get('status')})")
                else:
                    st.error(f"❌ Discord — failed: {discord_res.get('error')}")


# =============================================================================
# TAB 2 — VALIDATE CONFIG
# =============================================================================

with tab_validate:
    st.markdown("#### Validate docs.json")
    st.markdown(
        "Upload your Mintlify `docs.json` to validate it against the "
        "Pydantic v2 schema. This runs Stage 1 of the pipeline in isolation — "
        "useful for catching config errors before running a full diff."
    )

    config_file = st.file_uploader("docs.json", type=["json"], key="config_upload")

    if config_file:
        validate_clicked = st.button("Validate", type="primary", key="validate_btn")

        if validate_clicked:
            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, mode="wb"
            ) as tf:
                tf.write(config_file.getvalue())
                config_path = tf.name

            try:
                with st.spinner("Validating..."):
                    is_valid = validate_docs_config(config_path)

                if is_valid:
                    st.success(
                        f"**{config_file.name}** is structurally valid. "
                        "Safe to deploy."
                    )
                else:
                    st.error(
                        f"**{config_file.name}** failed validation. "
                        "Check the terminal output for field-level errors."
                    )

            except Exception as exc:
                st.error(f"Validation error: {exc}")
            finally:
                os.unlink(config_path)
