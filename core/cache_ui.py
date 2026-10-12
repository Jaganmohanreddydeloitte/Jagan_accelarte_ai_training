"""
Streamlit UI components for cache status and management.

Displays cache statistics, hit rates, and provides cache management controls.
"""

import streamlit as st
from pathlib import Path
from datetime import datetime

from core.caching import get_cache_manager, CACHE_DIR


def render_cache_status_sidebar() -> None:
    """Render cache status panel in Streamlit sidebar."""
    
    cache_mgr = get_cache_manager()
    stats = cache_mgr.get_stats()
    
    with st.sidebar:
        st.markdown("---")
        
        with st.expander("💾 **Cache Status**", expanded=False):
            # Status indicator
            if stats["enabled"]:
                st.success("✓ Caching **Enabled**")
            else:
                st.warning("⚠ Caching **Disabled**")
            
            # Cache size
            cache_size = stats["cache_dir_size_mb"]
            st.metric(
                "Cache Size",
                f"{cache_size:.2f} MB",
                delta="Auto-managed" if cache_size > 0 else "Empty"
            )
            
            # Total entries
            st.metric("Total Cached", f"{stats['total_entries']} entries")
            
            # Hit rates
            col1, col2, col3 = st.columns(3)
            
            with col1:
                profile_rate = stats["profile"]["hit_rate"]
                st.metric(
                    "Profile",
                    f"{profile_rate:.0f}%",
                    delta=f"{stats['profile']['hits']} hits"
                )
            
            with col2:
                sttm_rate = stats["sttm"]["hit_rate"]
                st.metric(
                    "STTM",
                    f"{sttm_rate:.0f}%",
                    delta=f"{stats['sttm']['hits']} hits"
                )
            
            with col3:
                llm_rate = stats["llm"]["hit_rate"]
                st.metric(
                    "LLM",
                    f"{llm_rate:.0f}%",
                    delta=f"{stats['llm']['hits']} hits"
                )
            
            # Cache management
            st.markdown("#### Cache Management")
            
            col_clear1, col_clear2, col_clear3 = st.columns(3)
            
            with col_clear1:
                if st.button("🗑️ Clear All", key="clear_all_cache"):
                    cleared = cache_mgr.clear_cache()
                    st.success(f"Cleared {cleared} entries")
                    st.rerun()
            
            with col_clear2:
                if st.button("📋 Clear STTM", key="clear_sttm_cache"):
                    cleared = cache_mgr.clear_cache(cache_type="sttm")
                    st.info(f"Cleared {cleared} STTM entries")
                    st.rerun()
            
            with col_clear3:
                if st.button("💬 Clear LLM", key="clear_llm_cache"):
                    cleared = cache_mgr.clear_cache(cache_type="llm")
                    st.info(f"Cleared {cleared} LLM entries")
                    st.rerun()


def render_cache_details_tab() -> None:
    """Render detailed cache statistics in main content area."""
    
    cache_mgr = get_cache_manager()
    stats = cache_mgr.get_stats()
    
    # Title
    st.header("💾 Cache Management")
    
    # Status summary
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Status",
            "Enabled" if stats["enabled"] else "Disabled",
            delta="Active" if stats["enabled"] else "Inactive"
        )
    
    with col2:
        st.metric("Cache Size", f"{stats['cache_dir_size_mb']:.2f} MB")
    
    with col3:
        st.metric("Total Entries", stats["total_entries"])
    
    with col4:
        total_hits = (
            stats["profile"]["hits"] +
            stats["sttm"]["hits"] +
            stats["llm"]["hits"]
        )
        st.metric("Total Cache Hits", total_hits)
    
    # Detailed statistics
    st.markdown("---")
    st.subheader("📊 Cache Statistics by Type")
    
    # Profile cache
    with st.expander("📁 **Profile Cache**", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Hits", stats["profile"]["hits"])
        
        with col2:
            st.metric("Misses", stats["profile"]["misses"])
        
        with col3:
            st.metric("Hit Rate", f"{stats['profile']['hit_rate']:.1f}%")
        
        st.info(
            "✓ Profile cache: Skips file analysis for repeated files. "
            f"**Saved: {stats['profile']['hits']} profile generations**"
        )
    
    # STTM cache
    with st.expander("🔄 **STTM Cache**", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Hits", stats["sttm"]["hits"])
        
        with col2:
            st.metric("Misses", stats["sttm"]["misses"])
        
        with col3:
            st.metric("Hit Rate", f"{stats['sttm']['hit_rate']:.1f}%")
        
        st.info(
            "✓ STTM cache: Reuses transformation rules for similar files. "
            f"**Saved: {stats['sttm']['hits']} STTM generations**"
        )
    
    # LLM cache
    with st.expander("💬 **LLM Response Cache**", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Hits", stats["llm"]["hits"])
        
        with col2:
            st.metric("Misses", stats["llm"]["misses"])
        
        with col3:
            st.metric("Hit Rate", f"{stats['llm']['hit_rate']:.1f}%")
        
        st.info(
            "✓ LLM cache: Minimizes API calls by caching responses. "
            f"**Saved: {stats['llm']['hits']} API calls**"
        )
    
    # Cache directory info
    st.markdown("---")
    st.subheader("📁 Cache Directory")
    
    st.code(f"Location: {CACHE_DIR}", language="bash")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Refresh Stats"):
            st.rerun()
    
    with col2:
        if st.button("⚙️ Advanced Options"):
            st.session_state.show_cache_options = not st.session_state.get("show_cache_options", False)
            st.rerun()
    
    # Advanced options
    if st.session_state.get("show_cache_options", False):
        st.markdown("---")
        st.subheader("⚙️ Advanced Cache Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            days_old = st.slider(
                "Clear entries older than (days)",
                min_value=1,
                max_value=365,
                value=30,
                key="cache_age_slider"
            )
            
            if st.button("Clear Old Entries"):
                cleared = cache_mgr.clear_cache(older_than_days=days_old)
                st.success(f"Cleared {cleared} entries older than {days_old} days")
                st.rerun()
        
        with col2:
            cache_types = ["All", "Profile", "STTM", "LLM"]
            selected_type = st.selectbox(
                "Clear by type",
                cache_types,
                key="cache_type_select"
            )
            
            type_map = {
                "Profile": "profile",
                "STTM": "sttm",
                "LLM": "llm"
            }
            
            if st.button("Clear Selected Type"):
                cache_type = type_map.get(selected_type)
                cleared = cache_mgr.clear_cache(cache_type=cache_type)
                st.success(f"Cleared {cleared} {selected_type} entries")
                st.rerun()


def render_cache_impact() -> None:
    """
    Render summary of cache impact on the current run.
    
    To be called after a pipeline run completes.
    """
    
    if "cache_impact" not in st.session_state:
        return
    
    impact = st.session_state.cache_impact
    
    st.markdown("---")
    
    with st.expander("📊 **Cache Impact Summary**", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Profiles Cached",
                impact["profiles_cached"],
                delta=f"Hit: {impact['profile_hits']}"
            )
        
        with col2:
            st.metric(
                "STTM Cached",
                impact["sttm_cached"],
                delta=f"Hit: {impact['sttm_hits']}"
            )
        
        with col3:
            st.metric(
                "API Calls Saved",
                impact["llm_hits"],
                delta=f"Savings: {impact.get('estimated_savings', '$0')}"
            )
        
        st.success(
            f"**Cache Savings:** This run was {impact.get('time_saved_pct', 0):.0f}% "
            f"faster due to {impact['total_hits']} cache hits."
        )


def cache_tracking_context(run_id: str):
    """
    Context manager for tracking cache usage during a run.
    
    Usage:
        with cache_tracking_context("RUN123") as tracker:
            # ... do work ...
            tracker.record_profile_hit()
            tracker.record_sttm_hit()
    """
    
    class CacheTracker:
        def __init__(self, run_id: str):
            self.run_id = run_id
            self.impact = {
                "run_id": run_id,
                "profiles_cached": 0,
                "profile_hits": 0,
                "sttm_cached": 0,
                "sttm_hits": 0,
                "llm_hits": 0,
                "total_hits": 0,
                "estimated_savings": "$0",
                "time_saved_pct": 0,
            }
            self.start_time = datetime.now()
        
        def record_profile_hit(self):
            self.impact["profile_hits"] += 1
            self.impact["total_hits"] += 1
        
        def record_profile_miss(self):
            self.impact["profiles_cached"] += 1
        
        def record_sttm_hit(self):
            self.impact["sttm_hits"] += 1
            self.impact["total_hits"] += 1
        
        def record_sttm_miss(self):
            self.impact["sttm_cached"] += 1
        
        def record_llm_hit(self):
            self.impact["llm_hits"] += 1
            self.impact["total_hits"] += 1
        
        def finalize(self):
            # Estimate API call savings (rough)
            # Assume each LLM call costs ~$0.001
            self.impact["estimated_savings"] = f"${self.impact['llm_hits'] * 0.001:.4f}"
            
            # Estimate time saved (rough)
            # Assume each cached call saves ~30 seconds
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed > 0:
                time_saved = self.impact["total_hits"] * 30
                self.impact["time_saved_pct"] = (time_saved / (elapsed + time_saved)) * 100
            
            # Store in session state
            st.session_state.cache_impact = self.impact
        
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.finalize()
    
    return CacheTracker(run_id)
