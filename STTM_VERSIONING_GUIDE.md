# STTM Version Control Integration Guide

This guide shows how to integrate STTM versioning into your pipeline.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Integration Points](#integration-points)
3. [Before/After Code Examples](#beforeafter-code-examples)
4. [API Reference](#api-reference)
5. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Import the Version Manager

```python
from core.sttm_versioning import get_version_manager

version_mgr = get_version_manager()
```

### 2. Save a Version When STTM is Generated

```python
# After generating STTM rules
version_id = version_mgr.save_version(
    layer="bronze",
    sttm_content=sttm_rules,
    file_path=str(sttm_file),
    user=current_user,
    description="Generated from business intent: Include salary > $50k"
)

if version_id:
    print(f"✅ Version saved: {version_id}")
else:
    print("⚠️ No changes detected, version not saved")
```

### 3. Add UI Dashboard to Streamlit

```python
# In your streamlit app
from core.sttm_version_ui import render_version_dashboard

if st.session_state.get("show_version_control"):
    render_version_dashboard()
```

---

## Integration Points

### 1. Bronze STTM Generator

**File:** `agents/sttm_generator.py`  
**Function:** `generate_bronze_sttm()`

#### Before

```python
def generate_bronze_sttm(file_path: str, business_intent: str, run_id: str):
    """Generate Bronze STTM rules"""
    
    # ... LLM call to generate STTM ...
    sttm_rules = json.loads(llm_response)
    
    # Save to file
    output_file = BRONZE_DIR / f"sttm_{run_id}.json"
    with open(output_file, "w") as f:
        json.dump(sttm_rules, f)
    
    return output_file
```

#### After

```python
from core.sttm_versioning import get_version_manager

def generate_bronze_sttm(file_path: str, business_intent: str, run_id: str, user: str = "system"):
    """Generate Bronze STTM rules"""
    
    version_mgr = get_version_manager()
    
    # ... LLM call to generate STTM ...
    sttm_rules = json.loads(llm_response)
    
    # Save to file
    output_file = BRONZE_DIR / f"sttm_{run_id}.json"
    with open(output_file, "w") as f:
        json.dump(sttm_rules, f)
    
    # NEW: Save version
    version_id = version_mgr.save_version(
        layer="bronze",
        sttm_content=sttm_rules,
        file_path=str(output_file),
        user=user,
        description=f"Generated for: {business_intent}"
    )
    
    if version_id:
        print(f"✅ Bronze STTM version: {version_id}")
    
    return output_file
```

---

### 2. Silver STTM Generator

**File:** `agents/sttm_generator.py`  
**Function:** `generate_silver_sttm()`

#### Before

```python
def generate_silver_sttm(bronze_sttm: dict, business_intent: str, run_id: str):
    """Generate Silver STTM rules from Bronze"""
    
    # ... Process bronze STTM ...
    silver_rules = process_rules(bronze_sttm)
    
    output_file = SILVER_DIR / f"sttm_{run_id}.json"
    with open(output_file, "w") as f:
        json.dump(silver_rules, f)
    
    return output_file
```

#### After

```python
from core.sttm_versioning import get_version_manager

def generate_silver_sttm(bronze_sttm: dict, business_intent: str, run_id: str, user: str = "system"):
    """Generate Silver STTM rules from Bronze"""
    
    version_mgr = get_version_manager()
    
    # ... Process bronze STTM ...
    silver_rules = process_rules(bronze_sttm)
    
    output_file = SILVER_DIR / f"sttm_{run_id}.json"
    with open(output_file, "w") as f:
        json.dump(silver_rules, f)
    
    # NEW: Save version
    version_id = version_mgr.save_version(
        layer="silver",
        sttm_content=silver_rules,
        file_path=str(output_file),
        user=user,
        description=f"Processed from bronze: {business_intent}"
    )
    
    if version_id:
        print(f"✅ Silver STTM version: {version_id}")
    
    return output_file
```

---

### 3. Gold STTM Generator

**File:** `agents/sttm_generator.py`  
**Function:** `generate_gold_sttm()`

#### Before

```python
def generate_gold_sttm(silver_sttm: dict, business_intent: str, run_id: str):
    """Generate Gold STTM rules from Silver"""
    
    # ... Final processing ...
    gold_rules = finalize_rules(silver_sttm)
    
    output_file = GOLD_DIR / f"sttm_{run_id}.json"
    with open(output_file, "w") as f:
        json.dump(gold_rules, f)
    
    return output_file
```

#### After

```python
from core.sttm_versioning import get_version_manager

def generate_gold_sttm(silver_sttm: dict, business_intent: str, run_id: str, user: str = "system"):
    """Generate Gold STTM rules from Silver"""
    
    version_mgr = get_version_manager()
    
    # ... Final processing ...
    gold_rules = finalize_rules(silver_sttm)
    
    output_file = GOLD_DIR / f"sttm_{run_id}.json"
    with open(output_file, "w") as f:
        json.dump(gold_rules, f)
    
    # NEW: Save version
    version_id = version_mgr.save_version(
        layer="gold",
        sttm_content=gold_rules,
        file_path=str(output_file),
        user=user,
        description=f"Final rules for: {business_intent}"
    )
    
    if version_id:
        print(f"✅ Gold STTM version: {version_id}")
    
    return output_file
```

---

### 4. Manual STTM Approval in Streamlit

**File:** `app/streamlit_app.py`

#### Before

```python
def approve_sttm():
    """User approves STTM rules"""
    
    st.markdown("## Approve STTM Rules")
    
    if st.button("✅ Approve"):
        # Save approved STTM
        save_approved_sttm(sttm_rules)
        st.success("STTM approved!")
```

#### After

```python
from core.sttm_versioning import get_version_manager

def approve_sttm():
    """User approves STTM rules"""
    
    version_mgr = get_version_manager()
    st.markdown("## Approve STTM Rules")
    
    # NEW: Get username from session
    if "username" not in st.session_state:
        st.session_state.username = st.text_input("Your name:")
    
    if st.button("✅ Approve"):
        # Save approved STTM
        save_approved_sttm(sttm_rules)
        
        # NEW: Version the approved rules
        version_id = version_mgr.save_version(
            layer=current_layer,
            sttm_content=sttm_rules,
            file_path=str(approved_path),
            user=st.session_state.username,
            description="User approved STTM rules"
        )
        
        st.success(f"✅ STTM approved! Version: {version_id}")
```

---

### 5. Add Version Control Dashboard to Streamlit

**File:** `app/streamlit_app.py`

```python
import streamlit as st
from core.sttm_version_ui import render_version_dashboard

def main():
    st.set_page_config(page_title="Pipeline", layout="wide")
    
    # Sidebar navigation
    page = st.sidebar.radio(
        "Pages",
        ["Upload", "Profile", "STTM Editor", "Report", "Version Control"]
    )
    
    if page == "Version Control":
        render_version_dashboard()
    
    elif page == "STTM Editor":
        # ... existing STTM editor code ...
        pass
    
    # ... rest of your app ...

if __name__ == "__main__":
    main()
```

---

### 6. Restore STTM from Previous Version

```python
from core.sttm_versioning import get_version_manager

def restore_sttm_from_version(version_id: str, user: str = "system"):
    """Restore STTM rules from a previous version"""
    
    version_mgr = get_version_manager()
    
    # Get the old version
    old_version = version_mgr.get_version(version_id)
    if not old_version:
        print(f"❌ Version {version_id} not found")
        return False
    
    # Restore to current layer
    success = version_mgr.restore_version(
        version_id=version_id,
        user=user,
        restore_reason="User restored from version history"
    )
    
    if success:
        print(f"✅ Restored version {version_id}")
        
        # Save restored rules to active STTM file
        output_path = get_current_sttm_path(old_version.layer)
        with open(output_path, "w") as f:
            json.dump(old_version.sttm_content, f, indent=2)
        
        return True
    else:
        print(f"❌ Failed to restore {version_id}")
        return False
```

---

### 7. Export STTM History for Audit

```python
from core.sttm_versioning import get_version_manager
from pathlib import Path

def export_sttm_audit_report(layer: str = None, output_dir: Path = None):
    """Export version history as audit report"""
    
    version_mgr = get_version_manager()
    
    # Get history
    history = version_mgr.get_version_history(layer)
    
    if not history:
        print("No versions to export")
        return
    
    # Export as JSON
    output_dir = output_dir or Path("audit_exports")
    output_dir.mkdir(exist_ok=True)
    
    report_file = output_dir / f"sttm_history_{layer or 'all'}.json"
    
    with open(report_file, "w") as f:
        json.dump(history, f, indent=2, default=str)
    
    print(f"✅ Exported to {report_file}")
    
    # Also export as CSV for Excel
    import csv
    
    csv_file = output_dir / f"sttm_history_{layer or 'all'}.csv"
    
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["version_id", "layer", "timestamp", "user", "description", "row_count"]
        )
        writer.writeheader()
        writer.writerows(history)
    
    print(f"✅ Also exported to {csv_file}")
```

---

## API Reference

### STTMVersionManager Class

#### `save_version(layer, sttm_content, file_path, user="system", description="Auto-saved")`

Save a new version of STTM rules.

**Parameters:**
- `layer` (str): "bronze", "silver", or "gold"
- `sttm_content` (dict): The STTM rules
- `file_path` (str): Path where rules are stored
- `user` (str): Username making the change
- `description` (str): Description of changes

**Returns:** version_id (str) or None if no changes

**Example:**
```python
version_id = version_mgr.save_version(
    layer="bronze",
    sttm_content={"col1": "rule1"},
    file_path="/path/to/sttm.json",
    user="alice",
    description="Added salary rule"
)
```

---

#### `get_version(version_id)`

Retrieve a specific version.

**Parameters:**
- `version_id` (str): The version ID to retrieve

**Returns:** STTMVersion object or None

**Example:**
```python
version = version_mgr.get_version("bronze_20241008_abc123")
print(version.description)
print(version.sttm_content)
```

---

#### `get_version_history(layer=None)`

Get all versions, optionally filtered by layer.

**Parameters:**
- `layer` (str, optional): "bronze", "silver", "gold", or None for all

**Returns:** List of version metadata dicts, sorted newest first

**Example:**
```python
bronze_history = version_mgr.get_version_history("bronze")
for v in bronze_history:
    print(f"{v['timestamp']}: {v['description']}")
```

---

#### `diff_versions(version_id_1, version_id_2)`

Compare two versions and show differences.

**Parameters:**
- `version_id_1` (str): Older version
- `version_id_2` (str): Newer version

**Returns:** Unified diff string

**Example:**
```python
diff = version_mgr.diff_versions("bronze_v1", "bronze_v2")
print(diff)
```

---

#### `restore_version(version_id, user="system", restore_reason="")`

Restore STTM rules from a previous version.

**Parameters:**
- `version_id` (str): Version to restore
- `user` (str): User performing restore
- `restore_reason` (str): Why it's being restored

**Returns:** True if successful

**Example:**
```python
success = version_mgr.restore_version(
    version_id="bronze_20241001",
    user="alice",
    restore_reason="Previous version had better results"
)
```

---

#### `get_change_summary(version_id)`

Get detailed summary of changes in a version.

**Parameters:**
- `version_id` (str): Version to summarize

**Returns:** Dict with added_rules, removed_rules, modified_rules, etc.

**Example:**
```python
summary = version_mgr.get_change_summary("bronze_v2")
print(f"Added: {summary['added_rules']}")
print(f"Removed: {summary['removed_rules']}")
print(f"Modified: {summary['modified_rules']}")
```

---

#### `get_version_stats()`

Get statistics about all versions.

**Parameters:** None

**Returns:** Dict with total_versions, layers, versions_by_layer, etc.

**Example:**
```python
stats = version_mgr.get_version_stats()
print(f"Total versions: {stats['total_versions']}")
print(f"Versions per layer: {stats['versions_by_layer']}")
```

---

#### `clear_old_versions(keep_count=10, layer=None)`

Remove old versions, keeping only most recent N.

**Parameters:**
- `keep_count` (int): How many recent versions to keep
- `layer` (str, optional): Only delete from this layer

**Returns:** Number of versions deleted

**Example:**
```python
deleted = version_mgr.clear_old_versions(keep_count=5, layer="bronze")
print(f"Deleted {deleted} old versions")
```

---

## Troubleshooting

### Q: My STTM change isn't being saved as a version

**A:** This is normal! Versioning detects **actual changes** using content hashing. If you save the same STTM twice, only the first time creates a version.

To force a version:
```python
# Always creates version, even if content is identical
version_mgr.save_version(..., description="Forced version")
```

---

### Q: How do I see what changed between two versions?

**A:** Use the Compare tab in the Version Control dashboard, or call diff:

```python
diff = version_mgr.diff_versions("v1", "v2")
print(diff)
```

---

### Q: I restored a version but the old STTM didn't get reloaded

**A:** Restoring creates a new version, but doesn't automatically reload the active STTM file. You must:

1. Call `restore_version()` to create the restore entry
2. Manually load the restored content from the old version
3. Save it to the current STTM file path

```python
old_version = version_mgr.get_version("bronze_v1")
# ... load old_version.sttm_content and save to active file ...
```

---

### Q: My version storage is using too much disk space

**A:** Use `clear_old_versions()` to delete old versions:

```python
# Keep only last 10 versions of each layer
for layer in ["bronze", "silver", "gold"]:
    deleted = version_mgr.clear_old_versions(keep_count=10, layer=layer)
    print(f"Deleted {deleted} versions from {layer}")
```

---

### Q: Can I export version history for compliance/audit?

**A:** Yes! The `get_version_history()` returns all metadata, and the UI has an "Export to JSON" button:

```python
history = version_mgr.get_version_history()

# Export as JSON
with open("sttm_audit.json", "w") as f:
    json.dump(history, f, indent=2, default=str)
```

---

### Q: How do I track who made what changes?

**A:** Pass the `user` parameter when saving versions:

```python
version_mgr.save_version(
    layer="bronze",
    sttm_content=rules,
    file_path=path,
    user="alice",  # Track the user
    description="Fixed salary rule"
)
```

Then view in the dashboard to see version history by user.

---

## Best Practices

1. **Always include a user:** Pass `user=current_username` to track who changed what
2. **Descriptive messages:** Use clear descriptions for each version
3. **Review before restoring:** Use the Compare tab to review changes before reverting
4. **Regular backups:** Export version history monthly
5. **Cleanup regularly:** Delete versions older than 90 days to save space

---

## Example: Complete STTM Approval Workflow

```python
from core.sttm_versioning import get_version_manager
import streamlit as st
import json

def complete_sttm_workflow():
    """Full example of STTM with version control"""
    
    version_mgr = get_version_manager()
    
    # Step 1: Generate Bronze STTM
    bronze_rules = llm_agent.generate_bronze_sttm(file_path, business_intent)
    
    version_mgr.save_version(
        layer="bronze",
        sttm_content=bronze_rules,
        file_path=str(bronze_sttm_path),
        user=st.session_state.username,
        description=f"Generated: {business_intent}"
    )
    
    # Step 2: User reviews and approves
    if st.button("✅ Approve Bronze"):
        version_mgr.save_version(
            layer="bronze",
            sttm_content=bronze_rules,
            file_path=str(bronze_sttm_path),
            user=st.session_state.username,
            description="Approved by user"
        )
    
    # Step 3: Generate Silver from Bronze
    silver_rules = llm_agent.generate_silver_sttm(bronze_rules, business_intent)
    
    version_mgr.save_version(
        layer="silver",
        sttm_content=silver_rules,
        file_path=str(silver_sttm_path),
        user=st.session_state.username,
        description="Generated from approved bronze rules"
    )
    
    # Step 4: Show history
    if st.button("📚 Show Version History"):
        history = version_mgr.get_version_history()
        st.dataframe(history)
    
    # Step 5: Option to restore
    if st.button("⏮️ Restore Previous Version"):
        versions = version_mgr.get_version_history("bronze")
        selected = st.selectbox("Select version:", [v["version_id"] for v in versions])
        
        if st.button("Confirm Restore"):
            version_mgr.restore_version(
                version_id=selected,
                user=st.session_state.username,
                restore_reason="User selected from history"
            )
            st.success("Restored!")
```

---

**That's it!** You now have complete version control for STTM rules. 🎉
