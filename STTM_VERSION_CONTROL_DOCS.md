# STTM Version Control System Documentation

Complete reference guide for versioning STTM transformation rules.

## 📚 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Concepts](#core-concepts)
4. [File Structure](#file-structure)
5. [API Guide](#api-guide)
6. [UI Features](#ui-features)
7. [Workflows](#workflows)
8. [Performance](#performance)
9. [FAQ](#faq)

---

## Overview

STTM Version Control allows you to:

- **Track changes** to transformation rules over time
- **Compare versions** to see what changed
- **Restore previous versions** with one click
- **Audit changes** with user attribution and timestamps
- **Export history** for compliance and analysis

### Key Benefits

✅ **No data loss** - All versions retained (optional cleanup)  
✅ **Easy rollback** - Restore any previous version in seconds  
✅ **Audit trail** - See who changed what and when  
✅ **Comparison** - View unified diffs between versions  
✅ **Production-ready** - Thread-safe, persistent storage  

### Use Cases

**Case 1: Rule Regression**
> A rule change caused unexpected results. Quickly restore the previous version.

**Case 2: User Accountability**
> Track which analyst approved each rule change for compliance.

**Case 3: A/B Testing**
> Save multiple rule versions and compare results.

**Case 4: Disaster Recovery**
> Recover from accidental STTM deletion or corruption.

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────┐
│         Streamlit UI                        │
│  ┌──────────────────────────────────────┐   │
│  │  Version History Dashboard           │   │
│  │  - View all versions                 │   │
│  │  - Compare versions                  │   │
│  │  - Restore with one click            │   │
│  │  - Statistics & analytics            │   │
│  └──────────────────────────────────────┘   │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│    STTMVersionManager (core/sttm_versioning.py)
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │  Save/Restore/Compare Logic          │   │
│  │  - Content hashing (SHA256)          │   │
│  │  - Metadata tracking                 │   │
│  │  - Thread-safe operations            │   │
│  └──────────────────────────────────────┘   │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  File Storage (.audit_logs/sttm_versions/)  │
│                                             │
│  bronze_20241008_123456.json  (v1 content)  │
│  silver_20241008_234567.json  (v2 content)  │
│  gold_20241008_345678.json    (v3 content)  │
│  metadata.json                (index)       │
└─────────────────────────────────────────────┘
```

### Data Flow

```
Agent Generates STTM
        ↓
Save to File (BRONZE_DIR, SILVER_DIR, GOLD_DIR)
        ↓
Call version_mgr.save_version()
        ↓
[Content Unchanged?] ──Yes──→ Return None (skip version)
        │
       No
        ↓
Generate Version ID (layer_TIMESTAMP_HASH)
        ↓
Compute Content Hash (SHA256)
        ↓
Save Version File (.audit_logs/sttm_versions/...)
        ↓
Update metadata.json
        ↓
Return version_id
```

---

## Core Concepts

### Content-Based Versioning

Versions are only created when content actually changes.

```python
# First save - creates version
v1 = version_mgr.save_version(layer="bronze", sttm_content=rules, ...)
# v1 = "bronze_20241008_abc123"

# Same content saved again - no version created
v2 = version_mgr.save_version(layer="bronze", sttm_content=rules, ...)
# v2 = None (no change)

# Different content - creates version
v3 = version_mgr.save_version(layer="bronze", sttm_content=different_rules, ...)
# v3 = "bronze_20241008_def456"
```

### Version ID Format

```
bronze_20241008_T153045_Z123456

┌─────┬──────────┬─────────────┬──────────┐
│Layer│  Date    │   Time      │  Hash    │
├─────┼──────────┼─────────────┼──────────┤
│     │ YYYYMMDD │ THHMMSS_Z   │ Short    │
│     │          │             │ SHA256   │
└─────┴──────────┴─────────────┴──────────┘

Example: bronze_20241008_T153045_Zabc123ab
- Layer: bronze
- Date: 2024-10-08
- Time: 15:30:45 UTC
- Hash: First 8 chars of content hash
```

### Metadata Tracking

Each version stores:
- **version_id** - Unique identifier
- **layer** - "bronze", "silver", or "gold"
- **timestamp** - ISO 8601 UTC
- **user** - Username who made the change
- **description** - What changed and why
- **content_hash** - SHA256 of STTM content
- **row_count** - Number of transformation rules
- **file_size_bytes** - Size of STTM file

---

## File Structure

### Storage Layout

```
.audit_logs/
├── sttm_versions/
│   ├── bronze_20241008_abc123.json
│   ├── bronze_20241009_def456.json
│   ├── silver_20241008_ghi789.json
│   ├── silver_20241009_jkl012.json
│   ├── gold_20241008_mno345.json
│   └── metadata.json
│
├── audit logs/
│   ├── run_abc123_state.json
│   └── ...
```

### Example Version File

```json
{
  "version_id": "bronze_20241008_abc123",
  "layer": "bronze",
  "timestamp": "2024-10-08T15:30:45.123456+00:00",
  "user": "alice",
  "description": "Generated from: Include employees with salary > 50k",
  "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "file_path": "/data/bronze_layer/sttm_run_abc123.json",
  "row_count": 15,
  "file_size_bytes": 3245,
  "sttm_content": {
    "salary_rule": {
      "type": "filter",
      "condition": "salary > 50000"
    },
    "name_rule": {
      "type": "transform",
      "operation": "uppercase"
    }
  }
}
```

### Example Metadata File

```json
[
  {
    "version_id": "bronze_20241008_abc123",
    "layer": "bronze",
    "timestamp": "2024-10-08T15:30:45.123456+00:00",
    "user": "alice",
    "description": "Generated from: Include employees with salary > 50k",
    "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "file_path": "/data/bronze_layer/sttm_run_abc123.json",
    "row_count": 15,
    "file_size_bytes": 3245
  },
  {
    "version_id": "bronze_20241009_def456",
    "layer": "bronze",
    "timestamp": "2024-10-09T10:15:30.654321+00:00",
    "user": "bob",
    "description": "Approved by manager",
    "content_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
    "file_path": "/data/bronze_layer/sttm_run_def456.json",
    "row_count": 17,
    "file_size_bytes": 3512
  }
]
```

---

## API Guide

### Quick Reference

```python
from core.sttm_versioning import get_version_manager

mgr = get_version_manager()

# Save version
version_id = mgr.save_version(layer, content, path, user, description)

# Retrieve
version = mgr.get_version(version_id)

# History
history = mgr.get_version_history(layer=None)

# Compare
diff = mgr.diff_versions(v1_id, v2_id)

# Restore
success = mgr.restore_version(version_id, user, reason)

# Stats
stats = mgr.get_version_stats()

# Change summary
summary = mgr.get_change_summary(version_id)

# Cleanup
deleted = mgr.clear_old_versions(keep_count=10, layer=None)
```

### Method Details

See [STTM_VERSIONING_GUIDE.md](STTM_VERSIONING_GUIDE.md#api-reference) for complete API reference.

---

## UI Features

### 1. Version History Tab

**View all versions with metadata**

- Sortable by date, user, layer
- Expandable cards showing full details
- Quick view of changes from previous version
- Action buttons: View, Restore, Export

### 2. Compare Versions Tab

**Side-by-side version comparison**

- Select two versions
- Show unified diff
- Show full content in JSON viewer
- Highlight added/removed/modified rules

### 3. Statistics Tab

**Analytics and metrics**

- Total versions by layer
- Storage used
- Version timeline
- User contribution chart

### 4. Management Tab

**Administrative functions**

- Cleanup old versions (keep last N)
- Export all versions to JSON
- Advanced options

### 5. Settings Tab

**Configuration and best practices**

- Current settings
- Auto-save status
- Retention policy
- Best practices guide

---

## Workflows

### Workflow 1: Approve and Version STTM

```
1. Agent generates STTM rules
   ↓
2. version_mgr.save_version(..., description="Generated")
   ↓
3. User reviews in Streamlit UI
   ↓
4. User clicks "Approve"
   ↓
5. version_mgr.save_version(..., description="Approved by user")
   ↓
6. STTM is production-ready
```

**Code:**
```python
# Generate
bronze = llm_agent.generate_bronze_sttm(file, intent)
v1 = version_mgr.save_version("bronze", bronze, path, user="system", desc="Generated")

# Approve
v2 = version_mgr.save_version("bronze", bronze, path, user="alice", desc="Approved")
```

---

### Workflow 2: Compare and Restore

```
1. User opens Version Control dashboard
   ↓
2. Selects Compare tab
   ↓
3. Chooses version 1 and version 2
   ↓
4. Views unified diff of changes
   ↓
5. If issues found, selects Restore tab
   ↓
6. Clicks "Restore v1"
   ↓
7. New version created with v1 content
   ↓
8. STTM rolls back to previous version
```

**Code:**
```python
# Compare
diff = version_mgr.diff_versions("bronze_v1", "bronze_v2")
print(diff)

# Restore
success = version_mgr.restore_version(
    "bronze_v1",
    user="alice",
    restore_reason="v2 had issues"
)
```

---

### Workflow 3: Audit Trail

```
1. Query version history
   ↓
2. Filter by user or layer
   ↓
3. Export as JSON
   ↓
4. Share with compliance team
```

**Code:**
```python
# Get history
history = version_mgr.get_version_history()

# Export
with open("sttm_audit.json", "w") as f:
    json.dump(history, f, indent=2, default=str)
```

---

### Workflow 4: Track Rule Changes Over Time

```
1. Version 1: salary > 50k
2. Version 2: salary > 60k (added commission rule)
3. Version 3: salary > 60k (removed commission, added bonus)

Use get_change_summary() to see:
- Version 2: +1 rule (commission)
- Version 3: -1 rule (commission), +1 rule (bonus)
```

**Code:**
```python
summary = version_mgr.get_change_summary("bronze_v3")

print(f"Added: {summary['added_rules']}")
print(f"Removed: {summary['removed_rules']}")
print(f"Modified: {summary['modified_rules']}")
```

---

## Performance

### Storage Usage

```
Per Version:
- JSON file: 2-5 KB (typical STTM with 10-20 rules)
- Metadata entry: ~0.3 KB

100 Versions:
- Total: ~250-500 KB (negligible)

1000 Versions:
- Total: ~2.5-5 MB (still negligible)
```

### Speed

```
Save version: <1 ms (file I/O + hash)
Load version: <1 ms
Diff versions: 1-5 ms (depends on size)
List history: <1 ms
Restore version: 1-2 ms
```

### Thread Safety

All operations are protected by `threading.Lock()` for concurrent access.

```python
# Safe with multiple threads
threads = []
for i in range(10):
    t = threading.Thread(
        target=version_mgr.save_version,
        args=(...,)
    )
    threads.append(t)
    t.start()

for t in threads:
    t.join()

# All saves completed successfully
```

---

## FAQ

### Q: How much disk space does versioning use?

**A:** Minimal. Each version stores just the STTM JSON (typically 2-5 KB). 100 versions = ~250 KB. You can cleanup old versions with `clear_old_versions()`.

---

### Q: Can I version control STTM manually?

**A:** Yes. You can save versions without the agent:

```python
version_mgr.save_version(
    layer="bronze",
    sttm_content=my_rules,
    file_path=str(my_file),
    user="manual",
    description="Manual edit"
)
```

---

### Q: What happens if I restore an old version?

**A:** A new version is created pointing to the old content. The old version remains in history. Restore is non-destructive.

---

### Q: How do I prevent accidental deletes?

**A:** The UI requires confirmation before restore. For API calls, consider adding:

```python
# Add approval step
if not st.session_state.get("version_approved"):
    st.warning("Restore requires approval")
    st.stop()

success = version_mgr.restore_version(...)
```

---

### Q: Can I export versions as CSV?

**A:** Yes, use the Management tab → Export to JSON, then open in Excel. Or programmatically:

```python
version_mgr.export_version_as_csv("bronze_v1", Path("export.csv"))
```

---

### Q: How do I track which user changed what?

**A:** Always pass the `user` parameter:

```python
version_mgr.save_version(
    ...,
    user=current_username,
    description="..."
)
```

Then view in the UI or query:

```python
history = version_mgr.get_version_history()
alice_versions = [v for v in history if v["user"] == "alice"]
```

---

### Q: Can I schedule automatic cleanups?

**A:** Yes, add to your scheduler:

```python
# In your cron job or scheduler
version_mgr.clear_old_versions(keep_count=30, layer=None)
```

---

### Q: What if two users save versions simultaneously?

**A:** Thread-safe by design. All operations use `threading.Lock()`, so concurrent saves are serialized safely.

---

### Q: How do I migrate from an old versioning system?

**A:** Convert your data to the expected format and load directly:

```python
# Manually create version files
for old_version in legacy_versions:
    version = STTMVersion(
        version_id=...,
        layer=...,
        timestamp=...,
        # ... rest of fields
    )
    
    version_file = mgr.versions_dir / f"{version.version_id}.json"
    with open(version_file, "w") as f:
        json.dump(asdict(version), f, indent=2, default=str)
```

---

### Q: Can I disable versioning?

**A:** Yes, just don't call `save_version()`. Or make it conditional:

```python
if ENABLE_VERSIONING:
    version_mgr.save_version(...)
```

---

## Best Practices

1. **Always set user** - Track who made changes
2. **Use descriptive descriptions** - Include business context
3. **Review before restoring** - Use Compare tab first
4. **Cleanup regularly** - Delete versions > 90 days old
5. **Export regularly** - Keep backups for compliance
6. **Test restores** - Verify rollback works before emergency
7. **Use consistent naming** - Keep descriptions consistent

---

## Troubleshooting

### Versions aren't being saved

**Check:**
- Is content actually different? (Same content = no version)
- Is `save_version()` being called?
- Check logs for errors

---

### Restore didn't work

**Remember:**
- Restore creates new version (doesn't overwrite)
- You must load restored content from the version object
- Verify restoration succeeded before reloading STTM

---

### Too many old versions

**Solution:**
```python
deleted = version_mgr.clear_old_versions(keep_count=20)
print(f"Deleted {deleted} versions")
```

---

**Need more help?** Check [STTM_VERSIONING_GUIDE.md](STTM_VERSIONING_GUIDE.md) for integration examples.
