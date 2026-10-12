# Admin Dashboard System - Complete Documentation

Comprehensive reference for the admin dashboard system.

## 📚 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Features](#features)
5. [Security](#security)
6. [Performance](#performance)
7. [FAQ](#faq)

---

## Overview

The Admin Dashboard provides real-time visibility into:
- **System Health**: CPU, memory, disk usage, alerts
- **Pipeline Performance**: Run statistics, success rates, agent metrics
- **Error Tracking**: Common failures, error rates, recent errors
- **User Management**: Admin authentication, password management

### Use Cases

1. **Operations Monitoring**: Track system health during long runs
2. **Debugging**: Identify which agents are failing and why
3. **Performance Analysis**: See which agents are bottlenecks
4. **Compliance**: Audit trail of pipeline runs and errors
5. **Capacity Planning**: Monitor resource usage trends

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                Streamlit Admin Dashboard UI                  │
│  (core/admin_dashboard.py)                                   │
│                                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│  │ System Health│ │Pipeline Runs │ │   Errors     │         │
│  │    Charts    │ │   Statistics │ │   Analysis   │         │
│  └──────────────┘ └──────────────┘ └──────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Display
                            │
┌─────────────────────────────────────────────────────────────┐
│         Authentication & Authorization Layer                 │
│  (core/admin_auth.py)                                        │
│                                                               │
│  • Username/password validation                              │
│  • Session management (8-hour timeout)                       │
│  • Admin user management                                     │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Query
                            │
┌─────────────────────────────────────────────────────────────┐
│         Metrics Collection & Aggregation                     │
│  (core/admin_metrics.py)                                     │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ SystemMonitor    │  │ PipelineMetrics  │                 │
│  │                  │  │                  │                 │
│  │ • CPU usage      │  │ • Agent runs     │                 │
│  │ • Memory         │  │ • Success rates  │                 │
│  │ • Disk space     │  │ • Errors         │                 │
│  │ • Alerts         │  │ • Performance    │                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Record
                            │
┌─────────────────────────────────────────────────────────────┐
│              Pipeline Agents (Your Code)                     │
│                                                               │
│  • Profiler → record_agent_run(...)                          │
│  • STTM Generators → record_agent_run(...)                   │
│  • Reporter → record_agent_run(...)                          │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Agent Run
    ↓
[Success/Failure]
    ↓
metrics.record_agent_run(
    agent_name, run_id, duration, status, error_message
)
    ↓
.audit_logs/metrics/agent_metrics.jsonl  (append)
    ↓
[User opens Admin Dashboard]
    ↓
render_admin_dashboard()
    ↓
PipelineMetrics.get_pipeline_run_summary()
    ↓
Reads .audit_logs/metrics/agent_metrics.jsonl
    ↓
Aggregates & calculates statistics
    ↓
Display charts and metrics
```

---

## Components

### 1. AdminAuthenticator (core/admin_auth.py)

**Purpose:** Handle admin authentication and user management

**Key Methods:**

- `authenticate(username, password)` → bool
- `add_admin(username, password, full_name)` → bool
- `change_password(username, old_password, new_password)` → bool
- `get_admin(username)` → dict

**Storage:** `.auth/admins.json`

**Security Features:**
- SHA256 password hashing (not plaintext)
- Session timeout (8 hours default)
- Credentials file protection
- No password recovery (intentional - use new admin)

### 2. SystemMonitor (core/admin_metrics.py)

**Purpose:** Monitor real-time system health

**Key Methods:**

- `get_system_metrics()` → SystemMetrics
- `get_health_status()` → dict with status and alerts
- `get_cpu_trend(minutes)` → List[float]
- `get_memory_trend(minutes)` → List[float]

**Metrics Captured:**
- CPU usage %
- Memory usage % and available MB
- Disk usage % and free GB
- Process count
- Overall status (HEALTHY, WARNING, CRITICAL)

**Thresholds:**
- CPU Warning: > 80%
- Memory Warning: > 85%
- Disk Critical: > 90%
- Low Memory Alert: < 512 MB

### 3. PipelineMetrics (core/admin_metrics.py)

**Purpose:** Track agent performance and errors

**Key Methods:**

- `record_agent_run(agent_name, run_id, duration, status, ...)` → None
- `get_agent_statistics(agent_name)` → dict
- `get_pipeline_run_summary()` → dict
- `get_error_summary()` → dict
- `get_recent_failures(limit)` → List[dict]

**Metrics Tracked:**
- Total runs per agent
- Success/failure count
- Average duration
- Error rate
- API calls used
- Tokens consumed

**Storage:** `.audit_logs/metrics/agent_metrics.jsonl` (append-only)

### 4. Admin Dashboard UI (core/admin_dashboard.py)

**Purpose:** Display metrics and enable admin functions

**Tabs:**
1. **System Health** - CPU, memory, disk, trends, alerts
2. **Pipeline Runs** - Run statistics, per-agent performance
3. **Performance** - Duration analysis, API efficiency
4. **Error Analysis** - Error distribution, recent failures
5. **Settings** - Password management, user admin

**Components:**
- `render_admin_dashboard()` - Main entry point
- `render_system_health_dashboard()` - System metrics
- `render_pipeline_runs_dashboard()` - Pipeline stats
- `render_error_analysis_dashboard()` - Error tracking
- `render_performance_metrics_dashboard()` - Performance metrics
- `render_mini_dashboard()` - Compact sidebar widget

---

## Features

### System Health Monitoring

**Real-time Metrics:**
- CPU usage with 5-minute trend
- Memory usage with trend
- Disk space usage
- Available memory
- Process count
- Overall status indicator

**Alerts:**
- High CPU (> 80%)
- High memory (> 85%)
- Disk space critical (> 90%)
- Low available memory (< 512 MB)

**Visual Indicators:**
- 🟢 HEALTHY - All systems normal
- 🟡 WARNING - One or more warnings
- 🔴 CRITICAL - Disk space or other critical issue

### Pipeline Run Statistics

**Aggregated Metrics:**
- Total runs (all-time)
- Successful runs
- Failed runs
- Success rate %
- Average run duration
- Total time spent
- Total API calls

**Per-Agent Metrics:**
- Runs per agent
- Success/failure per agent
- Error rate per agent
- Average duration per agent
- Total API calls per agent
- Comparison charts

### Error Analysis

**Error Tracking:**
- Error distribution (pie chart)
- Error type counts
- Recent failures (last 10)
- Error messages
- Failure timestamps
- Failed agent names

**Use Cases:**
- Identify most common errors
- Find patterns in failures
- Quick debugging of recent failures

### Performance Metrics

**Duration Analysis:**
- Average run duration (seconds)
- Total time spent (hours)
- Per-agent duration comparison
- Trend analysis

**API Efficiency:**
- Total API calls
- Calls per run
- Cost estimation (if configured)
- Usage trends

### User Management

**Admin Functions:**
- View current admin
- Change own password
- Add new admin (admin-only)
- Remove admin (manual file edit)

**Session Management:**
- 8-hour session timeout
- Automatic logout on expiry
- Clear session state
- Logout button

---

## Security

### Authentication

**Features:**
- Username/password validation
- SHA256 password hashing
- Session timeout (8 hours)
- Credentials stored in `.auth/admins.json`

**Process:**
1. User enters username/password
2. Password hashed with SHA256
3. Hash compared to stored hash
4. Session created with timeout
5. Session checked on each page load

### Best Practices

1. **Change default password immediately**
   ```python
   auth.change_password("admin", "admin123", "NewSecurePassword123")
   ```

2. **Use strong passwords**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, special chars
   - Avoid dictionary words

3. **Restrict access**
   - Only give admin access to trusted users
   - Don't share passwords
   - Use separate admin account per person

4. **Regular audits**
   - Check who has admin access
   - Review `.auth/admins.json` for unauthorized users
   - Monitor login timestamps

5. **Backup credentials**
   - Keep `.auth/admins.json` in version control (but .gitignored)
   - Backup to secure location
   - Document recovery process

### File Permissions

For production, set file permissions:

```bash
chmod 600 .auth/admins.json
chmod 700 .auth/
```

---

## Performance

### Storage

**Metrics Files:**
- `.audit_logs/metrics/system_metrics.jsonl` (daily appends)
- `.audit_logs/metrics/agent_metrics.jsonl` (run appends)

**Size Estimates:**
- Per system metric: ~150 bytes
- Per agent run: ~200 bytes
- 1000 runs/day = ~200 KB/day
- 1 year = ~70 MB (manageable)

### Speed

**Dashboard Load Time:**
- System health: < 100 ms (psutil call)
- Pipeline stats: 1-2 seconds (reads .jsonl file)
- Error analysis: 1-2 seconds (aggregates errors)
- Charts render: < 500 ms (plotly)

**Total page load: 3-5 seconds**

### Optimization

For large deployments:

1. **Archive old metrics:**
   ```python
   # Move old metrics to database/archive
   # Keep last 30 days in .jsonl
   ```

2. **Implement caching:**
   ```python
   @st.cache_data(ttl=300)  # Cache 5 minutes
   def get_pipeline_summary():
       return metrics.get_pipeline_run_summary()
   ```

3. **Limit displayed records:**
   ```python
   # Show only last 1000 runs
   # Show only recent failures (< 7 days)
   ```

---

## FAQ

### Q: How do I add more admins?

**A:** Use the Settings tab or programmatically:

```python
from core.admin_auth import AdminAuthenticator

auth = AdminAuthenticator()
auth.add_admin("alice", "SecurePass123", "Alice Smith")
```

### Q: I forgot the admin password

**A:** Delete `.auth/admins.json` and restart (creates defaults):

```bash
rm .auth/admins.json
# Restart streamlit
# Login with: admin / admin123
```

### Q: How do I track custom metrics?

**A:** Extend PipelineMetrics:

```python
class CustomPipelineMetrics(PipelineMetrics):
    def record_custom_metric(self, name, value):
        # Implement custom storage
        pass
```

### Q: Can I export metrics?

**A:** Yes, the .jsonl files are plain JSON:

```python
import json

with open(".audit_logs/metrics/agent_metrics.jsonl") as f:
    for line in f:
        metric = json.loads(line)
        print(metric)
```

### Q: What if system metrics won't show?

**A:** Ensure psutil is installed:

```bash
pip install psutil
```

### Q: How do I see metrics from a specific run?

**A:** Filter by run_id:

```python
from core.admin_metrics import get_pipeline_metrics

metrics = get_pipeline_metrics()
failures = metrics.get_recent_failures()

for failure in failures:
    if failure['run_id'] == 'my_run_id':
        print(failure)
```

### Q: Can I use this with Docker?

**A:** Yes! Mount volume for metrics:

```yaml
volumes:
  - ./audit_logs:/app/.audit_logs
  - ./.auth:/app/.auth
```

### Q: How often should I archive old metrics?

**A:** Recommended schedule:
- Every 30 days: Archive metrics > 90 days old
- Every quarter: Full backup of metrics database
- Keep last 12 months in active storage

### Q: Can I disable the admin dashboard?

**A:** Yes, simply don't add the admin page to your app:

```python
# Don't include this:
if page == "Admin Dashboard":
    render_admin_dashboard()
```

---

## Example Workflows

### Workflow 1: Debug a Failed Run

```
1. Open Admin Dashboard → Error Analysis tab
2. Find recent failure with agent name and error message
3. Note the run_id
4. Go to Audit logs and search for that run_id
5. See complete error trace
6. Fix the issue
7. Watch success rate recover in dashboard
```

### Workflow 2: Optimize Performance

```
1. Open Admin Dashboard → Performance tab
2. See which agents have longest average duration
3. Focus optimization on bottleneck agent
4. Make code changes
5. Check Performance tab again after next runs
6. See if average duration improved
```

### Workflow 3: Monitor Resource Usage

```
1. Open Admin Dashboard → System Health tab
2. Watch CPU/Memory/Disk trends during long run
3. If memory hits 85%+, get alert
4. If disk hits 90%+, get critical alert
5. Can then:
   - Add more disk space
   - Reduce batch size
   - Reduce concurrent runs
```

---

## Integration Checklist

- [ ] Install dependencies: `pip install psutil plotly`
- [ ] Create admin user: `AdminAuthenticator()`
- [ ] Change default password
- [ ] Add metric recording to each agent
- [ ] Add admin page to main app
- [ ] Test login/logout
- [ ] Run pipeline and verify metrics appear
- [ ] Review error analysis for any issues
- [ ] Document admin access procedure
- [ ] Set up automated metrics backup

---

**Complete, secure, and production-ready!** 🚀
