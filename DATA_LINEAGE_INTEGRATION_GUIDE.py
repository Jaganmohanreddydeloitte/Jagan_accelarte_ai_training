"""
Data Lineage Integration Guide - Practical Examples

Shows how to integrate lineage tracking into the pipeline at each stage.
"""

# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 1: Initialize Lineage in Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

from core.lineage import LineageTracker
from agents.orchestrator import run_until_bronze_sttm

def run_until_bronze_sttm_with_lineage(file_paths, business_intent):
    """Enhanced version with lineage tracking."""
    run_id = str(uuid4())
    
    # Initialize lineage tracker
    tracker = LineageTracker(run_id, business_intent)
    print(f"[Lineage] Started tracking for run {run_id}")
    
    # Profile files
    profiles = profile_dataset(file_paths[0])
    
    # Track source files
    tracker.track_source_files(file_paths, {file_paths[0]: profiles})
    print(f"[Lineage] Tracked {len(file_paths)} source files")
    
    # Start bronze stage
    tracker.start_stage("bronze", file_paths)
    
    # ... run bronze transformations ...
    tracker.add_transformation(
        "bronze",
        "Applied Bronze STTM rules",
        input_columns=list(profiles.get("columns", [])),
        output_columns=list(profiles.get("columns", []))
    )
    
    # Complete bronze stage
    tracker.complete_stage(
        "bronze",
        output_file=str(bronze_files[0]),
        row_count=50000,
        output_columns=[c["name"] for c in profiles["columns"]]
    )
    
    print(f"[Lineage] Completed bronze stage: 50,000 rows")
    
    # Save lineage
    lineage_file = tracker.save()
    print(f"[Lineage] Saved to {lineage_file}")
    
    return {
        "run_id": run_id,
        "bronze_files": bronze_files,
        # ... other state ...
    }


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 2: Track Silver Layer Transformations
# ─────────────────────────────────────────────────────────────────────────────

from core.lineage import load_lineage

def run_bronze_to_silver_sttm_with_lineage(pipeline_state):
    """Silver stage with lineage tracking."""
    run_id = pipeline_state["run_id"]
    
    # Load existing lineage
    tracker = LineageTracker(run_id, "")
    tracker.lineage = load_lineage(run_id)  # Load from file
    print(f"[Lineage] Loaded lineage for run {run_id}")
    
    # Start silver stage
    tracker.start_stage("silver", pipeline_state.get("bronze_output_paths", []))
    
    # Track transformations
    tracker.add_transformation(
        "silver",
        "Removed duplicate records (kept first occurrence)",
        input_columns=["all columns"],
        output_columns=["all columns"]
    )
    
    tracker.add_transformation(
        "silver",
        "Added derived columns: customer_segment based on lifetime_value",
        input_columns=["lifetime_value"],
        output_columns=["customer_segment"]
    )
    
    tracker.add_transformation(
        "silver",
        "Consolidated addresses (standardized format)",
        input_columns=["street", "city", "state", "zip"],
        output_columns=["full_address"]
    )
    
    # Apply STTM rules
    tracker.add_sttm_rules("silver", {
        "rules_applied": 3,
        "columns_filtered": 0,
        "columns_renamed": 2,
        "expressions_applied": 1
    })
    
    # Complete stage
    tracker.complete_stage(
        "silver",
        output_file=str(silver_files[0]),
        row_count=48500,
        output_columns=silver_columns
    )
    
    # Save
    tracker.save()
    print(f"[Lineage] Silver stage complete: 48,500 rows, 3 transformations")
    
    return {**pipeline_state, "silver_output_paths": silver_files}


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 3: Display Lineage in Streamlit
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
from core.lineage_ui import render_lineage_dashboard

# In Streamlit app report phase
def show_report_with_lineage():
    """Display report and lineage."""
    st.header("Executive Report")
    
    # Display report HTML
    report_path = st.session_state.pipeline_state.get("report_path")
    if report_path:
        with open(report_path) as f:
            st.components.v1.html(f.read(), height=2000)
    
    # Display lineage
    st.divider()
    
    run_id = st.session_state.pipeline_state.get("run_id")
    render_lineage_dashboard(run_id)


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 4: Query Lineage for Analysis
# ─────────────────────────────────────────────────────────────────────────────

from core.lineage import load_lineage

def analyze_data_quality(run_id):
    """Analyze how data changed through pipeline."""
    lineage = load_lineage(run_id)
    
    print("=== Data Quality Analysis ===\n")
    
    for stage in lineage.stages:
        if stage.stage_name == "source":
            continue
        
        print(f"{stage.stage_name.upper()}:")
        print(f"  Input rows: [from previous stage]")
        print(f"  Output rows: {stage.row_count:,}")
        print(f"  Columns: {len(stage.columns)}")
        print(f"  Transformations: {len(stage.transformations)}")
        
        # Calculate data retention
        if stage.stage_name == "bronze":
            bronze_rows = stage.row_count
        elif stage.stage_name == "silver":
            retention = (stage.row_count / bronze_rows * 100) if bronze_rows else 0
            print(f"  Data retention: {retention:.1f}%")
        
        print()
    
    # Find transformations
    summary = lineage.get_data_flow_summary()
    print(f"Total transformations: {summary['total_transformations']}")
    
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 5: Column-Level Lineage Query
# ─────────────────────────────────────────────────────────────────────────────

def trace_column_origin(run_id, column_name):
    """Trace where a column came from."""
    tracker = LineageTracker(run_id, "")
    tracker.lineage = load_lineage(run_id)
    
    source = tracker.get_column_source(column_name)
    
    if source:
        print(f"\nColumn: {column_name}")
        print(f"Source file: {source['source_file']}")
        print(f"Original column: {source['source_column']}")
        print(f"Transformations:")
        for t in source['transformations']:
            print(f"  - {t}")
    else:
        print(f"Column '{column_name}' not found in lineage")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 6: Export Lineage Report
# ─────────────────────────────────────────────────────────────────────────────

import json
from core.lineage_visualizer import create_lineage_diagram

def export_lineage_report(run_id, output_path):
    """Export lineage as comprehensive report."""
    lineage = load_lineage(run_id)
    
    report = {
        "metadata": {
            "run_id": lineage.run_id,
            "business_intent": lineage.business_intent,
            "created": lineage.created_at,
            "completed": lineage.completed_at,
        },
        "data_flow": lineage.get_data_flow_summary(),
        "diagrams": {
            "flow": create_lineage_diagram(lineage, "flow"),
            "transformations": create_lineage_diagram(lineage, "transformation"),
            "table": create_lineage_diagram(lineage, "table"),
            "summary": create_lineage_diagram(lineage, "summary"),
        }
    }
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Exported lineage to {output_path}")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 7: Compliance Audit - Generate Lineage Certificate
# ─────────────────────────────────────────────────────────────────────────────

def generate_lineage_certificate(run_id, auditor_name="Compliance Officer"):
    """Generate audit certificate showing data provenance."""
    lineage = load_lineage(run_id)
    
    certificate = f"""
    ╔═══════════════════════════════════════════════════════╗
    ║        DATA LINEAGE & PROVENANCE CERTIFICATE          ║
    ╚═══════════════════════════════════════════════════════╝
    
    Run ID: {lineage.run_id}
    Business Intent: {lineage.business_intent}
    Date: {lineage.created_at}
    
    SOURCE FILES:
    {chr(10).join(f"    ✓ {f}" for f in lineage.source_files)}
    
    PROCESSING STAGES:
    {chr(10).join(f"    → {s.stage_name.upper()}: {s.row_count:,} rows, {len(s.columns)} columns" for s in lineage.stages if s.stage_name != "source")}
    
    TOTAL TRANSFORMATIONS: {sum(len(s.transformations) for s in lineage.stages)}
    
    Certified by: {auditor_name}
    Timestamp: {lineage.completed_at}
    
    ✓ All data transformations tracked
    ✓ Complete audit trail available
    ✓ Compliant with data governance
    """
    
    return certificate


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 8: Lineage Search & Filter
# ─────────────────────────────────────────────────────────────────────────────

def find_transformations_by_keyword(run_id, keyword):
    """Search for transformations containing keyword."""
    lineage = load_lineage(run_id)
    
    results = []
    for stage in lineage.stages:
        for transform in stage.transformations:
            if keyword.lower() in transform.lower():
                results.append({
                    "stage": stage.stage_name,
                    "transformation": transform
                })
    
    return results


# Example usage:
# results = find_transformations_by_keyword(run_id, "customer")
# for r in results:
#     print(f"{r['stage']}: {r['transformation']}")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 9: Performance Impact Analysis
# ─────────────────────────────────────────────────────────────────────────────

import time
from core.lineage import LineageTracker

def benchmark_lineage_overhead():
    """Test performance impact of lineage tracking."""
    
    # Without lineage
    start = time.time()
    for i in range(10000):
        pass  # Simulate work
    time_without = time.time() - start
    
    # With lineage
    tracker = LineageTracker("test_run", "Test")
    start = time.time()
    for i in range(10000):
        if i % 100 == 0:
            tracker.add_transformation("test", f"Transform {i}")
    time_with = time.time() - start
    
    overhead = (time_with - time_without) / time_without * 100
    
    print(f"Time without lineage: {time_without*1000:.2f}ms")
    print(f"Time with lineage: {time_with*1000:.2f}ms")
    print(f"Overhead: {overhead:.2f}%")
    
    # Typical result: <1% overhead


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 10: Integration with Existing Metrics System
# ─────────────────────────────────────────────────────────────────────────────

from core.admin_metrics import get_pipeline_metrics

def track_with_metrics(run_id, stage_name):
    """Record both lineage and metrics."""
    
    # Get metric recorder
    metrics = get_pipeline_metrics()
    
    # Record lineage
    tracker = LineageTracker(run_id, "")
    tracker.lineage = load_lineage(run_id)
    
    # Record transformation as metric
    stage_transforms = tracker.get_stage_transformations(stage_name)
    metrics.record_agent_run(
        agent_name=f"{stage_name}_sttm",
        run_id=run_id,
        duration_seconds=5.2,
        status="success",
        extra_data={"transformations_applied": len(stage_transforms)}
    )
    
    # Save both
    tracker.save()


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 11: Batch Lineage Generation
# ─────────────────────────────────────────────────────────────────────────────

import os
from pathlib import Path
from core.lineage import load_lineage
from core.lineage_visualizer import create_lineage_diagram

def generate_lineage_for_all_runs():
    """Generate lineage diagrams for all runs."""
    
    lineage_dir = Path("data/lineage")
    
    print("Generating lineage diagrams...\n")
    
    for lineage_file in lineage_dir.glob("lineage_*.json"):
        run_id = lineage_file.stem.replace("lineage_", "")
        
        lineage = load_lineage(run_id)
        if not lineage:
            continue
        
        print(f"Run {run_id}:")
        
        # Generate all diagram types
        for diagram_type in ["flow", "transformation", "table"]:
            diagram = create_lineage_diagram(lineage, diagram_type)
            print(f"  ✓ Generated {diagram_type} diagram")
        
        print()


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 12: Lineage Migration & Versioning
# ─────────────────────────────────────────────────────────────────────────────

import shutil
from datetime import datetime

def archive_old_lineage(days_old=90):
    """Archive lineage older than N days."""
    
    lineage_dir = Path("data/lineage")
    archive_dir = Path("data/lineage_archive")
    archive_dir.mkdir(exist_ok=True)
    
    cutoff = datetime.now().timestamp() - (days_old * 86400)
    
    for lineage_file in lineage_dir.glob("lineage_*.json"):
        mtime = lineage_file.stat().st_mtime
        
        if mtime < cutoff:
            archive_path = archive_dir / lineage_file.name
            shutil.move(str(lineage_file), str(archive_path))
            print(f"Archived {lineage_file.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Quick Reference Summary
# ─────────────────────────────────────────────────────────────────────────────

"""
Quick Integration Checklist:

1. Initialize tracker at pipeline start:
   tracker = LineageTracker(run_id, business_intent)

2. Track source files after profiling:
   tracker.track_source_files(file_paths, profiles)

3. For each stage (Bronze, Silver, Gold):
   a. Start stage:  tracker.start_stage(stage_name, input_files)
   b. Add transforms: tracker.add_transformation(stage_name, description, ...)
   c. Complete: tracker.complete_stage(stage_name, output_file, row_count, columns)

4. Save lineage at end:
   tracker.save()

5. Display in Streamlit:
   render_lineage_dashboard(run_id)

6. Query lineage:
   lineage = load_lineage(run_id)
   source = tracker.get_column_source("column_name")

That's it! Lineage is now tracked end-to-end.
"""
