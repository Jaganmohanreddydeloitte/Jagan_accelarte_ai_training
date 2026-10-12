"""
Admin Dashboard UI Components for Streamlit

Complete admin interface with metrics, charts, and controls.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Any

from core.admin_auth import AdminAuthenticator, init_session_auth, show_logout_button
from core.admin_metrics import get_system_monitor, get_pipeline_metrics


def render_system_health_dashboard():
    """Display system health status and metrics"""
    st.markdown("## 🏥 System Health")

    monitor = get_system_monitor()
    health = monitor.get_health_status()

    # Status indicator
    col1, col2, col3, col4 = st.columns(4)

    metrics = health["metrics"]

    with col1:
        st.metric("CPU Usage", f"{metrics['cpu_percent']:.1f}%", delta="-2%")

    with col2:
        st.metric("Memory Usage", f"{metrics['memory_percent']:.1f}%", delta="-1%")

    with col3:
        st.metric("Disk Usage", f"{metrics['disk_percent']:.1f}%", delta="0%")

    with col4:
        status = health["status"]
        status_emoji = "🟢" if status == "HEALTHY" else "🟡" if status == "WARNING" else "🔴"
        st.metric("Overall Status", status_emoji + " " + status)

    # Issues
    if health["issues"]:
        st.warning("⚠️ Issues Detected:\n" + "\n".join(f"• {issue}" for issue in health["issues"]))

    # Detailed metrics
    st.markdown("### Detailed Metrics")

    detail_col1, detail_col2 = st.columns(2)

    with detail_col1:
        st.markdown("**Memory**")
        st.markdown(f"- Available: {metrics['memory_available_mb']} MB")
        st.markdown(f"- Usage: {metrics['memory_percent']:.1f}%")

    with detail_col2:
        st.markdown("**Disk**")
        st.markdown(f"- Free Space: {metrics['disk_free_gb']:.1f} GB")
        st.markdown(f"- Usage: {metrics['disk_percent']:.1f}%")

    # Trends
    st.markdown("### CPU Trend (Last 5 minutes)")

    cpu_trend = monitor.get_cpu_trend(5)
    mem_trend = monitor.get_memory_trend(5)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        y=cpu_trend,
        name="CPU %",
        mode="lines+markers",
        line=dict(color="blue")
    ))

    fig.add_trace(go.Scatter(
        y=mem_trend,
        name="Memory %",
        mode="lines+markers",
        line=dict(color="orange")
    ))

    fig.update_layout(
        title="CPU and Memory Trend",
        yaxis_title="Percentage (%)",
        xaxis_title="Time (minutes ago)",
        hovermode="x unified",
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def render_pipeline_runs_dashboard():
    """Display pipeline run statistics"""
    st.markdown("## 📊 Pipeline Runs")

    metrics = get_pipeline_metrics()
    summary = metrics.get_pipeline_run_summary()

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Runs", summary["total_runs"])

    with col2:
        st.metric("Successful", summary["successful"])

    with col3:
        st.metric("Failed", summary["failed"])

    with col4:
        success_rate = summary["success_rate"]
        st.metric("Success Rate", f"{success_rate:.1f}%", delta=f"{success_rate - 95:.1f}%")

    # Agent performance
    if summary["agents"]:
        st.markdown("### Agent Performance")

        agent_stats = summary["agents"]

        # Create table
        agent_data = []
        for agent_name, stats in agent_stats.items():
            agent_data.append({
                "Agent": agent_name,
                "Runs": stats["total_runs"],
                "Success": stats["successful"],
                "Failed": stats["failed"],
                "Success Rate": f"{100 - stats['error_rate']:.1f}%",
                "Avg Duration": f"{stats['avg_duration']:.1f}s",
                "API Calls": stats["total_api_calls"],
            })

        st.dataframe(agent_data, use_container_width=True)

        # Agent performance chart
        st.markdown("### Agent Comparison")

        agent_names = list(agent_stats.keys())
        success_rates = [100 - agent_stats[name]["error_rate"] for name in agent_names]

        fig = px.bar(
            x=agent_names,
            y=success_rates,
            title="Agent Success Rate Comparison",
            labels={"x": "Agent", "y": "Success Rate (%)"},
            color=success_rates,
            color_continuous_scale="RdYlGn"
        )

        st.plotly_chart(fig, use_container_width=True)


def render_error_analysis_dashboard():
    """Display error analysis and common failures"""
    st.markdown("## 🐛 Error Analysis")

    metrics = get_pipeline_metrics()
    error_summary = metrics.get_error_summary()
    recent_failures = metrics.get_recent_failures(10)

    # Error distribution
    if error_summary:
        st.markdown("### Error Distribution")

        error_names = list(error_summary.keys())
        error_counts = list(error_summary.values())

        fig = px.pie(
            values=error_counts,
            names=error_names,
            title="Top Errors"
        )

        st.plotly_chart(fig, use_container_width=True)

        # Error table
        st.markdown("### Error Counts")

        error_data = [
            {"Error Type": name, "Count": count}
            for name, count in sorted(error_summary.items(), key=lambda x: x[1], reverse=True)
        ]

        st.dataframe(error_data, use_container_width=True)

    else:
        st.info("No errors recorded")

    # Recent failures
    if recent_failures:
        st.markdown("### Recent Failures")

        for i, failure in enumerate(recent_failures[:5], 1):
            with st.expander(
                f"❌ {failure['agent_name']} - {failure['timestamp'][:10]}"
            ):
                st.markdown(f"**Agent:** {failure['agent_name']}")
                st.markdown(f"**Run ID:** {failure['run_id']}")
                st.markdown(f"**Duration:** {failure['duration_seconds']:.1f}s")
                st.markdown(f"**Error:** {failure.get('error_message', 'Unknown error')}")

    else:
        st.success("No recent failures!")


def render_performance_metrics_dashboard():
    """Display agent performance metrics"""
    st.markdown("## ⚡ Performance Metrics")

    metrics = get_pipeline_metrics()
    summary = metrics.get_pipeline_run_summary()

    # Duration analysis
    st.markdown("### Run Duration Analysis")

    col1, col2, col3 = st.columns(3)

    with col1:
        avg_duration = summary["avg_run_duration"]
        st.metric("Average Run Duration", f"{avg_duration:.1f}s")

    with col2:
        total_duration = summary["total_duration_hours"]
        st.metric("Total Time", f"{total_duration:.1f}h")

    with col3:
        api_calls = summary["total_api_calls"]
        st.metric("Total API Calls", f"{api_calls:,}")

    # API efficiency
    if summary["total_runs"] > 0:
        st.markdown("### API Efficiency")

        api_per_run = summary["total_api_calls"] / summary["total_runs"]
        st.metric("API Calls per Run", f"{api_per_run:.1f}")

    # Agent duration comparison
    if summary["agents"]:
        st.markdown("### Agent Duration Comparison")

        agent_names = list(summary["agents"].keys())
        agent_durations = [summary["agents"][name]["avg_duration"] for name in agent_names]

        fig = px.bar(
            x=agent_names,
            y=agent_durations,
            title="Average Duration by Agent",
            labels={"x": "Agent", "y": "Duration (seconds)"}
        )

        st.plotly_chart(fig, use_container_width=True)


def render_admin_dashboard():
    """Complete admin dashboard"""
    st.set_page_config(page_title="Admin Dashboard", layout="wide")

    # Sidebar authentication
    authenticator = AdminAuthenticator()

    if not init_session_auth(authenticator):
        st.error("Please login to access admin dashboard")
        st.stop()

    # Show logout button
    show_logout_button()

    # Page title
    st.markdown("# 📊 Admin Dashboard")

    username = st.session_state.get("admin_username", "Admin")
    st.markdown(f"Welcome, **{username}**! Here's your system overview.")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["System Health", "Pipeline Runs", "Performance", "Error Analysis", "Settings"]
    )

    with tab1:
        render_system_health_dashboard()

    with tab2:
        render_pipeline_runs_dashboard()

    with tab3:
        render_performance_metrics_dashboard()

    with tab4:
        render_error_analysis_dashboard()

    with tab5:
        render_admin_settings()


def render_admin_settings():
    """Admin settings and management"""
    st.markdown("### ⚙️ Admin Settings")

    authenticator = AdminAuthenticator()

    # Change password section
    with st.expander("🔐 Change Password"):
        username = st.session_state.get("admin_username")

        current_password = st.text_input("Current Password", type="password", key="current_pwd")
        new_password = st.text_input("New Password", type="password", key="new_pwd")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_pwd")

        if st.button("Update Password"):
            if new_password != confirm_password:
                st.error("Passwords don't match")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters")
            else:
                success = authenticator.change_password(username, current_password, new_password)

                if success:
                    st.success("✓ Password updated!")
                else:
                    st.error("❌ Current password is incorrect")

    # Add new admin (only for main admin)
    if st.session_state.get("admin_username") == "admin":
        with st.expander("👤 Add New Admin"):
            new_username = st.text_input("New Username", key="new_admin_username")
            new_password = st.text_input("New Password", type="password", key="new_admin_password")
            full_name = st.text_input("Full Name", key="new_admin_name")

            if st.button("Create Admin"):
                if not new_username or not new_password:
                    st.error("Username and password required")
                elif not new_username.isalnum():
                    st.error("Username must be alphanumeric")
                else:
                    success = authenticator.add_admin(new_username, new_password, full_name)

                    if success:
                        st.success(f"✓ Admin '{new_username}' created!")
                    else:
                        st.error(f"❌ Admin '{new_username}' already exists")

    # Dashboard information
    st.markdown("### ℹ️ Dashboard Information")

    st.markdown("""
    **System Health Tab:**
    - Monitors CPU, memory, and disk usage
    - Shows overall system status
    - Displays trends and alerts
    
    **Pipeline Runs Tab:**
    - Total runs and success rate
    - Per-agent performance metrics
    - Comparison charts
    
    **Performance Tab:**
    - Run duration analysis
    - API efficiency metrics
    - Agent comparison
    
    **Error Analysis Tab:**
    - Error distribution
    - Recent failures with details
    - Error trend analysis
    """)


def render_mini_dashboard():
    """Compact dashboard for sidebar or status page"""
    monitor = get_system_monitor()
    metrics = get_pipeline_metrics()

    health = monitor.get_health_status()
    summary = metrics.get_pipeline_run_summary()

    st.markdown("### 📊 Quick Stats")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Pipeline Runs", summary["total_runs"])
        st.metric("Success Rate", f"{summary['success_rate']:.0f}%")

    with col2:
        metrics_data = health["metrics"]
        st.metric("CPU", f"{metrics_data['cpu_percent']:.0f}%")
        st.metric("Memory", f"{metrics_data['memory_percent']:.0f}%")
