"""
Streamlit UI components for displaying performance metrics.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.performance_monitoring import (
    PerformanceMetrics,
    PerformanceAnalyzer,
    CostEstimator,
)


class PerformanceUI:
    """Streamlit UI for performance monitoring."""
    
    KEY_CURRENT_METRICS = "perf_current_metrics"
    KEY_SAVED_METRICS = "perf_saved_metrics"
    
    @staticmethod
    def initialize_session() -> None:
        """Initialize session state for performance tracking."""
        if PerformanceUI.KEY_CURRENT_METRICS not in st.session_state:
            st.session_state[PerformanceUI.KEY_CURRENT_METRICS] = None
        
        if PerformanceUI.KEY_SAVED_METRICS not in st.session_state:
            st.session_state[PerformanceUI.KEY_SAVED_METRICS] = []
    
    @staticmethod
    def set_current_metrics(metrics: PerformanceMetrics) -> None:
        """Store current metrics in session."""
        st.session_state[PerformanceUI.KEY_CURRENT_METRICS] = metrics
    
    @staticmethod
    def get_current_metrics() -> Optional[PerformanceMetrics]:
        """Retrieve current metrics from session."""
        return st.session_state.get(PerformanceUI.KEY_CURRENT_METRICS)
    
    @staticmethod
    def render_summary_metrics(metrics: PerformanceMetrics) -> None:
        """Display summary statistics."""
        analyzer = PerformanceAnalyzer()
        summary = analyzer.get_api_call_summary(metrics.api_calls)
        total_cost = CostEstimator.estimate_total_cost(metrics.api_calls)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            duration = metrics.duration_seconds or 0
            st.metric(
                "⏱️ Total Duration",
                f"{duration:.1f}s",
            )
        
        with col2:
            st.metric(
                "📞 API Calls",
                summary["total_calls"],
            )
        
        with col3:
            tokens = summary.get("total_tokens", 0)
            st.metric(
                "🔤 Total Tokens",
                f"{summary.get('total_tokens', 0):,}",
            )
        
        with col4:
            st.metric(
                "💾 Peak Memory",
                _format_memory(max(
                    (m.peak_memory_mb for m in metrics.memory_samples),
                    default=0,
                )),
            )
        
        with col5:
            st.metric(
                "💰 Estimated Cost",
                f"${total_cost:.4f}",
            )
    
    @staticmethod
    def render_execution_timeline(metrics: PerformanceMetrics) -> None:
        """Display execution timeline of operations."""
        st.subheader("⏳ Execution Timeline")
        
        if not metrics.timings:
            st.info("No timing data available")
            return
        
        # Group by agent
        timeline_data = []
        for timing in metrics.timings:
            timeline_data.append({
                "Agent": timing.agent,
                "Phase": timing.phase,
                "Operation": timing.operation,
                "Duration (s)": timing.duration_seconds,
                "Status": timing.status,
            })
        
        df = pd.DataFrame(timeline_data)
        
        # Create Gantt-style visualization
        fig = go.Figure()
        
        agents = df["Agent"].unique()
        colors = {
            "success": "#00D084",
            "failed": "#FF4B4B",
            "skipped": "#FFB703",
        }
        
        for agent in agents:
            agent_data = df[df["Agent"] == agent]
            
            cumulative_time = 0
            for idx, row in agent_data.iterrows():
                color = colors.get(row["Status"], "#636EFA")
                
                fig.add_trace(go.Bar(
                    x=[row["Duration (s)"]],
                    y=[agent],
                    orientation="h",
                    name=f"{row['Operation']} ({row['Status']})",
                    marker=dict(color=color),
                    hovertemplate=(
                        f"<b>{row['Operation']}</b><br>"
                        f"Duration: {row['Duration (s)']:.2f}s<br>"
                        f"Status: {row['Status']}<br>"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                ))
        
        fig.update_layout(
            barmode="stack",
            height=300,
            title="Agent Execution Timeline",
            xaxis_title="Duration (seconds)",
            yaxis_title="Agent",
            hovermode="y unified",
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def render_agent_breakdown(metrics: PerformanceMetrics) -> None:
        """Display performance breakdown by agent."""
        st.subheader("📊 Performance by Agent")
        
        analyzer = PerformanceAnalyzer()
        breakdown = analyzer.get_agent_breakdown(metrics)
        
        if not breakdown:
            st.info("No agent data available")
            return
        
        # Create data for table
        agent_data = []
        for agent, data in breakdown.items():
            avg_op_time = data["total_time"] / data["operations"] if data["operations"] > 0 else 0
            
            agent_data.append({
                "Agent": agent,
                "Total Time (s)": f"{data['total_time']:.2f}",
                "Operations": data["operations"],
                "Avg Time/Op (s)": f"{avg_op_time:.2f}",
                "Phases": ", ".join(data["phases"].keys()),
            })
        
        df = pd.DataFrame(agent_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Chart
        chart_data = pd.DataFrame([
            {"Agent": agent, "Time (s)": data["total_time"]}
            for agent, data in breakdown.items()
        ])
        
        fig = go.Figure(data=[
            go.Bar(
                x=chart_data["Agent"],
                y=chart_data["Time (s)"],
                marker_color="#1f77b4",
            )
        ])
        fig.update_layout(
            title="Total Time by Agent",
            xaxis_title="Agent",
            yaxis_title="Time (seconds)",
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def render_slowest_operations(metrics: PerformanceMetrics, limit: int = 10) -> None:
        """Display slowest operations."""
        st.subheader("🐌 Slowest Operations")
        
        analyzer = PerformanceAnalyzer()
        slowest = analyzer.get_slowest_operations(metrics, limit=limit)
        
        if not slowest:
            st.info("No operation data available")
            return
        
        df = pd.DataFrame(slowest)
        
        # Color code by duration
        def _color_duration(val):
            if val > 30:
                return "🔴"  # > 30s
            elif val > 10:
                return "🟠"  # > 10s
            elif val > 5:
                return "🟡"  # > 5s
            else:
                return "🟢"  # < 5s
        
        df["⏱️"] = df["duration_seconds"].apply(_color_duration)
        
        st.dataframe(
            df[["⏱️", "agent", "phase", "operation", "duration_seconds", "status"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "agent": "Agent",
                "phase": "Phase",
                "operation": "Operation",
                "duration_seconds": st.column_config.NumberColumn(
                    "Duration (s)",
                    format="%.2f",
                ),
                "status": "Status",
            },
        )
    
    @staticmethod
    def render_memory_usage(metrics: PerformanceMetrics) -> None:
        """Display memory usage over time."""
        st.subheader("🧠 Memory Usage")
        
        if not metrics.memory_samples:
            st.info("No memory data available")
            return
        
        # Prepare data
        memory_data = []
        for sample in metrics.memory_samples:
            memory_data.append({
                "Agent": sample.agent,
                "Timestamp": sample.timestamp,
                "Process Memory (MB)": sample.process_memory_mb,
                "Peak Memory (MB)": sample.peak_memory_mb,
                "Available (MB)": sample.available_system_mb,
            })
        
        df = pd.DataFrame(memory_data)
        
        # Display stats
        col1, col2, col3 = st.columns(3)
        
        with col1:
            peak = df["Peak Memory (MB)"].max()
            st.metric("📈 Peak Memory", _format_memory(peak))
        
        with col2:
            avg_available = df["Available (MB)"].mean()
            st.metric("💿 Avg Available", _format_memory(avg_available))
        
        with col3:
            max_used_pct = (
                (df["Process Memory (MB)"] / df["Available (MB)"] * 100).max()
            )
            st.metric("% Used", f"{max_used_pct:.1f}%")
        
        # Chart
        fig = go.Figure()
        
        agents = df["Agent"].unique()
        for agent in agents:
            agent_df = df[df["Agent"] == agent]
            fig.add_trace(go.Scatter(
                x=range(len(agent_df)),
                y=agent_df["Process Memory (MB)"],
                mode="lines+markers",
                name=agent,
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "Memory: %{y:.1f} MB<br>"
                    "<extra></extra>"
                ),
            ))
        
        fig.update_layout(
            title="Process Memory Over Time",
            xaxis_title="Sample Number",
            yaxis_title="Memory (MB)",
            height=350,
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def render_api_calls_summary(metrics: PerformanceMetrics) -> None:
        """Display API call statistics."""
        st.subheader("📞 API Calls")
        
        if not metrics.api_calls:
            st.info("No API call data available")
            return
        
        analyzer = PerformanceAnalyzer()
        summary = analyzer.get_api_call_summary(metrics.api_calls)
        cost_breakdown = analyzer.estimate_cost_breakdown(metrics.api_calls)
        
        # Tabs
        tab1, tab2, tab3 = st.tabs(["By Provider", "By Model", "Tokens & Cost"])
        
        # By Provider
        with tab1:
            if summary["by_provider"]:
                provider_data = []
                for provider, data in summary["by_provider"].items():
                    provider_data.append({
                        "Provider": provider.upper(),
                        "Calls": data["count"],
                        "Input Tokens": f"{data['input_tokens']:,}",
                        "Output Tokens": f"{data['output_tokens']:,}",
                        "Cost": f"${cost_breakdown.get(provider, 0):.4f}",
                    })
                
                df = pd.DataFrame(provider_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Chart
                chart_data = pd.DataFrame([
                    {"Provider": p.upper(), "Calls": d["count"]}
                    for p, d in summary["by_provider"].items()
                ])
                
                fig = go.Figure(data=[
                    go.Pie(
                        labels=chart_data["Provider"],
                        values=chart_data["Calls"],
                        hole=0.4,
                    )
                ])
                fig.update_layout(title="API Calls by Provider", height=350)
                st.plotly_chart(fig, use_container_width=True)
        
        # By Model
        with tab2:
            if summary["by_model"]:
                model_data = []
                for model, data in summary["by_model"].items():
                    model_data.append({
                        "Model": model,
                        "Calls": data["count"],
                        "Input Tokens": f"{data['input_tokens']:,}",
                        "Output Tokens": f"{data['output_tokens']:,}",
                    })
                
                df = pd.DataFrame(model_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Tokens & Cost
        with tab3:
            total_input = sum(
                c.input_tokens for c in metrics.api_calls
                if not c.error
            )
            total_output = sum(
                c.output_tokens for c in metrics.api_calls
                if not c.error
            )
            total_cost = CostEstimator.estimate_total_cost(metrics.api_calls)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("🔤 Input Tokens", f"{total_input:,}")
            
            with col2:
                st.metric("🔤 Output Tokens", f"{total_output:,}")
            
            with col3:
                st.metric("💰 Total Cost", f"${total_cost:.4f}")
            
            # Cost breakdown
            if cost_breakdown:
                cost_data = pd.DataFrame([
                    {"Provider": p.upper(), "Cost (USD)": cost}
                    for p, cost in cost_breakdown.items()
                ])
                
                fig = go.Figure(data=[
                    go.Bar(
                        x=cost_data["Provider"],
                        y=cost_data["Cost (USD)"],
                        marker_color="#FF6B6B",
                    )
                ])
                fig.update_layout(
                    title="Cost by Provider",
                    xaxis_title="Provider",
                    yaxis_title="Cost (USD)",
                    height=350,
                )
                st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def render_full_performance_report(metrics: PerformanceMetrics) -> None:
        """Display complete performance report."""
        st.markdown("# 📊 Performance Report")
        
        # Summary metrics
        PerformanceUI.render_summary_metrics(metrics)
        
        st.markdown("---")
        
        # Tabs for different views
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "⏳ Timeline",
            "👤 By Agent",
            "🐌 Slowest",
            "🧠 Memory",
            "📞 API Calls",
        ])
        
        with tab1:
            PerformanceUI.render_execution_timeline(metrics)
        
        with tab2:
            PerformanceUI.render_agent_breakdown(metrics)
        
        with tab3:
            PerformanceUI.render_slowest_operations(metrics)
        
        with tab4:
            PerformanceUI.render_memory_usage(metrics)
        
        with tab5:
            PerformanceUI.render_api_calls_summary(metrics)
        
        # Export options
        st.markdown("---")
        st.subheader("📥 Export Metrics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📋 Copy JSON"):
                import json
                json_str = json.dumps(metrics.to_dict(), indent=2)
                st.code(json_str, language="json")
        
        with col2:
            if st.button("📊 Download CSV"):
                # Create CSV from timings
                if metrics.timings:
                    df = pd.DataFrame([t.to_dict() for t in metrics.timings])
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download Timings",
                        data=csv,
                        file_name=f"timings_{metrics.run_id}.csv",
                        mime="text/csv",
                    )
    
    @staticmethod
    def render_metrics_comparison(
        metrics_list: List[PerformanceMetrics],
    ) -> None:
        """Compare multiple runs."""
        st.subheader("📈 Compare Runs")
        
        if len(metrics_list) < 2:
            st.info("Need at least 2 runs to compare")
            return
        
        # Prepare comparison data
        comparison_data = []
        for metrics in metrics_list:
            analyzer = PerformanceAnalyzer()
            total_cost = CostEstimator.estimate_total_cost(metrics.api_calls)
            summary = analyzer.get_api_call_summary(metrics.api_calls)
            
            comparison_data.append({
                "Run ID": metrics.run_id[:8],
                "Duration (s)": f"{metrics.duration_seconds or 0:.1f}",
                "API Calls": summary["total_calls"],
                "Peak Memory (MB)": (
                    max(
                        (m.peak_memory_mb for m in metrics.memory_samples),
                        default=0,
                    )
                ),
                "Cost (USD)": f"${total_cost:.4f}",
            })
        
        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True, hide_index=True)


def _format_memory(mb: float) -> str:
    """Format memory value."""
    if mb < 1024:
        return f"{mb:.1f} MB"
    else:
        return f"{mb / 1024:.1f} GB"
