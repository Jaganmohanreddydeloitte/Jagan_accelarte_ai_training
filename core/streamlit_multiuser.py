"""Streamlit session management for multi-user pipeline support."""

import streamlit as st
from typing import Optional, Dict, List
from pathlib import Path
import pandas as pd

from core.user_manager import get_user_manager, RunRecord
from core.audit import AuditLogger
from core.config import BASE_DIR


class StreamlitMultiUserSession:
    """Manage Streamlit session state for multi-user pipeline."""
    
    # Session state keys
    KEY_USERNAME = "username"
    KEY_IS_AUTHENTICATED = "is_authenticated"
    KEY_CURRENT_RUN_ID = "current_run_id"
    KEY_USER_PATHS = "user_paths"
    
    @staticmethod
    def initialize_session() -> None:
        """Initialize Streamlit session state."""
        if KEY_USERNAME not in st.session_state:
            st.session_state[StreamlitMultiUserSession.KEY_USERNAME] = None
        
        if StreamlitMultiUserSession.KEY_IS_AUTHENTICATED not in st.session_state:
            st.session_state[StreamlitMultiUserSession.KEY_IS_AUTHENTICATED] = False
        
        if StreamlitMultiUserSession.KEY_CURRENT_RUN_ID not in st.session_state:
            st.session_state[StreamlitMultiUserSession.KEY_CURRENT_RUN_ID] = None
        
        if StreamlitMultiUserSession.KEY_USER_PATHS not in st.session_state:
            st.session_state[StreamlitMultiUserSession.KEY_USER_PATHS] = {}
    
    @staticmethod
    def login(username: str) -> bool:
        """
        Authenticate user by username.
        
        Args:
            username: Username to authenticate
        
        Returns:
            True if authentication successful, False otherwise
        """
        manager = get_user_manager()
        
        # Register user (creates directories if new)
        if not manager.register_user(username):
            return False
        
        # Update session state
        st.session_state[StreamlitMultiUserSession.KEY_USERNAME] = username
        st.session_state[StreamlitMultiUserSession.KEY_IS_AUTHENTICATED] = True
        st.session_state[StreamlitMultiUserSession.KEY_USER_PATHS] = manager.get_paths_for_user(username)
        
        return True
    
    @staticmethod
    def logout() -> None:
        """Logout current user."""
        st.session_state[StreamlitMultiUserSession.KEY_USERNAME] = None
        st.session_state[StreamlitMultiUserSession.KEY_IS_AUTHENTICATED] = False
        st.session_state[StreamlitMultiUserSession.KEY_CURRENT_RUN_ID] = None
        st.session_state[StreamlitMultiUserSession.KEY_USER_PATHS] = {}
    
    @staticmethod
    def is_authenticated() -> bool:
        """Check if user is authenticated."""
        return st.session_state.get(StreamlitMultiUserSession.KEY_IS_AUTHENTICATED, False)
    
    @staticmethod
    def get_current_username() -> Optional[str]:
        """Get currently logged-in username."""
        if not StreamlitMultiUserSession.is_authenticated():
            return None
        return st.session_state.get(StreamlitMultiUserSession.KEY_USERNAME)
    
    @staticmethod
    def get_user_paths() -> Dict[str, Path]:
        """Get user's isolated paths."""
        return st.session_state.get(StreamlitMultiUserSession.KEY_USER_PATHS, {})
    
    @staticmethod
    def set_current_run(run_id: str) -> None:
        """Set current pipeline run ID."""
        st.session_state[StreamlitMultiUserSession.KEY_CURRENT_RUN_ID] = run_id
    
    @staticmethod
    def get_current_run() -> Optional[str]:
        """Get current pipeline run ID."""
        return st.session_state.get(StreamlitMultiUserSession.KEY_CURRENT_RUN_ID)
    
    @staticmethod
    def clear_current_run() -> None:
        """Clear current run ID (after completion)."""
        st.session_state[StreamlitMultiUserSession.KEY_CURRENT_RUN_ID] = None


def render_login_page() -> Optional[str]:
    """
    Render authentication/login page.
    
    Returns:
        Username if authenticated, None otherwise
    """
    st.set_page_config(page_title="IDAMP - Login", layout="centered")
    
    st.title("🏅 IDAMP - Multi-User Pipeline")
    st.markdown("**Intent-Driven Agentic Medallion Pipeline**")
    st.markdown("---")
    
    # Login form
    col1, col2 = st.columns([2, 1])
    
    with col1:
        username = st.text_input(
            "Username",
            placeholder="Enter username (3+ alphanumeric characters)",
            key="login_username",
        )
    
    with col2:
        login_button = st.button("Login", use_container_width=True)
    
    if login_button:
        if not username:
            st.error("❌ Please enter a username")
            return None
        
        if not StreamlitMultiUserSession.login(username):
            st.error("❌ Invalid username (must be 3+ alphanumeric characters)")
            return None
        
        st.success(f"✅ Welcome, {username}!")
        st.rerun()
    
    # Info section
    st.markdown("---")
    st.markdown("""
    ### 📋 About Multi-User Support
    
    - **Isolated Data**: Each user has their own data folders and reports
    - **Run History**: Track all your pipeline runs and their results
    - **Concurrent Use**: Multiple users can run pipelines simultaneously
    - **User Statistics**: View your quality scores and completion rates
    
    ### 🚀 Getting Started
    
    1. Enter your username (3+ characters, alphanumeric + underscore/dash)
    2. Click Login (new users automatically registered)
    3. Start uploading data and running the pipeline
    """)
    
    return None


def render_user_navbar() -> None:
    """Render user navigation bar."""
    username = StreamlitMultiUserSession.get_current_username()
    
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    
    with col1:
        st.markdown(f"### 👤 {username}")
    
    with col4:
        if st.button("Logout", key="logout_btn"):
            StreamlitMultiUserSession.logout()
            st.rerun()


def render_user_stats(username: str) -> None:
    """
    Render user statistics dashboard.
    
    Args:
        username: Username
    """
    manager = get_user_manager()
    stats = manager.get_user_stats(username)
    
    st.subheader("📊 Your Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Runs", stats["total_runs"])
    
    with col2:
        st.metric("Completed", stats["completed"])
    
    with col3:
        st.metric("Failed", stats["failed"])
    
    with col4:
        st.metric("Avg Quality", f"{stats['avg_quality_score']:.1f}/100")
    
    if stats["last_run"]:
        st.caption(f"Last run: {stats['last_run']}")


def render_run_history(username: str, limit: int = 10) -> None:
    """
    Render user's run history.
    
    Args:
        username: Username
        limit: Maximum number of runs to display
    """
    manager = get_user_manager()
    runs = manager.get_user_runs(username, limit=limit)
    
    if not runs:
        st.info("📭 No runs yet. Upload data to start a pipeline run!")
        return
    
    st.subheader("📜 Run History")
    
    # Convert to DataFrame for display
    run_data = []
    for run in runs:
        run_data.append({
            "Run ID": run.run_id,
            "Status": run.status,
            "Phase": run.phase,
            "Quality": f"{run.quality_score}/100" if run.quality_score else "N/A",
            "Started": run.started_at[:10],  # Just date
            "Completed": run.completed_at[:10] if run.completed_at else "-",
        })
    
    df_runs = pd.DataFrame(run_data)
    
    # Color status
    def color_status(val):
        if val == "completed":
            return "background-color: #d4edda"
        elif val == "failed":
            return "background-color: #f8d7da"
        elif val == "running":
            return "background-color: #e2e3e5"
        return ""
    
    styled_df = df_runs.style.applymap(
        color_status,
        subset=["Status"],
    )
    
    st.dataframe(styled_df, use_container_width=True)
    
    # Show detailed view on click
    with st.expander("📋 View Details"):
        selected_run_id = st.selectbox(
            "Select run to view details",
            [r.run_id for r in runs],
            key="run_detail_select",
        )
        
        run = manager.get_user_run(username, selected_run_id)
        if run:
            st.json(run.to_dict())


def render_phase_with_quality_gate(
    phase_name: str,
    phase_number: int,
    quality_score: Optional[float] = None,
    min_quality: float = 80.0,
) -> bool:
    """
    Render a pipeline phase with quality gate.
    
    Args:
        phase_name: Name of phase (Bronze, Silver, Gold)
        phase_number: Phase number (1-4)
        quality_score: Quality score from data quality check
        min_quality: Minimum acceptable quality score
    
    Returns:
        True if passed gate, False if failed
    """
    st.markdown(f"### Phase {phase_number}: {phase_name}")
    
    if quality_score is None:
        st.info(f"⏳ Processing {phase_name}...")
        return True
    
    # Display quality result
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        st.metric("Quality Score", f"{quality_score:.0f}/100")
    
    with col2:
        threshold_met = quality_score >= min_quality
        status = "✅ PASSED" if threshold_met else "❌ FAILED"
        st.markdown(f"**{status}**")
    
    with col3:
        st.caption(f"Required: {min_quality}/100")
    
    if quality_score < min_quality:
        st.error(
            f"❌ Quality gate failed: {quality_score:.0f}/100 < {min_quality}/100\n\n"
            f"Pipeline stopped. Review data quality issues above."
        )
        return False
    
    st.success(f"✅ Quality gate passed: {quality_score:.0f}/100 ≥ {min_quality}/100")
    return True


def require_authentication() -> Optional[str]:
    """
    Require user to be authenticated before showing main content.
    
    Returns:
        Username if authenticated, None otherwise
    """
    StreamlitMultiUserSession.initialize_session()
    
    if not StreamlitMultiUserSession.is_authenticated():
        render_login_page()
        st.stop()
    
    return StreamlitMultiUserSession.get_current_username()


# Export main functions
__all__ = [
    "StreamlitMultiUserSession",
    "render_login_page",
    "render_user_navbar",
    "render_user_stats",
    "render_run_history",
    "render_phase_with_quality_gate",
    "require_authentication",
]
