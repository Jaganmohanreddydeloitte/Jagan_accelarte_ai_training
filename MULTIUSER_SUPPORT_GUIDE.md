# Multi-User Support for IDAMP Pipeline

Complete guide to adding concurrent user support with isolated data, authentication, and run history.

---

## Overview

The multi-user system (`core/user_manager.py` + `core/streamlit_multiuser.py`) enables multiple users to run the pipeline simultaneously without conflicts. Each user gets:

✅ **Isolated data folders** — No cross-contamination
✅ **Separate run history** — Track individual runs
✅ **Session management** — Auto login/logout
✅ **User statistics** — Quality scores, completion rates
✅ **Quality gates by phase** — Streamlit UI integration

---

## Architecture

### Directory Structure

```
users/
  ├── users.json                    # All registered users
  ├── alice/
  │   ├── data/
  │   │   ├── landing/              # Uploaded CSVs
  │   │   ├── bronze_layer/         # Bronze Parquet
  │   │   ├── silver_layer/         # Silver Parquet
  │   │   ├── gold_layer/           # Gold Parquet
  │   │   ├── profiles/             # Data profiles
  │   │   ├── sttm/                 # STTM rules
  │   │   └── traces/               # Agent traces
  │   ├── reports/                  # Generated reports
  │   ├── audit_logs/               # Audit trail
  │   └── run_history/              # Run records
  │
  ├── bob/
  │   ├── data/
  │   ├── reports/
  │   ├── audit_logs/
  │   └── run_history/
  │
  └── charlie/
      └── ...
```

### Session Flow

```
1. User visits Streamlit app
   ↓
2. render_login_page() shown
   ↓
3. User enters username
   ↓
4. require_authentication() calls login()
   ↓
5. UserManager.register_user() creates directories (if new)
   ↓
6. StreamlitMultiUserSession sets session state
   ↓
7. Main app loads with user's isolated paths
   ↓
8. Pipeline runs, records to user's run_history/
   ↓
9. Logout clears session state
```

---

## Core Components

### 1. UserManager Class

```python
from core.user_manager import get_user_manager

manager = get_user_manager()  # Singleton instance

# Register user (creates directories if new)
manager.register_user("alice")

# Get user's paths
paths = manager.get_paths_for_user("alice")
bronze_dir = paths["bronze"]
reports_dir = paths["reports"]

# Record pipeline run
manager.record_run_start("alice", "run-001", ["file1.csv"])
manager.record_run_progress("alice", "run-001", "bronze", ["bronze.parquet"])
manager.record_run_complete("alice", "run-001", ["report.html"], 95.0)

# Get run history
runs = manager.get_user_runs("alice", limit=10)
run = manager.get_user_run("alice", "run-001")

# Get statistics
stats = manager.get_user_stats("alice")
# → {"total_runs": 5, "completed": 4, "failed": 1, "avg_quality_score": 92.5}
```

### 2. RunRecord Dataclass

```python
@dataclass
class RunRecord:
    run_id: str              # Unique run ID
    username: str            # Owner
    started_at: str          # ISO timestamp
    completed_at: Optional[str]  # ISO timestamp (null if running)
    status: str              # "running", "completed", "failed"
    phase: str               # "bronze", "silver", "gold", "report"
    input_files: List[str]   # Input CSVs
    output_files: List[str]  # Output Parquets/Reports
    quality_score: Optional[float]  # 0-100
    error_message: Optional[str]    # If failed
```

### 3. StreamlitMultiUserSession Class

```python
from core.streamlit_multiuser import StreamlitMultiUserSession

# Initialize session state
StreamlitMultiUserSession.initialize_session()

# Login user
StreamlitMultiUserSession.login("alice")

# Check authentication
if StreamlitMultiUserSession.is_authenticated():
    username = StreamlitMultiUserSession.get_current_username()
    paths = StreamlitMultiUserSession.get_user_paths()

# Set/get current run
StreamlitMultiUserSession.set_current_run("run-001")
run_id = StreamlitMultiUserSession.get_current_run()

# Logout
StreamlitMultiUserSession.logout()
```

---

## Implementation Guide

### Step 1: Add Login Page

```python
# In app/streamlit_app.py (top of file)
from core.streamlit_multiuser import require_authentication, render_login_page

# THIS MUST BE FIRST
username = require_authentication()
if username is None:
    render_login_page()
    st.stop()

# Now rest of app only runs if authenticated
st.title(f"🏅 IDAMP - {username}'s Pipeline")
```

### Step 2: Use User Paths

```python
from core.streamlit_multiuser import StreamlitMultiUserSession

# Get user's isolated paths
username = StreamlitMultiUserSession.get_current_username()
user_paths = StreamlitMultiUserSession.get_user_paths()

# Upload files to user's landing directory
uploaded_files = st.file_uploader(
    "Upload CSV files",
    type=["csv"],
    accept_multiple_files=True,
)

if uploaded_files:
    landing_dir = user_paths["landing"]
    for file in uploaded_files:
        filepath = landing_dir / file.name
        filepath.write_bytes(file.getbuffer())
```

### Step 3: Record Run Progress

```python
from core.user_manager import get_user_manager

manager = get_user_manager()
username = StreamlitMultiUserSession.get_current_username()

# Start run
run_id = generate_run_id()
manager.record_run_start(username, run_id, input_files)
StreamlitMultiUserSession.set_current_run(run_id)

# Execute phases
try:
    # Bronze phase
    bronze_paths = execute_bronze(...)
    manager.record_run_progress(username, run_id, "bronze", bronze_paths)
    
    # Silver phase
    silver_paths = execute_silver(...)
    manager.record_run_progress(username, run_id, "silver", silver_paths, quality_score=90.0)
    
    # Gold phase
    gold_paths = execute_gold(...)
    manager.record_run_progress(username, run_id, "gold", gold_paths, quality_score=95.0)
    
    # Report
    report_path = generate_report(...)
    manager.record_run_complete(username, run_id, [report_path], 95.0)

except Exception as e:
    manager.record_run_failed(username, run_id, current_phase, str(e))
    raise

finally:
    StreamlitMultiUserSession.clear_current_run()
```

### Step 4: Display Run History

```python
from core.streamlit_multiuser import render_user_stats, render_run_history

username = StreamlitMultiUserSession.get_current_username()

# Show statistics
render_user_stats(username)

# Show run history
st.markdown("---")
render_run_history(username, limit=10)
```

### Step 5: Add Quality Gate Display

```python
from core.streamlit_multiuser import render_phase_with_quality_gate
from core.data_quality import DataQualityChecker

# After bronze processing
checker = DataQualityChecker(run_id, "bronze")
quality = checker.validate(df_bronze, min_score=85.0)

passed = render_phase_with_quality_gate(
    phase_name="Bronze",
    phase_number=1,
    quality_score=quality.overall_score,
    min_quality=85.0,
)

if not passed:
    st.error("Pipeline stopped due to quality gate failure")
    return
```

---

## Example: Multi-User Streamlit App

```python
import streamlit as st
from core.streamlit_multiuser import (
    require_authentication,
    render_login_page,
    render_user_navbar,
    render_user_stats,
    render_run_history,
    render_phase_with_quality_gate,
    StreamlitMultiUserSession,
)
from core.user_manager import get_user_manager

# Initialize
st.set_page_config(page_title="IDAMP Multi-User", layout="wide")

# Authentication (MUST BE FIRST)
username = require_authentication()

# Render navbar
render_user_navbar()

# Tabs
tab1, tab2, tab3 = st.tabs(["Pipeline", "History", "Settings"])

with tab1:
    st.title("🚀 Pipeline Execution")
    
    # Get user's paths
    manager = get_user_manager()
    user_paths = StreamlitMultiUserSession.get_user_paths()
    
    # Upload files
    uploaded_files = st.file_uploader("Upload CSV files", type=["csv"], accept_multiple_files=True)
    if uploaded_files:
        for file in uploaded_files:
            filepath = user_paths["landing"] / file.name
            filepath.write_bytes(file.getbuffer())
        st.success(f"✅ Uploaded {len(uploaded_files)} files")
    
    # Start pipeline
    if st.button("🚀 Start Workflow"):
        run_id = generate_run_id()
        manager.record_run_start(username, run_id, [...])
        StreamlitMultiUserSession.set_current_run(run_id)
        
        # Execute phases
        try:
            # Bronze
            bronze_output = execute_bronze(...)
            quality_bronze = check_quality(bronze_output, min_score=85.0)
            passed = render_phase_with_quality_gate("Bronze", 1, quality_bronze.overall_score, 85.0)
            if not passed:
                raise ValueError("Bronze quality failed")
            
            # Silver
            silver_output = execute_silver(...)
            quality_silver = check_quality(silver_output, min_score=90.0)
            passed = render_phase_with_quality_gate("Silver", 2, quality_silver.overall_score, 90.0)
            if not passed:
                raise ValueError("Silver quality failed")
            
            # Gold
            gold_output = execute_gold(...)
            quality_gold = check_quality(gold_output, min_score=95.0)
            passed = render_phase_with_quality_gate("Gold", 3, quality_gold.overall_score, 95.0)
            if not passed:
                raise ValueError("Gold quality failed")
            
            # Report
            report = generate_report(...)
            manager.record_run_complete(username, run_id, [report], quality_gold.overall_score)
            st.success("✅ Pipeline completed successfully!")
        
        except Exception as e:
            manager.record_run_failed(username, run_id, "pipeline", str(e))
            st.error(f"❌ Pipeline failed: {e}")
        
        finally:
            StreamlitMultiUserSession.clear_current_run()

with tab2:
    st.title("📜 Run History")
    render_user_stats(username)
    st.markdown("---")
    render_run_history(username, limit=20)

with tab3:
    st.title("⚙️ Settings")
    st.write(f"**Username:** {username}")
    
    if st.button("Delete Old Runs (>30 days)"):
        deleted = manager.cleanup_old_runs(username, days_to_keep=30)
        st.info(f"🗑️ Deleted {deleted} old runs")
```

---

## Data Model

### users.json

```json
{
  "users": [
    {
      "username": "alice",
      "created_at": "2024-01-10T10:00:00Z",
      "last_login": "2024-01-10T15:30:00Z"
    },
    {
      "username": "bob",
      "created_at": "2024-01-10T11:00:00Z",
      "last_login": "2024-01-10T14:00:00Z"
    }
  ]
}
```

### users/alice/run_history/run-001.json

```json
{
  "run_id": "run-001",
  "username": "alice",
  "started_at": "2024-01-10T15:00:00Z",
  "completed_at": "2024-01-10T15:45:00Z",
  "status": "completed",
  "phase": "report",
  "input_files": ["customers.csv"],
  "output_files": ["report.html"],
  "quality_score": 95.0,
  "error_message": null
}
```

---

## Usage Examples

### Example 1: Simple Login

```python
from core.streamlit_multiuser import require_authentication

# At top of Streamlit app
username = require_authentication()

st.write(f"Welcome, {username}!")
```

### Example 2: User Paths in Pipeline

```python
from core.streamlit_multiuser import StreamlitMultiUserSession
from core.user_manager import get_user_manager

username = StreamlitMultiUserSession.get_current_username()
paths = StreamlitMultiUserSession.get_user_paths()

# Read/write files using user's isolated paths
df = pd.read_csv(paths["landing"] / "data.csv")
df.to_parquet(paths["bronze"] / "output.parquet")
```

### Example 3: Record Run

```python
manager = get_user_manager()
username = StreamlitMultiUserSession.get_current_username()

# Start
manager.record_run_start(username, "run-001", ["input.csv"])

# Progress
manager.record_run_progress(username, "run-001", "bronze", ["bronze.parquet"], 90.0)

# Complete
manager.record_run_complete(username, "run-001", ["report.html"], 95.0)
```

### Example 4: Show History

```python
from core.streamlit_multiuser import render_run_history, render_user_stats

username = StreamlitMultiUserSession.get_current_username()

render_user_stats(username)
render_run_history(username, limit=10)
```

### Example 5: Quality Gate

```python
from core.streamlit_multiuser import render_phase_with_quality_gate

passed = render_phase_with_quality_gate(
    phase_name="Bronze",
    phase_number=1,
    quality_score=92.5,
    min_quality=85.0,
)

if not passed:
    st.stop()  # Stop execution if quality failed
```

---

## Testing

### Run User Manager Tests

```bash
pytest tests/test_user_manager.py -v

# Output:
# 25 passed in 1.20s ✅

# Test coverage:
# - User registration (valid/invalid usernames)
# - Directory creation
# - Run recording (start/progress/complete/failed)
# - Run history queries
# - User statistics
# - Filtering and limiting
```

---

## Configuration

### Username Validation

- Minimum 3 characters
- Alphanumeric + underscore + dash
- Case-sensitive
- No spaces

**Valid:** `alice`, `user_123`, `bob-smith`
**Invalid:** `ab`, `user@123`, `alice smith`

---

## Best Practices

1. **Call require_authentication() first**
   ```python
   # CORRECT - at very top
   username = require_authentication()
   
   # WRONG - after other code
   st.title("App")
   username = require_authentication()  # Too late!
   ```

2. **Always use user paths**
   ```python
   # CORRECT - use user-isolated path
   df.to_parquet(user_paths["bronze"] / "output.parquet")
   
   # WRONG - hard-coded path used by all users
   df.to_parquet("data/bronze/output.parquet")
   ```

3. **Record all run events**
   ```python
   # CORRECT - full tracking
   manager.record_run_start(username, run_id, input_files)
   # ... process ...
   manager.record_run_complete(username, run_id, output_files, quality_score)
   
   # WRONG - no tracking
   # ... process without recording ...
   ```

4. **Clean up old runs**
   ```python
   # Periodically delete old runs to save space
   manager.cleanup_old_runs(username, days_to_keep=30)
   ```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Invalid username" | Too short or special chars | Use 3+ alphanumeric chars |
| "Permission denied" | Path ownership | Recreate user directory |
| "Run not found" | Wrong username or run_id | Check spelling in history |
| Multiple users see same data | Not using user_paths | Switch to user-isolated paths |
| Login page loops | require_authentication() not first | Move to top of app |

---

## Summary

✅ **Multi-user system provides:**
- User registration with isolated directories
- Run history tracking per user
- Session management in Streamlit
- Quality gate displays
- User statistics dashboard
- 25 comprehensive passing tests

**You can now:**
1. ✅ Run multiple users simultaneously
2. ✅ Isolate data per user
3. ✅ Track individual run histories
4. ✅ Display quality gates in UI
5. ✅ Manage user sessions

---

See [core/user_manager.py](core/user_manager.py) and [core/streamlit_multiuser.py](core/streamlit_multiuser.py) for complete implementation.
