# Admin Dashboard Integration Guide

Complete guide for integrating the admin dashboard into your pipeline.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Integration Points](#integration-points)
3. [Recording Metrics](#recording-metrics)
4. [Admin Page Setup](#admin-page-setup)
5. [Authentication](#authentication)
6. [Dashboard Features](#dashboard-features)
7. [Advanced Configuration](#advanced-configuration)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Step 1: Update requirements.txt

Add new dependencies:

```
psutil>=5.9.0
plotly>=5.0.0
```

### Step 2: Initialize Admin Authenticator

```python
from core.admin_auth import AdminAuthenticator

# Creates .auth/admins.json with default credentials
authenticator = AdminAuthenticator()

# Default login: username="admin", password="admin123"
# CHANGE THIS IN PRODUCTION!
```

### Step 3: Add Admin Page to Streamlit

In your main `app/streamlit_app.py`:

```python
import streamlit as st
from core.admin_dashboard import render_admin_dashboard

def main():
    st.set_page_config(page_title="Pipeline", layout="wide")
    
    # Navigation
    page = st.sidebar.radio(
        "Pages",
        ["Upload", "Profile", "STTM Editor", "Report", "Admin Dashboard"]
    )
    
    if page == "Admin Dashboard":
        render_admin_dashboard()
    
    elif page == "Upload":
        # ... your existing code ...
        pass

if __name__ == "__main__":
    main()
```

### Step 4: Record Metrics During Runs

Wrap your agent calls:

```python
from core.admin_metrics import get_pipeline_metrics
import time

metrics = get_pipeline_metrics()

# Before running agent
start_time = time.time()

try:
    result = agent.run(...)
    duration = time.time() - start_time
    
    # Record success
    metrics.record_agent_run(
        agent_name="bronze_profiler",
        run_id=run_id,
        duration_seconds=duration,
        status="success",
        tokens_used=tokens_used,
        api_calls=api_calls
    )
    
except Exception as e:
    duration = time.time() - start_time
    
    # Record failure
    metrics.record_agent_run(
        agent_name="bronze_profiler",
        run_id=run_id,
        duration_seconds=duration,
        status="failed",
        error_message=str(e)
    )
    raise
```

---

## Integration Points

### 1. Profile Agent

**File:** `agents/profiler.py`

#### Before

```python
def profile_dataset(file_path: str, run_id: str):
    """Profile dataset"""
    
    profile = analyze(file_path)
    
    return profile
```

#### After

```python
from core.admin_metrics import get_pipeline_metrics
import time

def profile_dataset(file_path: str, run_id: str):
    """Profile dataset"""
    
    metrics = get_pipeline_metrics()
    start_time = time.time()
    
    try:
        profile = analyze(file_path)
        duration = time.time() - start_time
        
        metrics.record_agent_run(
            agent_name="profiler",
            run_id=run_id,
            duration_seconds=duration,
            status="success"
        )
        
        return profile
        
    except Exception as e:
        duration = time.time() - start_time
        
        metrics.record_agent_run(
            agent_name="profiler",
            run_id=run_id,
            duration_seconds=duration,
            status="failed",
            error_message=str(e)
        )
        
        raise
```

---

### 2. STTM Generator

**File:** `agents/sttm_generator.py`

#### Before

```python
def generate_bronze_sttm(file_path: str, business_intent: str, run_id: str):
    """Generate Bronze STTM"""
    
    sttm = llm_agent.generate_sttm(file_path, business_intent)
    
    return sttm
```

#### After

```python
from core.admin_metrics import get_pipeline_metrics
import time

def generate_bronze_sttm(file_path: str, business_intent: str, run_id: str):
    """Generate Bronze STTM"""
    
    metrics = get_pipeline_metrics()
    start_time = time.time()
    
    try:
        sttm = llm_agent.generate_sttm(file_path, business_intent)
        duration = time.time() - start_time
        
        # Count API calls (if tracking)
        api_calls = llm_agent.api_call_count
        
        metrics.record_agent_run(
            agent_name="sttm_generator_bronze",
            run_id=run_id,
            duration_seconds=duration,
            status="success",
            api_calls=api_calls
        )
        
        return sttm
        
    except Exception as e:
        duration = time.time() - start_time
        
        metrics.record_agent_run(
            agent_name="sttm_generator_bronze",
            run_id=run_id,
            duration_seconds=duration,
            status="failed",
            error_message=str(e)
        )
        
        raise
```

---

### 3. Reporter Agent

**File:** `agents/reporter.py`

#### Before

```python
def generate_report(gold_data: dict, run_id: str):
    """Generate final report"""
    
    report = create_report(gold_data)
    
    return report
```

#### After

```python
from core.admin_metrics import get_pipeline_metrics
import time

def generate_report(gold_data: dict, run_id: str):
    """Generate final report"""
    
    metrics = get_pipeline_metrics()
    start_time = time.time()
    
    try:
        report = create_report(gold_data)
        duration = time.time() - start_time
        
        metrics.record_agent_run(
            agent_name="reporter",
            run_id=run_id,
            duration_seconds=duration,
            status="success"
        )
        
        return report
        
    except Exception as e:
        duration = time.time() - start_time
        
        metrics.record_agent_run(
            agent_name="reporter",
            run_id=run_id,
            duration_seconds=duration,
            status="failed",
            error_message=str(e)
        )
        
        raise
```

---

## Recording Metrics

### Basic Recording

```python
from core.admin_metrics import get_pipeline_metrics

metrics = get_pipeline_metrics()

# Record a successful run
metrics.record_agent_run(
    agent_name="my_agent",
    run_id="run_abc123",
    duration_seconds=45.5,
    status="success"
)
```

### With Full Details

```python
metrics.record_agent_run(
    agent_name="sttm_generator",
    run_id="run_abc123",
    duration_seconds=45.5,
    status="success",
    tokens_used=1250,      # LLM tokens consumed
    api_calls=2,            # Number of API calls
    error_message=None      # Only for failed runs
)
```

### Recording Failures

```python
metrics.record_agent_run(
    agent_name="sttm_generator",
    run_id="run_abc123",
    duration_seconds=10.5,
    status="failed",
    error_message="Invalid JSON in LLM response: expected 'rules' key"
)
```

---

## Admin Page Setup

### Option 1: Separate Admin Page

Create `pages/admin.py`:

```python
import streamlit as st
from core.admin_dashboard import render_admin_dashboard

st.set_page_config(page_title="Admin", layout="wide", initial_sidebar_state="collapsed")

render_admin_dashboard()
```

Run with: `streamlit run pages/admin.py`

### Option 2: Integrated in Main App

In your main `app/streamlit_app.py`:

```python
import streamlit as st
from core.admin_dashboard import render_admin_dashboard

def main():
    st.set_page_config(page_title="Pipeline", layout="wide")
    
    page = st.sidebar.radio("Navigate", ["Dashboard", "Admin", "Reports"])
    
    if page == "Admin":
        render_admin_dashboard()
    else:
        # ... other pages ...
        pass

if __name__ == "__main__":
    main()
```

---

## Authentication

### Default Credentials

After first run, `.auth/admins.json` contains:

```json
{
  "admins": [
    {
      "username": "admin",
      "password_hash": "...",
      "full_name": "System Administrator",
      "created_at": "2024-10-08T..."
    }
  ]
}
```

**Default:** username=`admin`, password=`admin123`

### Change Default Password

```python
from core.admin_auth import AdminAuthenticator

auth = AdminAuthenticator()
success = auth.change_password("admin", "admin123", "NewSecurePassword123")

if success:
    print("Password changed!")
```

### Add New Admin User

```python
from core.admin_auth import AdminAuthenticator

auth = AdminAuthenticator()
success = auth.add_admin("alice", "SecurePass123", "Alice Smith")

if success:
    print("Admin 'alice' created!")
```

### Session Timeout

Default: 8 hours

Change in `core/admin_auth.py`:

```python
self.session_timeout = timedelta(hours=4)  # 4 hours
```

---

## Dashboard Features

### 1. System Health Tab

**Shows:**
- CPU usage percentage
- Memory usage percentage
- Disk usage percentage
- Available memory (MB)
- Free disk space (GB)
- Process count
- Overall health status
- Issues and alerts
- CPU and Memory trends

**Thresholds:**
- CPU Warning: > 80%
- Memory Warning: > 85%
- Disk Critical: > 90%
- Low Memory: < 512 MB available

### 2. Pipeline Runs Tab

**Shows:**
- Total pipeline runs
- Successful runs
- Failed runs
- Success rate
- Per-agent performance table
- Agent success rate comparison chart

**Metrics tracked:**
- Run count
- Success/failure count
- Average duration
- Total API calls
- Total tokens used
- Error rate

### 3. Performance Tab

**Shows:**
- Average run duration
- Total time spent
- Total API calls
- API calls per run
- Agent duration comparison

**Useful for:**
- Identifying slow agents
- Optimizing pipeline
- Reducing API costs

### 4. Error Analysis Tab

**Shows:**
- Error distribution pie chart
- Error type counts
- Recent failed runs with details
- Error messages

**Helps with:**
- Debugging common failures
- Identifying systemic issues
- Prioritizing fixes

### 5. Settings Tab

**Allows:**
- Change admin password
- Add new admin users
- View configuration
- Access documentation

---

## Advanced Configuration

### Custom Thresholds

In `core/admin_metrics.py`, modify `get_health_status()`:

```python
def get_health_status(self) -> Dict[str, Any]:
    """Get overall system health status"""
    metrics = self.get_system_metrics()
    
    status = "HEALTHY"
    issues = []
    
    if metrics.cpu_percent > 85:  # Change from 80
        status = "WARNING"
        issues.append(f"High CPU: {metrics.cpu_percent}%")
    
    # ... rest of checks ...
```

### Custom Metrics

Add to `core/admin_metrics.py`:

```python
class CustomMetrics:
    """Add your own metrics"""
    
    def record_custom_metric(self, name: str, value: float, unit: str):
        """Record a custom metric"""
        # Implement storage logic
        pass
```

### Automated Reports

Create scheduled admin reports:

```python
from core.admin_metrics import get_pipeline_metrics
import json
from datetime import datetime

def generate_daily_report():
    """Generate daily admin report"""
    
    metrics = get_pipeline_metrics()
    summary = metrics.get_pipeline_run_summary()
    
    report = {
        "date": datetime.now().isoformat(),
        "total_runs": summary["total_runs"],
        "success_rate": summary["success_rate"],
        "api_calls": summary["total_api_calls"]
    }
    
    with open("reports/daily_report.jsonl", "a") as f:
        f.write(json.dumps(report) + "\n")

# Schedule with cron:
# 0 0 * * * python -c "from scripts.reports import generate_daily_report; generate_daily_report()"
```

---

## Troubleshooting

### Q: Admin login not working

**A:** Check `.auth/admins.json` exists and is valid JSON:

```bash
cat .auth/admins.json
```

### Q: System metrics not showing

**A:** Ensure `psutil` is installed:

```bash
pip install psutil
```

### Q: No agent metrics appearing

**A:** Ensure you're calling `record_agent_run()` in your agents. Check `.audit_logs/metrics/agent_metrics.jsonl` exists.

### Q: Dashboard is slow

**A:** Dashboard reads all metrics from JSONL files. For large deployments, consider:

1. Implement caching (cache metrics for 5 minutes)
2. Archive old metrics to database
3. Show only recent metrics (last 1000 runs)

### Q: Password reset needed

**A:** Delete `.auth/admins.json` and restart - it will recreate with defaults.

```bash
rm -rf .auth/
# Restart streamlit
```

---

## Best Practices

1. **Change default password immediately** in production
2. **Restrict admin access** - only give to trusted admins
3. **Review error logs regularly** for patterns
4. **Monitor disk space** to prevent pipeline failures
5. **Archive old metrics** to keep dashboard fast
6. **Use strong passwords** (12+ characters, mixed case)
7. **Export metrics** regularly for analysis and compliance

---

## API Reference

See code docstrings for complete API reference:

- `AdminAuthenticator.authenticate(username, password)`
- `AdminAuthenticator.add_admin(username, password, full_name)`
- `AdminAuthenticator.change_password(username, old_password, new_password)`
- `SystemMonitor.get_system_metrics()`
- `SystemMonitor.get_health_status()`
- `PipelineMetrics.record_agent_run(...)`
- `PipelineMetrics.get_agent_statistics(agent_name)`
- `PipelineMetrics.get_pipeline_run_summary()`
- `PipelineMetrics.get_error_summary()`
- `PipelineMetrics.get_recent_failures(limit)`

---

**Complete, tested, and production-ready!** 🚀
