"""
IDAMP Streamlit App — Human-facing entry point for the Intent-Driven Agentic Medallion Pipeline.

This interface allows users to:
1. Upload CSV files and specify business intent
2. Review and approve AI-generated transformation rules at each layer
3. Monitor pipeline execution through a visual progress tracker
4. Download generated reports and artifacts
5. Explore data lineage and transformations
6. Ask follow-up questions about the data
"""

import sys
import json
import html
from textwrap import dedent
from pathlib import Path

import streamlit as st
import pandas as pd

from core.config import LANDING_DIR, STTM_DIR, GOLD_DIR
from core.audit import AuditLogger
from core.chat_ui import render_chat_interface
from core.lineage_ui import render_lineage_dashboard
from agents.orchestrator import (
    run_until_bronze_sttm,
    run_bronze_to_silver_sttm,
    run_silver_to_gold_sttm,
    run_gold_and_report,
)


# ─── Page Configuration ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="IDAMP - Intent-Driven Agentic Medallion Pipeline",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── Constants ───────────────────────────────────────────────────────────────

PROGRESS_STEPS = [
    ("upload", "Upload & Intent"),
    ("bronze_sttm", "Bronze STTM Review"),
    ("bronze_load", "Bronze Layer Load"),
    ("silver_sttm", "Silver STTM Review"),
    ("silver_load", "Silver Layer Load"),
    ("gold_sttm", "Gold STTM Review"),
    ("gold_load", "Gold Layer Load"),
    ("report", "Executive Report"),
]

SELECTION_COL = "_selected_for_approval"


# ─── Progress Banner Rendering ──────────────────────────────────────────────

def render_progress_banner(current_phase: str, state: dict, report_complete: bool) -> None:
    """
    Render a professional progress stepper showing pipeline phase progress.
    
    Args:
        current_phase: Current phase key (e.g., "bronze_sttm")
        state: Pipeline state dict
        report_complete: Whether the report has been generated
    """
    # Find current step index
    current_idx = next(
        (i for i, (key, _) in enumerate(PROGRESS_STEPS) if key == current_phase),
        0,
    )

    # Determine completed steps
    completed_steps = set()
    if state.get("profile_path"):
        completed_steps.add(0)  # upload
    if state.get("sttm_bronze_path") and state.get("bronze_sttm_approved"):
        completed_steps.add(1)  # bronze_sttm
    if state.get("bronze_output_paths"):
        completed_steps.add(2)  # bronze_load
    if state.get("sttm_silver_path") and state.get("silver_sttm_approved"):
        completed_steps.add(3)  # silver_sttm
    if state.get("silver_output_paths"):
        completed_steps.add(4)  # silver_load
    if state.get("sttm_gold_path") and state.get("gold_sttm_approved"):
        completed_steps.add(5)  # gold_sttm
    if state.get("gold_output_paths"):
        completed_steps.add(6)  # gold_load
    if report_complete:
        completed_steps.add(7)  # report

    # Build HTML for progress bar
    steps_html = ""
    for i, (step_key, step_label) in enumerate(PROGRESS_STEPS):
        is_current = i == current_idx
        is_completed = i in completed_steps

        if is_completed:
            step_class = "step completed"
            step_icon = "✓"
            step_color = "#10b981"  # Green
        elif is_current:
            step_class = "step current"
            step_icon = str(i + 1)
            step_color = "#3b82f6"  # Blue
        else:
            step_class = "step"
            step_icon = str(i + 1)
            step_color = "#d1d5db"  # Gray

        steps_html += f"""
        <div class="step-container {step_class}">
            <div class="step-circle" style="background-color: {step_color};">
                {step_icon}
            </div>
            <div class="step-label">{step_label}</div>
        </div>
        """

    # Custom CSS for styling
    progress_css = dedent("""
        <style>
            .progress-banner {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 24px;
                border-radius: 12px;
                margin-bottom: 24px;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
                position: sticky;
                top: 60px;
                z-index: 50;
            }
            .progress-title {
                color: white;
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 16px;
                text-align: center;
            }
            .progress-container {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 8px;
            }
            .step-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 8px;
            }
            .step-circle {
                width: 44px;
                height: 44px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                font-size: 16px;
                transition: all 0.3s ease;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            }
            .step.current .step-circle {
                transform: scale(1.1);
                box-shadow: 0 4px 16px rgba(59, 130, 246, 0.4);
            }
            .step.completed .step-circle {
                box-shadow: 0 4px 16px rgba(16, 185, 129, 0.4);
            }
            .step-label {
                font-size: 12px;
                color: white;
                text-align: center;
                max-width: 90px;
                word-wrap: break-word;
                opacity: 0.9;
            }
            .step.current .step-label {
                font-weight: bold;
                opacity: 1;
            }
        </style>
    """)

    progress_html = f"""
    {progress_css}
    <div class="progress-banner">
        <div class="progress-title">🚀 Pipeline Progress</div>
        <div class="progress-container">
            {steps_html}
        </div>
    </div>
    """

    st.markdown(progress_html, unsafe_allow_html=True)


# ─── Helper Functions ───────────────────────────────────────────────────────

def _reset_analysis_session() -> None:
    """Reset the analysis session to start a new pipeline run."""
    st.session_state.phase = "upload"
    st.session_state.pipeline_state = {}
    st.session_state.current_run_id = None


def _prepare_sttm_editor_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare STTM DataFrame for editing by adding selection column."""
    df_copy = df.copy()
    df_copy.insert(0, SELECTION_COL, True)
    # Convert all columns to string to avoid type issues
    for col in df_copy.columns:
        if col != SELECTION_COL:
            df_copy[col] = df_copy[col].astype(str)
    return df_copy


def _extract_selected_rows(edited_df: pd.DataFrame) -> pd.DataFrame:
    """Extract only the rows selected for approval."""
    selected = edited_df[edited_df[SELECTION_COL] == True].copy()
    selected = selected.drop(columns=[SELECTION_COL])
    return selected


def _current_audit_logs() -> list[dict]:
    """Get audit logs for the current run."""
    run_id = st.session_state.get("current_run_id")
    if not run_id:
        return []
    logger = AuditLogger(run_id)
    return logger.get_logs()


def _format_audit_entry(entry: dict) -> str:
    """Format an audit log entry for display."""
    timestamp = entry.get("timestamp", "")
    agent = entry.get("agent", "Unknown")
    action = entry.get("action", "Unknown")
    status = entry.get("status", "info")

    return f"{timestamp} | {agent} | {action} ({status})"


def _status_class(entry: dict) -> str:
    """Return CSS class based on audit entry status."""
    status = entry.get("status", "").lower()
    if "error" in status or "fail" in status:
        return "is-failed"
    elif "success" in status or "complete" in status:
        return "is-success"
    elif "progress" in status or "running" in status:
        return "is-progress"
    else:
        return "is-neutral"


def _render_audit_card(entry: dict, latest: bool = False) -> str:
    """Render HTML for an audit log entry card."""
    timestamp = entry.get("timestamp", "N/A")
    agent = entry.get("agent", "Unknown")
    action = entry.get("action", "Unknown")
    status = entry.get("status", "info")
    status_class = _status_class(entry)

    # Extract optional fields
    phase = entry.get("phase", "")
    rationale = entry.get("rationale", "")

    status_badge = f'<span class="status-badge {status_class}">{status}</span>'

    card_html = f"""
    <div class="audit-card {'latest' if latest else ''}">
        <div class="audit-header">
            <div class="audit-meta">
                <span class="audit-agent">🤖 {html.escape(agent)}</span>
                <span class="audit-action">{html.escape(action)}</span>
                {status_badge}
            </div>
            <div class="audit-time">{timestamp}</div>
        </div>
        <div class="audit-body">
            {f'<p><strong>Phase:</strong> {html.escape(phase)}</p>' if phase else ''}
            {f'<p><strong>Notes:</strong> {html.escape(rationale)}</p>' if rationale else ''}
        </div>
    </div>
    """
    return card_html


def render_audit_trail_panel() -> None:
    """Render the audit trail sidebar panel with all logged events."""
    logs = _current_audit_logs()

    if not logs:
        st.info("No audit events yet. Start a pipeline run to see activity.")
        return

    # Custom CSS for audit cards
    audit_css = dedent("""
        <style>
            .audit-trail {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            .audit-card {
                border-left: 4px solid #d1d5db;
                background: #f9fafb;
                padding: 12px;
                border-radius: 6px;
                transition: all 0.2s ease;
            }
            .audit-card.latest {
                border-left-color: #3b82f6;
                background: #eff6ff;
                box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
                transform: scale(1.01);
            }
            .audit-card:hover {
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
            }
            .audit-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            .audit-meta {
                display: flex;
                gap: 8px;
                align-items: center;
                flex-wrap: wrap;
            }
            .audit-agent {
                font-weight: bold;
                color: #1f2937;
                font-size: 14px;
            }
            .audit-action {
                color: #6b7280;
                font-size: 13px;
            }
            .status-badge {
                font-size: 11px;
                padding: 2px 8px;
                border-radius: 4px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .status-badge.is-success {
                background-color: #d1fae5;
                color: #065f46;
            }
            .status-badge.is-failed {
                background-color: #fee2e2;
                color: #991b1b;
            }
            .status-badge.is-progress {
                background-color: #fef3c7;
                color: #92400e;
            }
            .status-badge.is-neutral {
                background-color: #f3f4f6;
                color: #374151;
            }
            .audit-time {
                font-size: 11px;
                color: #9ca3af;
            }
            .audit-body {
                font-size: 12px;
                color: #4b5563;
                line-height: 1.5;
            }
            .audit-body p {
                margin: 4px 0;
            }
        </style>
    """)

    st.markdown(audit_css, unsafe_allow_html=True)

    # Show latest event prominently
    latest_entry = logs[-1] if logs else None
    if latest_entry:
        st.subheader("🎯 Latest Event")
        st.markdown(_render_audit_card(latest_entry, latest=True), unsafe_allow_html=True)

    # Show previous events
    if len(logs) > 1:
        st.subheader("📜 Event History")
        audit_html = '<div class="audit-trail">'
        for entry in reversed(logs[:-1][:20]):  # Show last 20 events, excluding latest
            audit_html += _render_audit_card(entry, latest=False)
        audit_html += "</div>"
        st.markdown(audit_html, unsafe_allow_html=True)

    # Download audit logs as JSON
    if logs:
        audit_json = json.dumps(logs, indent=2, default=str)
        st.download_button(
            label="📥 Download Audit Logs (JSON)",
            data=audit_json,
            file_name=f"audit_logs_{st.session_state.get('current_run_id', 'run')}.json",
            mime="application/json",
        )


# ─── Main Application ───────────────────────────────────────────────────────

# Main title and description
st.title("🏗️ Intent-Driven Agentic Medallion Workflow")
st.markdown(dedent("""
    Welcome to **IDAMP** — an AI-powered data pipeline that transforms raw data into actionable insights.
    
    **How it works:**
    1. 📤 Upload your CSV files and describe your business question
    2. 🤖 AI agents profile your data and generate transformation rules
    3. ✅ Review and approve transformation rules at each layer
    4. 🔄 Automatic execution through Bronze → Silver → Gold layers
    5. 📊 Generate beautiful HTML reports with charts and insights
    
    ---
"""))

# Initialize session state
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = {}
if "phase" not in st.session_state:
    st.session_state.phase = "upload"
if "current_run_id" not in st.session_state:
    st.session_state.current_run_id = ""
if "report_complete" not in st.session_state:
    st.session_state.report_complete = False

# Update current_run_id from pipeline_state if exists
if st.session_state.pipeline_state and st.session_state.pipeline_state.get("run_id"):
    st.session_state.current_run_id = st.session_state.pipeline_state["run_id"]

# Render progress banner
render_progress_banner(st.session_state.phase, st.session_state.pipeline_state, st.session_state.report_complete)

# Create layout columns
main_col, audit_col = st.columns([3.4, 1.4])

# Audit trail sidebar
with audit_col:
    st.subheader("📋 Audit Trail")
    render_audit_trail_panel()

# Main content area
with main_col:
    # ── Phase 1: Upload Data & Define Intent ──────────────────────────────────
    if st.session_state.phase == "upload":
        st.header("📤 Phase 1: Upload Data & Define Intent")
        st.markdown("Upload your CSV files and describe what you want to analyze.")

        # File uploader
        uploaded_files = st.file_uploader(
            "Choose CSV files to analyze",
            type=["csv"],
            accept_multiple_files=True,
            help="Upload one or more CSV files with your data.",
        )

        # Business intent textarea
        business_intent = st.text_area(
            "What is your business question or objective?",
            placeholder="e.g., 'Analyze sales performance by region and product category for Q3 2024'",
            height=100,
            help="Be specific about what insights you want to extract from the data.",
        )

        # Start workflow button
        if st.button(
            "🚀 Start Workflow",
            disabled=(not uploaded_files or not business_intent),
            use_container_width=True,
            type="primary",
        ):
            with st.spinner("🔍 Profiling data and generating Bronze STTM..."):
                try:
                    # Save uploaded files to LANDING_DIR
                    saved_paths = []
                    for uploaded_file in uploaded_files:
                        file_path = LANDING_DIR / uploaded_file.name
                        file_path.write_bytes(uploaded_file.getbuffer())
                        saved_paths.append(str(file_path))

                    # Run Phase 1
                    result_state = run_until_bronze_sttm(saved_paths, business_intent)

                    # Store in session state
                    st.session_state.pipeline_state = result_state
                    st.session_state.current_run_id = result_state.get("run_id", "")

                    # Move to next phase
                    st.session_state.phase = "bronze_sttm"

                    st.success("✅ Data profiled and Bronze STTM rules generated! Review them below.")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error during Phase 1: {str(e)}")
                    logger = AuditLogger(st.session_state.get("current_run_id", ""))
                    logger.log("streamlit_app", "phase1_ui_error", error=str(e))

    # ── Phase 2: Review Bronze Layer STTM ────────────────────────────────────
    elif st.session_state.phase == "bronze_sttm":
        st.header("🥉 Phase 2: Review Bronze Layer STTM")
        st.info(
            "🔍 **Bronze Layer:** Raw data ingestion with minimal transformation. "
            "Review the transformation rules below — these map your source columns to the Bronze staging layer."
        )

        try:
            sttm_path = st.session_state.pipeline_state.get("sttm_bronze_path")
            if not sttm_path:
                raise ValueError("No Bronze STTM path found")

            sttm_df = pd.read_csv(sttm_path)

            if sttm_df.empty:
                raise pd.errors.EmptyDataError("STTM file is empty")

            st.metric("Total Transformations", len(sttm_df))

            # Prepare for editing
            editor_df = _prepare_sttm_editor_df(sttm_df)

            # Data editor
            edited_df = st.data_editor(
                editor_df,
                use_container_width=True,
                height=400,
                key="bronze_sttm_editor",
            )

            # Approve button
            if st.button("✅ Approve & Continue", use_container_width=True, type="primary"):
                with st.spinner("Executing Bronze layer..."):
                    try:
                        # Save selected rows
                        selected_df = _extract_selected_rows(edited_df)
                        selected_df.to_csv(sttm_path, index=False)

                        # Run Phase 2
                        st.session_state.pipeline_state["bronze_sttm_approved"] = True
                        result_state = run_bronze_to_silver_sttm(st.session_state.pipeline_state)

                        # Update session
                        st.session_state.pipeline_state = result_state
                        st.session_state.phase = "silver_sttm"

                        st.success("✅ Bronze layer approved! Proceeding to Silver layer review.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error approving Bronze STTM: {str(e)}")
                        logger = AuditLogger(st.session_state.get("current_run_id", ""))
                        logger.log("streamlit_app", "bronze_sttm_approve_error", error=str(e))

        except pd.errors.EmptyDataError:
            st.error("❌ Bronze STTM file is empty or corrupted. Starting over...")
            if st.button("🔄 Restart Workflow"):
                _reset_analysis_session()
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error loading Bronze STTM: {str(e)}")
            if st.button("🔄 Restart Workflow"):
                _reset_analysis_session()
                st.rerun()

    # ── Phase 3: Review Silver Layer STTM ────────────────────────────────────
    elif st.session_state.phase == "silver_sttm":
        st.header("🥈 Phase 3: Review Silver Layer STTM")
        st.info(
            "✨ **Silver Layer:** Data cleansing with deduplication, null handling, and standardization. "
            "Review the cleansing rules — these ensure data quality and consistency."
        )

        try:
            sttm_path = st.session_state.pipeline_state.get("sttm_silver_path")
            if not sttm_path:
                raise ValueError("No Silver STTM path found")

            sttm_df = pd.read_csv(sttm_path)

            if sttm_df.empty:
                raise pd.errors.EmptyDataError("STTM file is empty")

            st.metric("Total Cleansing Rules", len(sttm_df))

            # Prepare for editing
            editor_df = _prepare_sttm_editor_df(sttm_df)

            # Data editor
            edited_df = st.data_editor(
                editor_df,
                use_container_width=True,
                height=400,
                key="silver_sttm_editor",
            )

            # Approve button
            if st.button("✅ Approve & Continue", use_container_width=True, type="primary"):
                with st.spinner("Executing Silver layer..."):
                    try:
                        # Save selected rows
                        selected_df = _extract_selected_rows(edited_df)
                        selected_df.to_csv(sttm_path, index=False)

                        # Run Phase 3
                        st.session_state.pipeline_state["silver_sttm_approved"] = True
                        result_state = run_silver_to_gold_sttm(st.session_state.pipeline_state)

                        # Update session
                        st.session_state.pipeline_state = result_state
                        st.session_state.phase = "gold_sttm"

                        st.success("✅ Silver layer approved! Proceeding to Gold layer review.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error approving Silver STTM: {str(e)}")
                        logger = AuditLogger(st.session_state.get("current_run_id", ""))
                        logger.log("streamlit_app", "silver_sttm_approve_error", error=str(e))

        except pd.errors.EmptyDataError:
            st.error("❌ Silver STTM file is empty or corrupted. Starting over...")
            if st.button("🔄 Restart Workflow"):
                _reset_analysis_session()
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error loading Silver STTM: {str(e)}")
            if st.button("🔄 Restart Workflow"):
                _reset_analysis_session()
                st.rerun()

    # ── Phase 4: Review Gold Layer STTM ──────────────────────────────────────
    elif st.session_state.phase == "gold_sttm":
        st.header("🥇 Phase 4: Review Gold Layer STTM")
        st.info(
            "📊 **Gold Layer:** Analytics-ready data with joins, aggregations, and dimensions. "
            "Review the analytics rules — these transform clean data into business insights."
        )

        try:
            sttm_path = st.session_state.pipeline_state.get("sttm_gold_path")
            if not sttm_path:
                raise ValueError("No Gold STTM path found")

            sttm_df = pd.read_csv(sttm_path)

            if sttm_df.empty:
                raise pd.errors.EmptyDataError("STTM file is empty")

            st.metric("Total Analytics Rules", len(sttm_df))

            # Prepare for editing
            editor_df = _prepare_sttm_editor_df(sttm_df)

            # Data editor
            edited_df = st.data_editor(
                editor_df,
                use_container_width=True,
                height=400,
                key="gold_sttm_editor",
            )

            # Approve button
            if st.button("✅ Approve & Execute Final Phase", use_container_width=True, type="primary"):
                with st.spinner("Executing Gold layer and generating report..."):
                    try:
                        # Save selected rows
                        selected_df = _extract_selected_rows(edited_df)
                        selected_df.to_csv(sttm_path, index=False)

                        # Run Phase 4
                        st.session_state.pipeline_state["gold_sttm_approved"] = True
                        result_state = run_gold_and_report(st.session_state.pipeline_state)

                        # Update session
                        st.session_state.pipeline_state = result_state
                        st.session_state.report_complete = True
                        st.session_state.phase = "report"

                        st.success("✅ Gold layer approved! Report generated. View it below.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error approving Gold STTM: {str(e)}")
                        logger = AuditLogger(st.session_state.get("current_run_id", ""))
                        logger.log("streamlit_app", "gold_sttm_approve_error", error=str(e))

        except pd.errors.EmptyDataError:
            st.error("❌ Gold STTM file is empty or corrupted. Starting over...")
            if st.button("🔄 Restart Workflow"):
                _reset_analysis_session()
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error loading Gold STTM: {str(e)}")
            if st.button("🔄 Restart Workflow"):
                _reset_analysis_session()
                st.rerun()

    # ── Phase 5: Executive Report ────────────────────────────────────────────
    elif st.session_state.phase == "report":
        st.header("📊 Phase 5: Executive Report")
        st.session_state.report_complete = True

        report_path = st.session_state.pipeline_state.get("report_path")

        if report_path and Path(report_path).exists():
            try:
                # Read and display HTML report
                with open(report_path, "r", encoding="utf-8") as f:
                    report_html = f.read()

                st.components.v1.html(report_html, height=2000, scrolling=True)

                # Action buttons
                col1, col2 = st.columns(2)

                with col1:
                    # Download button
                    with open(report_path, "r", encoding="utf-8") as f:
                        report_content = f.read()

                    st.download_button(
                        label="📥 Download Report (HTML)",
                        data=report_content,
                        file_name=Path(report_path).name,
                        mime="text/html",
                        use_container_width=True,
                    )

                with col2:
                    # Restart button
                    if st.button("🔄 Start New Analysis", use_container_width=True):
                        _reset_analysis_session()
                        st.success("Session reset. Ready for a new analysis!")
                        st.rerun()

                # Summary metrics
                st.divider()
                st.subheader("📈 Pipeline Summary")

                summary_cols = st.columns(4)
                with summary_cols[0]:
                    st.metric("Run ID", st.session_state.pipeline_state.get("run_id", "N/A")[:12])
                with summary_cols[1]:
                    st.metric("Status", st.session_state.pipeline_state.get("status", "N/A"))
                with summary_cols[2]:
                    bronze_count = len(st.session_state.pipeline_state.get("bronze_output_paths", []))
                    st.metric("Bronze Files", bronze_count)
                with summary_cols[3]:
                    gold_count = len(st.session_state.pipeline_state.get("gold_output_paths", []))
                    st.metric("Gold Tables", gold_count)
                
                # Chat interface for follow-up questions
                st.divider()
                gold_files = st.session_state.pipeline_state.get("gold_output_paths", [])
                if gold_files:
                    # Use the first gold table for queries
                    gold_file = Path(gold_files[0])
                    run_id = st.session_state.pipeline_state.get("run_id", "")
                    render_chat_interface(gold_file, run_id)
                else:
                    st.info("💡 No Gold layer files available for queries.")

                # Data lineage visualization
                st.divider()
                st.subheader("📊 Data Lineage & Transformations")
                run_id = st.session_state.pipeline_state.get("run_id", "")
                if run_id:
                    render_lineage_dashboard(run_id)
                else:
                    st.info("💡 Lineage dashboard will be available after pipeline execution.")

            except Exception as e:
                st.error(f"❌ Error displaying report: {str(e)}")
                if st.button("🔄 Restart Workflow"):
                    _reset_analysis_session()
                    st.rerun()

        else:
            st.error(
                "❌ Report file not found. Please check the pipeline execution. "
                "Ensure all phases completed successfully."
            )
            if st.button("🔄 Restart Workflow"):
                _reset_analysis_session()
                st.rerun()


