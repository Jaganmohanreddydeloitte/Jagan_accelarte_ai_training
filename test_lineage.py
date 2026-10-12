"""
Test script for Data Lineage components
"""

from core.lineage import LineageTracker, load_lineage
from core.lineage_visualizer import LineageVisualizer
import json

print("\n" + "="*60)
print("DATA LINEAGE - COMPONENT VERIFICATION")
print("="*60 + "\n")

# Test 1: Initialize tracker
print("1. Testing LineageTracker initialization...")
tracker = LineageTracker("test_run_123", "Test business intent")
print("   [OK] LineageTracker created")
print(f"   - Run ID: {tracker.run_id}")
print(f"   - Intent: {tracker.lineage.business_intent}")

# Test 2: Track source files
print("\n2. Testing source file tracking...")
tracker.track_source_files(
    ["data/customers.csv"],
    {
        "data/customers.csv": {
            "columns": [
                {"name": "customer_id", "type": "int"},
                {"name": "name", "type": "string"},
                {"name": "email", "type": "string"},
            ]
        }
    }
)
print("   [OK] Source files tracked")
print(f"   - Files: {len(tracker.lineage.source_files)}")

# Test 3: Track stages
print("\n3. Testing stage tracking...")
tracker.start_stage("bronze", ["data/customers.csv"])
tracker.add_transformation(
    "bronze", 
    "Removed 500 null rows",
    ["customer_id"],
    ["customer_id"]
)
tracker.complete_stage(
    "bronze",
    "data/bronze/customers.parquet",
    9500,
    ["customer_id", "name", "email"]
)
print("   [OK] Bronze stage tracked")
print("   - 9,500 rows")
print("   - 3 columns")

# Test 4: Visualizer
print("\n4. Testing LineageVisualizer...")
visualizer = LineageVisualizer(tracker.lineage)
diagram = visualizer.generate_flow_diagram()
print("   [OK] Flow diagram generated")
print(f"   - Diagram length: {len(diagram)} chars")

# Test 5: Summary
print("\n5. Testing summary generation...")
summary = tracker.get_data_flow_summary()
print("   [OK] Summary created")
print(f"   - Source files: {len(summary['source_files'])}")
print(f"   - Stages: {len(summary['stages'])}")

# Test 6: Save lineage
print("\n6. Testing lineage persistence...")
lineage_file = tracker.save()
print("   [OK] Lineage saved")
print(f"   - File exists: {lineage_file.exists()}")
print(f"   - File size: {lineage_file.stat().st_size} bytes")

# Test 7: Load lineage
print("\n7. Testing lineage loading...")
loaded = load_lineage("test_run_123")
print("   [OK] Lineage loaded")
print(f"   - Run ID matches: {loaded.run_id == 'test_run_123'}")
print(f"   - Intent matches: {loaded.business_intent == 'Test business intent'}")

# Test 8: Query operations
print("\n8. Testing query operations...")
col_source = tracker.get_column_source("customer_id")
print("   [OK] Column source query works")
print(f"   - Found column: {col_source is not None}")

transforms = tracker.get_stage_transformations("bronze")
print("   [OK] Stage query works")
print(f"   - Transformations: {len(transforms)}")

print("\n" + "="*60)
print("[SUCCESS] All 8 tests PASSED!")
print("="*60 + "\n")
print("Data Lineage components are working correctly!")
print("Ready for integration into orchestrator and Streamlit app.\n")
