"""
Pipeline Error Recovery UI

Streamlit components for displaying errors and managing retries:
- Error message display with context
- Retry interface
- Recovery options
- Error history viewer
"""

import streamlit as st
from typing import Optional, Callable, Any, Dict, List
from pathlib import Path
import pandas as pd
from datetime import datetime

from core.error_handling import (
    PipelineException,
    ErrorContext,
    ErrorLogger,
    RecoveryState,
    RetryPolicy,
)


class PipelineErrorUI:
    """Streamlit UI for error handling and recovery"""

    # Session state keys
    KEY_CURRENT_ERROR = "current_error"
    KEY_ERROR_HISTORY = "error_history"
    KEY_RECOVERY_STATE = "recovery_state"
    KEY_RETRY_POLICY = "retry_policy"

    @staticmethod
    def initialize_session(
        error_log_dir: Path = None,
        recovery_dir: Path = None,
        retry_policy: RetryPolicy = None,
    ) -> None:
        """Initialize error handling session state"""
        if PipelineErrorUI.KEY_ERROR_HISTORY not in st.session_state:
            st.session_state[PipelineErrorUI.KEY_ERROR_HISTORY] = []
        
        if PipelineErrorUI.KEY_RECOVERY_STATE not in st.session_state:
            st.session_state[PipelineErrorUI.KEY_RECOVERY_STATE] = {}
        
        if PipelineErrorUI.KEY_RETRY_POLICY not in st.session_state:
            st.session_state[PipelineErrorUI.KEY_RETRY_POLICY] = retry_policy or RetryPolicy()

    @staticmethod
    def render_error_display(error_context: ErrorContext) -> None:
        """Display error with detailed information"""
        error = error_context.error

        # Error header with severity
        severity_colors = {
            "critical": "🔴",
            "error": "🟠",
            "warning": "🟡",
            "info": "⚪",
        }
        severity_emoji = severity_colors.get(error.severity.value, "❓")

        st.error(
            f"{severity_emoji} **{error.category.value.upper()}**: {error.get_user_message()}"
        )

        # Detailed information
        with st.expander("📋 Error Details", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Location:**")
                st.code(f"Phase: {error_context.phase or 'N/A'}\nStep: {error_context.step or 'N/A'}")

                st.markdown("**Category & Severity:**")
                st.code(f"Category: {error.category.value}\nSeverity: {error.severity.value}")

            with col2:
                st.markdown("**Time & Run:**")
                st.code(f"Timestamp: {error.timestamp}\nRun ID: {error_context.run_id}")

                st.markdown("**Attempt:**")
                st.code(f"Attempt {error_context.attempt_number}/{error_context.max_attempts}")

        # Context information
        if error.context:
            with st.expander("🔍 Error Context"):
                for key, value in error.context.items():
                    st.markdown(f"**{key}:** `{value}`")

        # Root cause (if available)
        if error.cause:
            with st.expander("🌳 Root Cause"):
                st.code(str(error.cause), language="")

        # Stack trace
        with st.expander("📜 Stack Trace"):
            st.code(error.traceback, language="python")

        # Recovery suggestion
        suggestion = error.get_recovery_suggestion()
        if suggestion:
            st.info(f"💡 **Recovery Suggestion:** {suggestion}")

    @staticmethod
    def render_retry_interface(
        error_context: ErrorContext,
        on_retry: Callable[[], Any],
    ) -> bool:
        """Display retry interface and handle retry button"""
        if not error_context.can_retry:
            st.warning("⚠️ This error cannot be retried automatically")
            return False

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button(
                "🔄 Retry Operation",
                key=f"retry_{error_context.run_id}",
                use_container_width=True,
            ):
                st.info(f"Retrying (Attempt {error_context.attempt_number + 1}/{error_context.max_attempts})...")
                try:
                    result = on_retry()
                    st.success("✅ Retry successful! Continuing pipeline...")
                    return True
                except Exception as e:
                    st.error(f"Retry failed: {e}")
                    return False

        with col2:
            if st.button(
                "⏭️ Skip & Continue",
                key=f"skip_{error_context.run_id}",
                use_container_width=True,
            ):
                st.warning("⚠️ Skipping this step. Some data may not be processed.")
                return True

        with col3:
            if st.button(
                "🛑 Abort Pipeline",
                key=f"abort_{error_context.run_id}",
                use_container_width=True,
            ):
                st.error("Pipeline aborted by user")
                return False

        return False

    @staticmethod
    def render_recovery_options(error_context: ErrorContext) -> Optional[str]:
        """Display recovery options for user to choose"""
        st.subheader("🔧 Recovery Options")

        options = {
            "retry": "🔄 Retry the failed operation",
            "skip": "⏭️ Skip this step and continue",
            "modify": "✏️ Modify input and retry",
            "abort": "🛑 Abort and start over",
        }

        if not error_context.can_retry:
            # Remove retry option if not retryable
            options.pop("retry", None)
            options.pop("modify", None)

        choice = st.radio("What would you like to do?", options=list(options.keys()))

        if choice:
            if choice == "retry":
                st.info("Preparing to retry operation...")
                return "retry"

            elif choice == "skip":
                st.warning("⚠️ You chose to skip this step. Some data may not be processed.")
                return "skip"

            elif choice == "modify":
                st.markdown("---")
                st.markdown("#### Modify Input Data")

                if error_context.input_data:
                    new_input = st.text_area(
                        "Edit input (JSON format)",
                        value=str(error_context.input_data),
                        height=200,
                    )
                    if st.button("✓ Save and Retry"):
                        return "modify_and_retry"
                else:
                    st.info("No input data available to modify")

            elif choice == "abort":
                if st.button("⚠️ Confirm Abort"):
                    return "abort"

        return None

    @staticmethod
    def render_error_history(
        error_history: List[ErrorContext],
        run_id: Optional[str] = None,
    ) -> None:
        """Display history of errors"""
        st.subheader(f"📜 Error History ({len(error_history)} errors)")

        if not error_history:
            st.info("No errors recorded")
            return

        # Filter by run_id if provided
        if run_id:
            error_history = [e for e in error_history if e.run_id == run_id]

        if not error_history:
            st.info(f"No errors for run {run_id}")
            return

        # Display as table
        df_errors = pd.DataFrame([
            {
                "Timestamp": e.created_at,
                "Phase": e.phase or "N/A",
                "Step": e.step or "N/A",
                "Category": e.error.category.value,
                "Severity": e.error.severity.value,
                "Message": e.error.message[:50] + "..." if len(e.error.message) > 50 else e.error.message,
                "Retries": f"{e.attempt_number}/{e.max_attempts}",
            }
            for e in error_history
        ])

        st.dataframe(df_errors, use_container_width=True, hide_index=True)

        # Detailed view
        st.markdown("---")
        st.subheader("📋 Error Details")

        selected_idx = st.selectbox(
            "Select error to view details",
            options=range(len(error_history)),
            format_func=lambda i: f"{error_history[i].error.category.value} - {error_history[i].error.message[:40]}",
        )

        if selected_idx is not None:
            PipelineErrorUI.render_error_display(error_history[selected_idx])

    @staticmethod
    def render_recovery_state_viewer(
        recovery_state_dir: Path = None,
    ) -> None:
        """Display recovery state information"""
        if recovery_state_dir is None:
            recovery_state_dir = Path("recovery_state")

        st.subheader("💾 Recovery State")

        recovery = RecoveryState(recovery_state_dir)

        # List available recovery states
        state_files = list(recovery_state_dir.glob("*_state.json"))

        if not state_files:
            st.info("No recovery states available")
            return

        st.markdown(f"**Available States:** {len(state_files)}")

        for state_file in sorted(state_files, reverse=True)[:10]:  # Show last 10
            with st.expander(f"📁 {state_file.name}"):
                try:
                    state_data = recovery.load_state(
                        run_id=state_file.stem.split("_")[0],
                        phase=state_file.stem.split("_")[1],
                    )
                    
                    if state_data:
                        st.json(state_data)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(
                                "Load State",
                                key=f"load_{state_file.stem}",
                            ):
                                st.session_state[PipelineErrorUI.KEY_RECOVERY_STATE] = state_data
                                st.success("State loaded into session")

                except Exception as e:
                    st.error(f"Error loading state: {e}")

    @staticmethod
    def handle_error(
        error: Exception,
        run_id: str,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        username: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        error_logger: Optional[ErrorLogger] = None,
    ) -> ErrorContext:
        """Handle an error: log it, display it, and set up for recovery"""
        
        # Convert to PipelineException if needed
        if not isinstance(error, PipelineException):
            error = PipelineException(
                message=str(error),
                cause=error,
            )

        # Update error with location info
        if phase:
            error.phase = phase
        if step:
            error.step = step

        # Create error context
        error_context = ErrorContext(
            error=error,
            run_id=run_id,
            username=username,
            phase=phase,
            step=step,
            input_data=input_data,
        )

        # Log error if logger provided
        if error_logger:
            error_logger.log_error(error_context)

        # Add to history
        if PipelineErrorUI.KEY_ERROR_HISTORY in st.session_state:
            st.session_state[PipelineErrorUI.KEY_ERROR_HISTORY].append(error_context)

        # Display error
        PipelineErrorUI.render_error_display(error_context)

        return error_context

    @staticmethod
    def wrap_with_error_handling(
        func: Callable,
        run_id: str,
        phase: str,
        step: str,
        error_logger: Optional[ErrorLogger] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> Callable:
        """Wrapper to add error handling to a function"""
        
        retry_policy = retry_policy or RetryPolicy()
        
        def wrapper(*args, **kwargs):
            attempt = 1
            last_error = None

            while attempt <= retry_policy.max_retries + 1:
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_error = e
                    
                    if not isinstance(e, PipelineException):
                        e = PipelineException(
                            message=str(e),
                            phase=phase,
                            step=step,
                            cause=e,
                        )
                    else:
                        if not e.phase:
                            e.phase = phase
                        if not e.step:
                            e.step = step

                    # Create error context
                    error_context = ErrorContext(
                        error=e,
                        run_id=run_id,
                        phase=phase,
                        step=step,
                        attempt_number=attempt,
                        max_attempts=retry_policy.max_retries + 1,
                        can_retry=retry_policy.is_retryable(e) if isinstance(e, PipelineException) else False,
                    )

                    # Log error
                    if error_logger:
                        error_logger.log_error(error_context)

                    # Display error
                    PipelineErrorUI.render_error_display(error_context)

                    # Check if retryable
                    if not error_context.can_retry or attempt >= retry_policy.max_retries + 1:
                        raise e

                    # Show retry interface
                    st.markdown("---")
                    if PipelineErrorUI.render_retry_interface(error_context, lambda: func(*args, **kwargs)):
                        return  # Successful retry

                    attempt += 1

            raise last_error if last_error else Exception("Unknown error")

        return wrapper

    @staticmethod
    def render_full_error_recovery(
        run_id: str,
        phase: Optional[str] = None,
        error_logger: Optional[ErrorLogger] = None,
        recovery_dir: Path = None,
    ) -> None:
        """Render complete error recovery interface"""
        st.title("🚨 Pipeline Error Recovery")

        # Tabs
        tab1, tab2, tab3 = st.tabs(["Current Error", "Error History", "Recovery State"])

        with tab1:
            st.markdown("### Current Error")
            
            error_history = st.session_state.get(PipelineErrorUI.KEY_ERROR_HISTORY, [])
            
            if error_history:
                current_error = error_history[-1]
                PipelineErrorUI.render_error_display(current_error)
                
                st.markdown("---")
                st.markdown("### Recovery Options")
                PipelineErrorUI.render_recovery_options(current_error)
            else:
                st.info("No errors to display")

        with tab2:
            error_history = st.session_state.get(PipelineErrorUI.KEY_ERROR_HISTORY, [])
            PipelineErrorUI.render_error_history(error_history, run_id=run_id)

        with tab3:
            PipelineErrorUI.render_recovery_state_viewer(recovery_dir)
