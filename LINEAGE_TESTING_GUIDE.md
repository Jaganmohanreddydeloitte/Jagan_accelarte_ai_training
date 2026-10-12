# Data Lineage Integration — Quick Testing Guide

## Verify Integration (5 minutes)

### Step 1: Verify Component Syntax

```bash
# Check orchestrator
python -m py_compile agents/orchestrator.py
# Expected: No output (success)

# Check Streamlit app
python -m py_compile app/streamlit_app.py
# Expected: No output (success)

# Check lineage components
python test_lineage.py
# Expected: All 8 tests PASSED
```

### Step 2: Verify Imports

```bash
python -c "from agents.orchestrator import LineageTracker; print('OK')"
python -c "from core.lineage_ui import render_lineage_dashboard; print('OK')"
```

---

## End-to-End Test (15 minutes)

### Setup

1. **Prepare test data:**
   ```bash
   # Create a simple CSV if you don't have one
   cat > test_data.csv << 'EOF'
   customer_id,name,email,purchase_amount,date
   1001,Alice,alice@example.com,150.00,2025-01-01
   1002,Bob,bob@example.com,200.00,2025-01-02
   1003,Charlie,charlie@example.com,175.00,2025-01-03
   1004,Diana,diana@example.com,220.00,2025-01-04
   1005,Eve,eve@example.com,180.00,2025-01-05
   EOF
   ```

2. **Start Streamlit app:**
   ```bash
   streamlit run .\app\streamlit_app.py
   ```
   - Browser should open to `http://localhost:8501`
   - If not, click the link in terminal

### Execute Test

1. **Phase 1: Upload & Profile**
   - Click "Choose CSV file(s)"
   - Select your test_data.csv
   - Enter Business Intent: "Analyze customer purchasing patterns"
   - Click "➤ Analyze & Profile"
   - Wait 20-30 seconds
   - Verify: Profile summary appears

2. **Review Bronze STTM**
   - Scroll down to see Bronze transformation rules
   - Click "✓ Approve" button
   - Verify: "Bronze STTM approved" message

3. **Execute Bronze**
   - Click "➤ Execute Bronze Layer"
   - Wait 30-60 seconds
   - Verify: "Bronze execution complete" message

4. **Review Silver STTM**
   - Scroll to Silver STTM section
   - Click "✓ Approve" button
   - Verify: "Silver STTM approved" message

5. **Execute Silver**
   - Click "➤ Execute Silver Layer"
   - Wait 30-60 seconds
   - Verify: "Silver execution complete" message

6. **Review Gold STTM**
   - Scroll to Gold STTM section
   - Click "✓ Approve" button
   - Verify: "Gold STTM approved" message

7. **Execute Gold & Generate Report**
   - Click "➤ Execute Gold & Report"
   - Wait 60-90 seconds
   - Verify: HTML report displays

8. **Verify Lineage Dashboard** ← NEW FEATURE
   - Scroll down below the report
   - Look for "📊 Data Lineage & Transformations" section
   - Verify: 5 tabs visible (Data Flow, Transformations, Stage Details, Column Trace, Summary)

### Test Dashboard Tabs

**Tab 1: Data Flow**
- ✓ Shows Mermaid diagram
- ✓ Shows "source → bronze → silver → gold" flow
- ✓ Displays row counts
- ✓ Displays column counts

**Tab 2: Transformations**
- ✓ Shows transformation nodes
- ✓ Lists all stages
- ✓ Shows descriptions of transformations applied

**Tab 3: Stage Details**
- ✓ Shows table with stage information
- ✓ Expandable sections for each stage
- ✓ Shows column names per stage

**Tab 4: Column Trace**
- ✓ Dropdown to select column
- ✓ Shows source file
- ✓ Shows all transformations for that column
- ✓ Try selecting different columns

**Tab 5: Summary**
- ✓ Shows markdown report
- ✓ Lists all stages and transformations
- ✓ Shows business intent
- ✓ Shows run ID

---

## Verify Lineage Files

### Check Lineage JSON File

```bash
# List lineage files
ls -la data/lineage/

# Expected output:
# -rw-r--r-- data/lineage/lineage_abc123def.json (2-5 KB)

# View lineage content
cat data/lineage/lineage_abc123def.json | python -m json.tool

# Expected output:
# {
#   "run_id": "...",
#   "business_intent": "...",
#   "source_files": [...],
#   "stages": [...]
# }
```

### Check Audit Logs

```bash
# View audit logs for lineage tracking
tail -20 audit_logs/run_id.jsonl

# Expected to see entries like:
# {"timestamp": "...", "agent": "orchestrator", "action": "phase1_start", ...}
# {"timestamp": "...", "agent": "orchestrator", "action": "phase2_lineage_start", ...}
# {"timestamp": "...", "agent": "orchestrator", "action": "phase4_lineage_saved", ...}
```

---

## Verification Checklist

### Code Level

- [ ] orchestrator.py compiles without syntax errors
- [ ] streamlit_app.py compiles without syntax errors
- [ ] test_lineage.py runs with all 8 tests PASSED
- [ ] Imports work: `from core.lineage import LineageTracker`
- [ ] Imports work: `from core.lineage_ui import render_lineage_dashboard`

### File System

- [ ] data/lineage/ directory exists
- [ ] lineage_*.json file created after Phase 4
- [ ] File size is 2-5 KB (not empty)
- [ ] audit_logs/ directory has run logs

### Streamlit Interface

- [ ] "📊 Data Lineage & Transformations" section appears in report phase
- [ ] All 5 tabs render without errors:
  - [ ] Data Flow tab shows Mermaid diagram
  - [ ] Transformations tab shows details
  - [ ] Stage Details tab shows table
  - [ ] Column Trace tab shows dropdown and selections
  - [ ] Summary tab shows markdown

### Functionality

- [ ] Lineage data flows through all 4 phases
- [ ] Transformations recorded correctly per stage
- [ ] Row counts show changes between stages
- [ ] Column names tracked correctly
- [ ] Diagrams render properly
- [ ] Column tracing works (dropdown selection works)

---

## Troubleshooting

### Issue: Lineage Dashboard Not Appearing

**Check:**
1. Is run_id being passed to dashboard?
   ```python
   run_id = st.session_state.pipeline_state.get("run_id", "")
   print(f"Run ID: {run_id}")  # Debug print
   ```

2. Does lineage file exist?
   ```bash
   ls data/lineage/lineage_${run_id}.json
   ```

3. Check Streamlit logs:
   - Look for import errors
   - Look for render_lineage_dashboard errors

**Fix:**
- Make sure orchestrator.py changes are saved
- Make sure streamlit_app.py changes are saved
- Restart Streamlit: `Ctrl+C` then `streamlit run ...`

### Issue: Dashboard Shows "No Lineage Data"

**Check:**
1. Did Phase 4 complete? (Check for report file)
2. Did tracker.save() get called?
3. Is the lineage JSON file created?

**Debug:**
```python
# Add to orchestrator.py in Phase 4
lineage_file = tracker.save()
print(f"Lineage saved to: {lineage_file}")
print(f"File size: {lineage_file.stat().st_size} bytes")
```

### Issue: Tabs Not Rendering / Errors in Dashboard

**Check:**
1. Streamlit version: `streamlit --version` (need 1.23+)
2. Browser console for JavaScript errors (F12)
3. Streamlit logs for Python errors

**Fix:**
```bash
# Update Streamlit
pip install --upgrade streamlit

# Restart app
Ctrl+C
streamlit run .\app\streamlit_app.py
```

### Issue: Mermaid Diagrams Show "Diagram rendering failed"

**Check:**
1. Streamlit version (need 1.23+)
2. Browser has internet (Mermaid CDN)
3. No special characters in descriptions

**Fix:**
- Update Streamlit
- Clear browser cache
- Restart Streamlit
- Check lineage descriptions don't have JSON-breaking characters

---

## Quick Diagnostic Commands

```bash
# Test orchestrator
python -c "
from agents.orchestrator import LineageTracker, run_until_bronze_sttm
print('✓ Orchestrator imports OK')
print('✓ LineageTracker available')
"

# Test lineage module
python -c "
from core.lineage import LineageTracker, load_lineage
from core.lineage_visualizer import LineageVisualizer
from core.lineage_ui import render_lineage_dashboard
print('✓ All lineage modules import OK')
"

# Test Streamlit imports
python -c "
import streamlit as st
from core.lineage_ui import render_lineage_dashboard
print('✓ Streamlit + lineage UI imports OK')
"

# Check file changes
git diff agents/orchestrator.py | head -50
git diff app/streamlit_app.py | head -50
```

---

## Performance Expectations

### Lineage Overhead Per Phase

| Phase | Operation | Time | Notes |
|-------|-----------|------|-------|
| 1 | Initialize tracker | <1ms | Negligible |
| 1 | Track source files | <5ms | Per 100 files |
| 2 | Track Bronze stage | <5ms | Start + transformations |
| 3 | Track Silver stage | <5ms | Start + transformations |
| 4 | Track Gold stage | <5ms | Start + transformations |
| 4 | Save lineage JSON | ~50ms | File I/O |
| **Total** | **All lineage ops** | **~80ms** | **<1% of pipeline** |

### Expected File Sizes

- Lineage JSON: 2-5 KB per run
- Audit logs: Variable (depends on agent chatter)
- Traces: ~5-10 KB per run

---

## Success Criteria

✅ **Full Success if:**
1. Lineage file created in data/lineage/
2. Dashboard renders all 5 tabs without errors
3. All tabs show data (not empty)
4. Column trace dropdown works
5. Mermaid diagrams render
6. No Python errors in logs

✅ **Partial Success if:**
1. Lineage JSON created (main feature)
2. Dashboard renders (UI working)
3. Some tabs have data (core functionality)
4. Can see flow diagram (primary use case)

❌ **Failure if:**
1. No lineage file created
2. Dashboard doesn't render
3. Python import errors
4. Syntax errors in modified files

---

## Expected Output Example

```
Phase 1: Profile & Bronze STTM
├─ ✓ Profile created
├─ ✓ Lineage tracker initialized
├─ ✓ Source files tracked
└─ ✓ Bronze STTM generated

Phase 2: Bronze Load
├─ ✓ Bronze stage started
├─ ✓ Transformation tracked
├─ ✓ 45,000 rows processed
└─ ✓ Stage completed

Phase 3: Silver Load
├─ ✓ Silver stage started
├─ ✓ Transformation tracked
├─ ✓ 42,000 rows processed
└─ ✓ Stage completed

Phase 4: Gold Load & Report
├─ ✓ Gold stage started
├─ ✓ Transformation tracked
├─ ✓ 12,000 records processed
├─ ✓ Report generated
└─ ✓ Lineage saved to data/lineage/lineage_abc123.json

Streamlit Report Phase
├─ ✓ HTML report displayed
├─ ✓ Chat interface ready
├─ ✓ Lineage dashboard renders
├─ ✓ All 5 tabs functional
└─ ✓ Column tracing works
```

---

## Next: Full Integration Testing

After verifying the quick test above, refer to:
- [LINEAGE_INTEGRATION_COMPLETE.md](LINEAGE_INTEGRATION_COMPLETE.md) for detailed integration info
- [DATA_LINEAGE_GUIDE.md](DATA_LINEAGE_GUIDE.md) for API reference
- [DATA_LINEAGE_SUMMARY.md](DATA_LINEAGE_SUMMARY.md) for quick reference
