"""
Quick sanity check to verify all project imports work before running the application.

This script validates that:
1. All core modules can be imported
2. All orchestrator functions are accessible
3. No dependency or configuration errors exist

Run with: python test_import.py
"""

import sys
from pathlib import Path
import traceback

# Add project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set UTF-8 encoding for Windows
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

try:
    # Test core module imports
    print("Testing core module imports...")
    from core.config import BASE_DIR, LLM_PROVIDER
    print("  [OK] core.config")
    
    from core.audit import AuditLogger
    print("  [OK] core.audit")
    
    from core.observability import AgentTrace
    print("  [OK] core.observability")
    
    from core.state import PipelineState
    print("  [OK] core.state")
    
    from core.memory import store_document, query_memory
    print("  [OK] core.memory")
    
    # Test agent module imports
    print("\nTesting agent module imports...")
    from agents.profiler import profile_dataset, profile_multiple_datasets
    print("  [OK] agents.profiler")
    
    from agents.bronze_agent import execute_bronze
    print("  [OK] agents.bronze_agent")
    
    from agents.silver_agent import execute_silver
    print("  [OK] agents.silver_agent")
    
    from agents.gold_agent import execute_gold
    print("  [OK] agents.gold_agent")
    
    from agents.sttm_generator import generate_bronze_sttm, generate_silver_sttm, generate_gold_sttm
    print("  [OK] agents.sttm_generator")
    
    from agents.reporter import generate_report
    print("  [OK] agents.reporter")
    
    # Test orchestrator imports (main entry points)
    print("\nTesting orchestrator imports...")
    from agents.orchestrator import (
        run_until_bronze_sttm,
        run_bronze_to_silver_sttm,
        run_silver_to_gold_sttm,
        run_gold_and_report,
    )
    print("  [OK] agents.orchestrator")
    print("    - run_until_bronze_sttm")
    print("    - run_bronze_to_silver_sttm")
    print("    - run_silver_to_gold_sttm")
    print("    - run_gold_and_report")
    
    # Test app imports
    print("\nTesting app module imports...")
    # Note: Streamlit app may have rendering dependencies, so wrap in try/except
    try:
        from app.streamlit_app import render_progress_banner
        print("  [OK] app.streamlit_app")
    except Exception as e:
        print(f"  [WARN] app.streamlit_app (expected if running outside Streamlit): {type(e).__name__}")
    
    print("\n" + "="*60)
    print("SUCCESS! All core imports worked.")
    print("="*60)
    print(f"\nProject root: {project_root}")
    print(f"LLM Provider: {LLM_PROVIDER}")
    print(f"Base directory: {BASE_DIR}")
    print("\nReady to run the pipeline!")

except Exception as e:
    print("\n" + "="*60)
    print(f"IMPORT ERROR: {type(e).__name__}: {e}")
    print("="*60)
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
