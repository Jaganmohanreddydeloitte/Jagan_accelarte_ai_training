"""
STTM Version Control UI Components for Streamlit

Displays version history, comparison, and restoration UI.
"""

import streamlit as st
from datetime import datetime
from typing import Optional

from core.sttm_versioning import get_version_manager


def render_version_history_tab():
    """Display version history for all STTM layers"""
    st.markdown("### 📋 Version History")

    version_mgr = get_version_manager()
    history = version_mgr.get_version_history()

    if not history:
        st.info("No STTM versions recorded yet")
        return

    # Filter options
    col1, col2 = st.columns(2)

    with col1:
        layer_filter = st.selectbox(
            "Filter by layer:",
            ["All"] + list(set(v["layer"] for v in history)),
            key="version_layer_filter",
        )

    with col2:
        user_filter = st.selectbox(
            "Filter by user:",
            ["All"] + list(set(v["user"] for v in history)),
            key="version_user_filter",
        )

    # Apply filters
    filtered_history = history
    if layer_filter != "All":
        filtered_history = [v for v in filtered_history if v["layer"] == layer_filter]
    if user_filter != "All":
        filtered_history = [v for v in filtered_history if v["user"] == user_filter]

    # Display as table
    if filtered_history:
        st.markdown("#### Recent Versions")

        for i, version in enumerate(filtered_history[:20]):  # Show top 20
            with st.expander(
                f"🔹 {version['version_id']} — {version['layer'].upper()} — {version['timestamp'][:16]}"
            ):
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Layer", version["layer"].upper())

                with col2:
                    st.metric("Rows", version["row_count"])

                with col3:
                    size_kb = version["file_size_bytes"] / 1024
                    st.metric("Size", f"{size_kb:.1f} KB")

                with col4:
                    st.metric("User", version["user"])

                st.markdown(f"**Description:** {version['description']}")
                st.markdown(f"**Timestamp:** {version['timestamp']}")
                st.markdown(f"**Hash:** `{version['content_hash'][:16]}...`")

                # Get change summary
                summary = version_mgr.get_change_summary(version["version_id"])

                if not summary.get("is_first_version"):
                    st.markdown("**Changes from previous version:**")

                    delta_col1, delta_col2, delta_col3 = st.columns(3)
                    with delta_col1:
                        st.metric("Added", summary.get("added_rules", 0))
                    with delta_col2:
                        st.metric("Removed", summary.get("removed_rules", 0))
                    with delta_col3:
                        st.metric("Modified", summary.get("modified_rules", 0))

                # Action buttons
                action_col1, action_col2, action_col3 = st.columns(3)

                with action_col1:
                    if st.button(
                        "👁️ View Details", key=f"view_{version['version_id']}"
                    ):
                        st.session_state.view_version_id = version["version_id"]

                with action_col2:
                    if st.button(
                        "🔄 Restore This Version", key=f"restore_{version['version_id']}"
                    ):
                        st.session_state.restore_version_id = version["version_id"]

                with action_col3:
                    if st.button(
                        "📥 Export as CSV", key=f"export_{version['version_id']}"
                    ):
                        st.session_state.export_version_id = version["version_id"]
    else:
        st.warning("No versions match your filters")


def render_version_comparison_tab():
    """Compare two versions side-by-side"""
    st.markdown("### 🔀 Compare Versions")

    version_mgr = get_version_manager()
    history = version_mgr.get_version_history()

    if len(history) < 2:
        st.info("Need at least 2 versions to compare")
        return

    col1, col2 = st.columns(2)

    with col1:
        version_id_1 = st.selectbox(
            "From version:",
            [v["version_id"] for v in history],
            key="compare_from",
        )

    with col2:
        # Filter to versions after the selected one
        from_idx = next((i for i, v in enumerate(history) if v["version_id"] == version_id_1), -1)
        available_to = [v["version_id"] for v in history[:from_idx]] if from_idx > 0 else []

        if available_to:
            version_id_2 = st.selectbox("To version:", available_to, key="compare_to")
        else:
            st.warning("No newer version to compare with")
            return

    # Get versions
    v1 = version_mgr.get_version(version_id_1)
    v2 = version_mgr.get_version(version_id_2)

    if not v1 or not v2:
        st.error("Version not found")
        return

    # Show metadata
    st.markdown("#### Metadata Comparison")

    meta_col1, meta_col2 = st.columns(2)

    with meta_col1:
        st.markdown(f"**Version 1: {version_id_1}**")
        st.markdown(f"- Timestamp: {v1.timestamp}")
        st.markdown(f"- User: {v1.user}")
        st.markdown(f"- Rows: {v1.row_count}")
        st.markdown(f"- Size: {v1.file_size_bytes / 1024:.1f} KB")

    with meta_col2:
        st.markdown(f"**Version 2: {version_id_2}**")
        st.markdown(f"- Timestamp: {v2.timestamp}")
        st.markdown(f"- User: {v2.user}")
        st.markdown(f"- Rows: {v2.row_count}")
        st.markdown(f"- Size: {v2.file_size_bytes / 1024:.1f} KB")

    # Show unified diff
    st.markdown("#### Unified Diff")

    diff = version_mgr.diff_versions(version_id_1, version_id_2)

    if diff:
        st.code(diff, language="diff")
    else:
        st.info("No differences found")

    # Side-by-side content view
    st.markdown("#### Side-by-Side Content")

    import json

    view_col1, view_col2 = st.columns(2)

    with view_col1:
        st.markdown(f"**{version_id_1}**")
        st.json(v1.sttm_content, expanded=False)

    with view_col2:
        st.markdown(f"**{version_id_2}**")
        st.json(v2.sttm_content, expanded=False)


def render_version_restore_dialog():
    """Modal dialog for restoring a version"""
    if "restore_version_id" not in st.session_state:
        return

    version_id = st.session_state.restore_version_id
    version_mgr = get_version_manager()
    version = version_mgr.get_version(version_id)

    if not version:
        return

    st.warning(
        f"⚠️ **Are you sure you want to restore version `{version_id}`?**"
    )

    st.markdown(
        f"""
    This will create a new version with the content from **{version_id}**.
    
    - **Layer:** {version.layer.upper()}
    - **Timestamp:** {version.timestamp}
    - **User:** {version.user}
    - **Description:** {version.description}
    - **Rows:** {version.row_count}
    
    The original version will remain in history.
    """
    )

    restore_reason = st.text_input("Why are you restoring this version?", key="restore_reason_input")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Confirm Restore", key="confirm_restore"):
            success = version_mgr.restore_version(
                version_id=version_id,
                user=st.session_state.get("username", "unknown"),
                restore_reason=restore_reason or "Manual restore",
            )

            if success:
                st.success(f"✅ Successfully restored version {version_id}")
                del st.session_state.restore_version_id
                st.rerun()
            else:
                st.error("❌ Failed to restore version")

    with col2:
        if st.button("❌ Cancel", key="cancel_restore"):
            del st.session_state.restore_version_id
            st.rerun()


def render_version_stats():
    """Show statistics about version history"""
    st.markdown("### 📊 Version Statistics")

    version_mgr = get_version_manager()
    stats = version_mgr.get_version_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Versions", stats["total_versions"])

    with col2:
        st.metric("Layers", len(stats["layers"]))

    with col3:
        storage_mb = stats["total_storage_bytes"] / (1024 * 1024)
        st.metric("Storage Used", f"{storage_mb:.2f} MB")

    with col4:
        st.metric("Users", len(stats["users"]))

    # Versions by layer
    if stats["versions_by_layer"]:
        st.markdown("#### Versions by Layer")

        layer_data = stats["versions_by_layer"]
        layer_names = list(layer_data.keys())
        layer_counts = list(layer_data.values())

        import plotly.express as px

        fig = px.bar(
            x=layer_names,
            y=layer_counts,
            labels={"x": "Layer", "y": "Version Count"},
            title="STTM Versions per Layer",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Timeline
    if stats["total_versions"] > 0:
        st.markdown("#### Version Timeline")

        history = version_mgr.get_version_history()

        import plotly.graph_objects as go

        timestamps = [v["timestamp"][:10] for v in history]
        layers = [v["layer"] for v in history]

        fig = go.Figure()

        for layer in set(layers):
            layer_timestamps = [
                h["timestamp"][:10] for h in history if h["layer"] == layer
            ]
            layer_counts = [1] * len(layer_timestamps)

            fig.add_trace(
                go.Scatter(
                    x=layer_timestamps,
                    y=layer_counts,
                    mode="markers+lines",
                    name=layer.upper(),
                    marker=dict(size=10),
                )
            )

        fig.update_layout(title="Version Activity Timeline", xaxis_title="Date", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)


def render_version_management_panel():
    """Administrative panel for managing versions"""
    st.markdown("### ⚙️ Version Management")

    version_mgr = get_version_manager()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Cleanup Old Versions")

        keep_count = st.slider("Keep last N versions:", 1, 50, 10, key="cleanup_keep_count")
        layer_cleanup = st.selectbox(
            "Cleanup for:",
            ["All Layers"] + list(set(v["layer"] for v in version_mgr.metadata)),
            key="cleanup_layer",
        )

        if st.button("🗑️ Delete Old Versions", key="cleanup_button"):
            layer = None if layer_cleanup == "All Layers" else layer_cleanup
            deleted = version_mgr.clear_old_versions(keep_count=keep_count, layer=layer)

            if deleted > 0:
                st.success(f"✅ Deleted {deleted} old version(s)")
            else:
                st.info("No old versions to delete")

            st.rerun()

    with col2:
        st.markdown("#### Export All Versions")

        export_layer = st.selectbox(
            "Export for layer:",
            ["All"] + list(set(v["layer"] for v in version_mgr.metadata)),
            key="export_all_layer",
        )

        if st.button("📥 Export to JSON", key="export_all_button"):
            history = version_mgr.get_version_history(
                None if export_layer == "All" else export_layer
            )

            import json

            json_str = json.dumps(history, indent=2, default=str)
            st.download_button(
                "Download JSON",
                json_str,
                file_name=f"sttm_versions_{export_layer}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
            )


def render_version_dashboard():
    """Complete version control dashboard"""
    st.markdown("# 📚 STTM Version Control")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["History", "Compare", "Statistics", "Management", "Settings"]
    )

    with tab1:
        render_version_history_tab()

    with tab2:
        render_version_comparison_tab()

    with tab3:
        render_version_stats()

    with tab4:
        render_version_management_panel()

    with tab5:
        st.markdown("### ⚙️ Version Control Settings")

        st.markdown(
            """
        **Current Configuration:**
        - Auto-save on STTM generation: ✅ Enabled
        - Change detection: Content-based SHA256 hashing
        - Version storage: `.audit_logs/sttm_versions/`
        - Retention policy: Keep all versions (manual cleanup available)
        """
        )

        st.markdown(
            """
        **Best Practices:**
        1. **Descriptive commit messages** - Always explain what changed
        2. **Regular exports** - Back up important versions to JSON
        3. **Review changes** - Use Compare tab to review before restoring
        4. **Cleanup old versions** - Periodically remove versions older than 3 months
        """
        )

    # Handle dialogs
    render_version_restore_dialog()
