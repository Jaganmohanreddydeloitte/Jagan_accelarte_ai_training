"""
Streamlit UI components for interactive data lineage visualization.

Displays lineage diagrams, allows exploration, and shows detailed information.
"""

import streamlit as st
from pathlib import Path
from typing import Optional

from core.lineage import load_lineage, PipelineLineage
from core.lineage_visualizer import create_lineage_diagram


def render_lineage_dashboard(run_id: str):
    """
    Render complete lineage exploration dashboard.
    
    Args:
        run_id: Run ID to load and display lineage for
    """
    # Load lineage
    lineage = load_lineage(run_id)
    
    if not lineage:
        st.error(f"No lineage data found for run {run_id}")
        return
    
    # Header
    st.subheader("📊 Data Lineage Explorer")
    st.caption(f"Business Intent: {lineage.business_intent}")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔄 Data Flow",
        "🔧 Transformations",
        "📋 Stage Details",
        "🔍 Column Trace",
        "📄 Summary"
    ])
    
    # Tab 1: Data Flow
    with tab1:
        st.write("**Data Flow Through Pipeline Stages**")
        st.caption("Shows how data moves from source files through Bronze → Silver → Gold → Report")
        
        diagram = create_lineage_diagram(lineage, "flow")
        st.mermaid(diagram)
        
        # Flow summary
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Source Files", len(lineage.source_files))
        
        with col2:
            total_transformations = sum(len(s.transformations) for s in lineage.stages)
            st.metric("Transformations", total_transformations)
        
        with col3:
            gold_stage = next((s for s in lineage.stages if s.stage_name == "gold"), None)
            gold_rows = gold_stage.row_count if gold_stage else 0
            st.metric("Final Rows", f"{gold_rows:,}")
        
        with col4:
            gold_stage = next((s for s in lineage.stages if s.stage_name == "gold"), None)
            gold_cols = len(gold_stage.columns) if gold_stage else 0
            st.metric("Final Columns", gold_cols)
    
    # Tab 2: Transformations
    with tab2:
        st.write("**Transformations at Each Stage**")
        st.caption("Click stage to see applied transformations")
        
        diagram = create_lineage_diagram(lineage, "transformation")
        st.mermaid(diagram)
        
        # Detailed transformation list
        st.divider()
        st.write("**Detailed Transformation Log**")
        
        for stage in lineage.stages:
            if stage.stage_name == "source" or not stage.transformations:
                continue
            
            with st.expander(f"🔧 {stage.stage_name.upper()} Layer ({len(stage.transformations)} transformations)", expanded=False):
                for i, transform in enumerate(stage.transformations, 1):
                    st.write(f"{i}. {transform}")
                
                if stage.sttm_applied:
                    st.divider()
                    st.write("**STTM Rules Applied:**")
                    st.json(stage.sttm_applied, expanded=False)
    
    # Tab 3: Stage Details
    with tab3:
        st.write("**Detailed Stage Information**")
        
        table_md = create_lineage_diagram(lineage, "table")
        st.markdown(table_md)
        
        st.divider()
        
        # Detailed stage info
        for stage in lineage.stages:
            if stage.stage_name == "source":
                continue
            
            with st.expander(f"📋 {stage.stage_name.upper()} Stage Details", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Input Files:**")
                    for f in stage.input_files:
                        st.write(f"- {f.split('/')[-1]}")
                    
                    st.write("**Output File:**")
                    st.write(stage.output_file.split('/')[-1] if stage.output_file else "N/A")
                
                with col2:
                    st.write("**Row Count:**")
                    st.write(f"{stage.row_count:,}")
                    
                    st.write("**Column Count:**")
                    st.write(len(stage.columns))
                
                st.divider()
                
                # Columns in this stage
                st.write("**Columns in this stage:**")
                for col in stage.columns[:10]:  # Show first 10
                    col_info = f"- **{col.name}**"
                    if col.transformations:
                        col_info += f" ({len(col.transformations)} transformations)"
                    st.write(col_info)
                
                if len(stage.columns) > 10:
                    st.caption(f"... and {len(stage.columns) - 10} more columns")
    
    # Tab 4: Column Trace
    with tab4:
        st.write("**Trace Individual Column Lineage**")
        st.caption("Select a column to see its complete journey through the pipeline")
        
        # Collect all columns from gold stage
        gold_stage = next((s for s in lineage.stages if s.stage_name == "gold"), None)
        if gold_stage:
            column_names = [col.name for col in gold_stage.columns]
            
            if column_names:
                selected_column = st.selectbox(
                    "Select column to trace:",
                    column_names,
                    key="lineage_column_select"
                )
                
                if selected_column:
                    st.divider()
                    
                    # Show column lineage diagram
                    diagram = create_lineage_diagram(lineage, "flow")  # Use flow for simplicity
                    # In production, would use: create_lineage_diagram(lineage, "column", selected_column)
                    
                    st.write(f"**Lineage for column: {selected_column}**")
                    
                    # Find column through stages
                    for stage in lineage.stages:
                        for col in stage.columns:
                            if col.name == selected_column:
                                st.write(f"**{stage.stage_name.upper()} Layer:**")
                                if col.source_file:
                                    st.write(f"- Source: {col.source_file.split('/')[-1]}")
                                if col.source_column:
                                    st.write(f"- Original column: {col.source_column}")
                                if col.transformations:
                                    st.write("- Transformations:")
                                    for t in col.transformations:
                                        st.write(f"  - {t}")
                                st.divider()
            else:
                st.info("No columns found in Gold stage")
        else:
            st.info("No Gold stage data available")
    
    # Tab 5: Summary
    with tab5:
        st.write("**Lineage Summary**")
        
        summary_text = create_lineage_diagram(lineage, "summary")
        st.markdown(summary_text)


def render_lineage_widget(run_id: str):
    """
    Render compact lineage widget for sidebar or report.
    
    Args:
        run_id: Run ID to display lineage for
    """
    lineage = load_lineage(run_id)
    
    if not lineage:
        st.warning("No lineage data available")
        return
    
    st.subheader("📊 Data Lineage")
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_transforms = sum(len(s.transformations) for s in lineage.stages)
        st.metric("Transformations", total_transforms)
    
    with col2:
        gold_stage = next((s for s in lineage.stages if s.stage_name == "gold"), None)
        gold_rows = gold_stage.row_count if gold_stage else 0
        st.metric("Final Rows", f"{gold_rows:,}")
    
    with col3:
        gold_stage = next((s for s in lineage.stages if s.stage_name == "gold"), None)
        gold_cols = len(gold_stage.columns) if gold_stage else 0
        st.metric("Final Columns", gold_cols)
    
    # Mini flow diagram
    st.divider()
    diagram = create_lineage_diagram(lineage, "flow")
    st.mermaid(diagram)


def render_lineage_details_modal(run_id: str, stage_name: str = None):
    """
    Render detailed modal for specific stage.
    
    Args:
        run_id: Run ID
        stage_name: Optional stage to focus on
    """
    lineage = load_lineage(run_id)
    
    if not lineage:
        st.error("Could not load lineage data")
        return
    
    # Find stage
    stage = next(
        (s for s in lineage.stages if s.stage_name == (stage_name or "gold")),
        None
    )
    
    if not stage:
        st.error(f"Stage {stage_name} not found")
        return
    
    st.write(f"### {stage.stage_name.upper()} Layer Details")
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Row Count", f"{stage.row_count:,}")
    with col2:
        st.metric("Columns", len(stage.columns))
    with col3:
        st.metric("Transformations", len(stage.transformations))
    
    # Content tabs
    tab1, tab2 = st.tabs(["Transformations", "Columns"])
    
    with tab1:
        if stage.transformations:
            for i, transform in enumerate(stage.transformations, 1):
                st.write(f"**{i}. {transform}**")
        else:
            st.info("No transformations applied")
    
    with tab2:
        st.write(f"**{len(stage.columns)} columns in output:**")
        for col in stage.columns:
            with st.expander(col.name):
                if col.source_file:
                    st.write(f"**Source:** {col.source_file}")
                if col.source_column:
                    st.write(f"**Original Column:** {col.source_column}")
                if col.transformations:
                    st.write("**Transformations:**")
                    for t in col.transformations:
                        st.write(f"- {t}")
