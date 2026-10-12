# Setup Checklist — IDAMP Project

Complete this checklist to verify your Agentic Medallion Pipeline is ready for production.

---

## 1. Project Files

Verify all required files exist in your project root:

### Core Infrastructure
- [ ] `core/config.py` — Environment loading, path setup, LLM provider detection
- [ ] `core/audit.py` — JSONL audit logging
- [ ] `core/observability.py` — AgentTrace for reasoning capture
- [ ] `core/state.py` — PipelineState TypedDict
- [ ] `core/memory.py` — ChromaDB semantic storage
- [ ] `core/__init__.py` — Package marker

### Agents
- [ ] `agents/profiler.py` — Data profiling agent
- [ ] `agents/bronze_agent.py` — Raw data ingestion
- [ ] `agents/silver_agent.py` — Data cleansing
- [ ] `agents/gold_agent.py` — Analytics tables
- [ ] `agents/sttm_generator.py` — Transformation rule generation
- [ ] `agents/reporter.py` — Report generation
- [ ] `agents/orchestrator.py` — 4-phase coordinator
- [ ] `agents/__init__.py` — Package marker

### User Interface
- [ ] `app/streamlit_app.py` — Streamlit web interface
- [ ] `app/__init__.py` — Package marker

### Tests (93 tests)
- [ ] `tests/conftest.py` — Shared pytest fixtures
- [ ] `tests/pytest.ini` — Pytest configuration (or top-level `pytest.ini`)
- [ ] `tests/test_audit.py` — 10 audit logger tests
- [ ] `tests/test_bronze.py` — 12 bronze layer tests
- [ ] `tests/test_silver.py` — 13 silver layer tests
- [ ] `tests/test_gold.py` — 13 gold layer tests
- [ ] `tests/test_profiler.py` — 12 profiler tests
- [ ] `tests/test_reporter.py` — 14 reporter tests
- [ ] `tests/test_sttm.py` — 19 STTM generator tests
- [ ] `tests/README.md` — Testing guide
- [ ] `tests/__init__.py` — Package marker

### Configuration & Documentation
- [ ] `.env` — Environment variables with API keys (DO NOT commit)
- [ ] `.env.example` — Template for `.env`
- [ ] `README.md` — Comprehensive project documentation
- [ ] `SETUP_CHECKLIST.md` — This file
- [ ] `test_import.py` — Quick import sanity check
- [ ] `requirements.txt` — Python dependencies
- [ ] `pytest.ini` — Pytest configuration
- [ ] `.gitignore` — Excludes .env, venv, __pycache__, etc.

### Data Directories (auto-created)
- [ ] `data/` — Root data directory
- [ ] `data/landing/` — Uploaded CSV files
- [ ] `data/profiles/` — Profile JSON files
- [ ] `data/bronze_layer/` — Bronze Parquet files
- [ ] `data/silver_layer/` — Silver Parquet files
- [ ] `data/gold_layer/` — Gold Parquet files
- [ ] `data/sttm/` — Transformation rule CSV files
- [ ] `data/reports/` — HTML reports
- [ ] `data/traces/` — Agent reasoning traces (JSON)
- [ ] `data/audit_logs/` — Audit trail (JSONL)
- [ ] `.chroma/` — ChromaDB persistent storage

---

## 2. Verification Commands

Run these commands in order to verify your setup:

### Step 1: Check Python Version
```bash
python --version
```
**Expected**: Python 3.11 or later
```
Python 3.11.x, 3.12.x, or 3.13.x
```

### Step 2: Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python -m venv venv
source venv/bin/activate
```

**Expected**: Prompt shows `(venv)` prefix

### Step 3: Upgrade pip
```bash
python -m pip install --upgrade pip
```

**Expected**: Latest pip version installed

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

**Expected**: All packages installed without errors
```
Successfully installed langchain-0.x.x, langchain-groq-0.x.x, streamlit-1.x.x, ...
```

### Step 5: Quick Import Test
```bash
python test_import.py
```

**Expected**: Green SUCCESS message
```
Testing core module imports...
  [OK] core.config
  [OK] core.audit
  [OK] core.observability
  [OK] core.state
  [OK] core.memory

Testing agent module imports...
  [OK] agents.profiler
  [OK] agents.bronze_agent
  [OK] agents.silver_agent
  [OK] agents.gold_agent
  [OK] agents.sttm_generator
  [OK] agents.reporter

Testing orchestrator imports...
  [OK] agents.orchestrator
    - run_until_bronze_sttm
    - run_bronze_to_silver_sttm
    - run_silver_to_gold_sttm
    - run_gold_and_report

Testing app module imports...
  [WARN] app.streamlit_app (expected if running outside Streamlit): ...

============================================================
SUCCESS! All core imports worked.
============================================================
```

### Step 6: Run Full Test Suite (93 tests)
```bash
pytest tests/ -v
```

**Expected**: All 93 tests PASS
```
============================= 93 passed, 12 warnings in 44.11s =======================
```

**Individual test files** (optional):
```bash
# Run specific test file
pytest tests/test_audit.py -v
pytest tests/test_bronze.py -v
pytest tests/test_silver.py -v
pytest tests/test_gold.py -v
pytest tests/test_profiler.py -v
pytest tests/test_reporter.py -v
pytest tests/test_sttm.py -v
```

### Step 7: Check Environment Variables
```bash
# Verify .env file exists
ls -la .env    # macOS/Linux
dir .env       # Windows

# View .env file (DO NOT share output publicly)
cat .env       # macOS/Linux
type .env      # Windows
```

**Expected**: File contains all required API keys:
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
GOOGLE_API_KEY=...
OPENAI_API_KEY=sk-...
```

### Step 8: Start Streamlit App
```bash
streamlit run app/streamlit_app.py
```

**Expected**: App starts and URL shows
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

**Browser**: Open http://localhost:8501

---

## 3. Common Issues & Solutions

### Issue: Python Version Too Old
**Error**: `SyntaxError` or `AttributeError` with TypeError messages  
**Fix**:
```bash
python --version  # Check current version
# If < 3.11, install Python 3.11+ from python.org
python3.11 -m venv venv
python3.11 -m pip install -r requirements.txt
```

---

### Issue: Virtual Environment Not Activated
**Error**: `ModuleNotFoundError` or `No module named 'langchain'`  
**Fix**:
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# Verify: prompt should show (venv) prefix
```

---

### Issue: Missing or Incorrect `.env` File
**Error**: `KeyError` or `LLM_PROVIDER not found` in `core/config.py`  
**Fix**:
```bash
# Copy template
cp .env.example .env

# Edit with your API keys
# Windows: notepad .env
# macOS/Linux: nano .env or vim .env

# Verify required keys exist:
GROQ_API_KEY=gsk_...
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.3-70b-versatile
```

---

### Issue: Missing Dependencies
**Error**: `ModuleNotFoundError: No module named 'langchain'`  
**Fix**:
```bash
# Reinstall requirements
pip install --force-reinstall -r requirements.txt

# Or install individually
pip install langchain langchain-groq streamlit pandas
```

---

### Issue: Import Errors After Installation
**Error**: `ImportError: cannot import name 'xyz' from 'module'`  
**Fix**:
```bash
# Run import test to diagnose
python test_import.py

# Check specific module
python -c "from core.config import BASE_DIR; print(BASE_DIR)"

# If still failing, reinstall:
pip install --force-reinstall -r requirements.txt
python test_import.py
```

---

### Issue: Groq Model Not Found (404)
**Error**: 
```
groq.error.APIStatusError: Error code: 404 — model_not_found
The model 'llama-3.2-70b-versatile' (or whatever model you specified) does not exist
```

**Cause**: Groq has deprecated or renamed the model.

**Fix**:
1. Check current models at: https://console.groq.com/docs/models
2. Update `.env` file:
   ```bash
   # OLD (deprecated)
   GROQ_MODEL=llama-3.2-70b-versatile
   
   # NEW (current)
   GROQ_MODEL=llama-3.3-70b-versatile
   ```
3. Verify `core/config.py` reads from `.env` dynamically:
   ```python
   GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
   ```
   ❌ NOT hardcoded: `GROQ_MODEL = "llama-3.3-70b-versatile"`
4. Restart Streamlit:
   ```bash
   # Kill current process (see below)
   # Then restart
   streamlit run app/streamlit_app.py
   ```

---

### Issue: "Bronze/Silver/Gold STTM file is empty or corrupted"
**Error**: STTM CSV has zero rows; LLM response couldn't be parsed to JSON  
**Symptoms**:
- Streamlit shows: `EmptyDataError: No columns to parse from file`
- Or STTM CSV is 0 bytes
- Or traceback in terminal shows JSON parsing failed

**Cause**: LLM call returned non-JSON text; `<think>` tags corrupted JSON extraction (if not hidden).

**Fix**:
1. Check `agents/sttm_generator.py` uses `reasoning_format="hidden"` for Groq:
   ```python
   def _make_llm():
       if LLM_PROVIDER == "groq":
           from langchain_groq import ChatGroq
           return ChatGroq(
               api_key=GROQ_API_KEY,
               model=GROQ_MODEL,
               reasoning_format="hidden",  # ← MUST BE HERE
               reasoning_effort="low",
           )
   ```

2. Check `_invoke_llm_for_sttm_rows()` raises clear error (doesn't silently return empty):
   ```python
   def _invoke_llm_for_sttm_rows(prompt: str, layer: str) -> list[dict]:
       # ... first attempt ...
       rows = _parse_json_array(response.content)
       
       if not rows:
           # ... RETRY ONCE ...
           response = llm.invoke([...])
           rows = _parse_json_array(response.content)
       
       if not rows:
           # ← RAISE ERROR, DON'T SILENTLY RETURN []
           raise ValueError(
               f"STTM generation failed after 2 attempts. "
               f"Last response (truncated): {response.content[:200]}"
           )
       return rows
   ```

3. Restart Streamlit and re-run Phase 1:
   ```bash
   # Kill stale process (see below)
   streamlit run app/streamlit_app.py
   ```

4. Check terminal for full traceback showing what LLM returned.

---

### Issue: Streamlit Not Starting / Port 8501 Already in Use
**Error**: 
```
OSError: [Errno 48] Address already in use
or
Traceback: Address already in use
```

**Cause**: Stale Streamlit process still running (previous terminal, wrong venv, etc.)

**Fix**:

#### Windows:
```powershell
# Find all Python processes
Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='streamlit.exe'" | Select-Object ProcessId, CommandLine

# Kill by ID
Stop-Process -Id <id> -Force

# Example: Stop-Process -Id 12345 -Force
```

#### macOS/Linux:
```bash
# Find process on port 8501
lsof -i :8501

# Kill by PID
kill -9 <pid>

# Or kill all python processes
pkill -f streamlit
pkill -f python
```

**Then restart fresh:**
```bash
# Verify venv is active (should show (venv) in prompt)
streamlit run app/streamlit_app.py
```

---

### Issue: "I fixed the code but getting the exact same error"
**Cause**: Stale Streamlit process serving OLD code from memory/cache

**Fix**:
1. Kill all stale processes (see above)
2. Clear Streamlit cache:
   ```bash
   rm -rf ~/.streamlit/cache    # macOS/Linux
   rmdir %USERPROFILE%\.streamlit\cache /S  # Windows
   ```
3. Verify your code change was actually saved
4. Start exactly ONE fresh process:
   ```bash
   streamlit run app/streamlit_app.py
   ```

---

### Issue: Agent Failure / Timeout
**Error**: 
```
langchain.exceptions.OutputParserException: Failed to parse...
or
Timeout waiting for agent...
```

**Fix**:
1. Check agent logs in terminal (full traceback)
2. Verify API key is valid (not expired)
3. Check `.env` has correct LLM_PROVIDER
4. Increase timeout in `agents/orchestrator.py` (default 300s):
   ```python
   result = agent.invoke({"messages": [...], "timeout": 600})  # 10 min
   ```
5. Use faster LLM (Groq < OpenAI < Gemini in speed)

---

### Issue: Data Not Appearing in Landing Directory
**Error**: Upload succeeds but files not in `data/landing/`

**Cause**: `LANDING_DIR` path incorrect or not created

**Fix**:
```bash
# Check LANDING_DIR is set correctly in core/config.py
python -c "from core.config import LANDING_DIR; print(LANDING_DIR)"

# Expected: /absolute/path/to/project/data/landing

# Manually create if missing
mkdir -p data/landing
```

---

### Issue: ChromaDB Connection Error
**Error**: 
```
chromadb.errors.InvalidCollectionException
or
sqlite3.OperationalError
```

**Fix**:
```bash
# Clear stale ChromaDB cache
rm -rf .chroma/    # macOS/Linux
rmdir .chroma /S   # Windows

# Restart app
streamlit run app/streamlit_app.py
```

---

### Issue: Pandas Warning / Deprecation Errors
**Warning**: `FutureWarning` or `DeprecationWarning`  
**Fix**: Usually safe to ignore; if problematic, upgrade pandas:
```bash
pip install --upgrade pandas
```

---

## 4. Full Workflow Test

Test the complete pipeline end-to-end:

### 4.1 Prepare Test Data

Create a sample CSV file `test_data.csv`:
```csv
customer_id,name,email,purchase_amount,purchase_date
1,Alice Johnson,alice@example.com,1250.50,2024-01-15
2,Bob Smith,bob@example.com,2100.00,2024-01-16
3,Charlie Brown,charlie@example.com,950.75,2024-01-17
1,Alice Johnson,alice@example.com,500.00,2024-01-18
4,Diana Prince,diana@example.com,1800.25,2024-01-19
5,Eve Davis,eve@example.com,NULL,2024-01-20
2,Bob Smith,bob@example.com,3200.00,2024-01-21
```

**Features**:
- Mix of numeric and string data
- Duplicate customer (Alice, Bob)
- Null value (Eve's amount)
- Email format consistency

### 4.2 Start Streamlit App
```bash
streamlit run app/streamlit_app.py
```

Open: http://localhost:8501

### 4.3 Phase 1: Upload & Intent

**Action**:
1. Drag/upload `test_data.csv`
2. Enter business question:
   ```
   What are the top customers by purchase amount and their email contact?
   ```
3. Click "🚀 Start Workflow"

**Expected**:
- Spinner: "🔍 Profiling data..."
- Page refreshes to Phase 2
- Audit logs appear in sidebar
- Status: "awaiting_bronze_sttm_approval"

**Backend**:
- `data/profiles/{run_id}.json` created
- `data/sttm/bronze_sttm_{run_id[:8]}.csv` created with transformation rules
- `data/audit_logs/{run_id}.jsonl` created with phase start event

### 4.4 Phase 2: Bronze Review

**Expected**:
- Shows "Review Bronze Layer STTM"
- Data editor with transformation rules (5 rows: customer_id, name, email, purchase_amount, purchase_date)
- Each row has checkbox (approved by default)
- Column names show target mappings

**Action**:
- Review rules (should show: column rename, add _load_timestamp, add _source_file)
- Click "✅ Approve & Continue"

**Expected**:
- Spinner: "Applying Bronze rules..."
- Page refreshes to Phase 3
- Status: "awaiting_silver_sttm_approval"

**Backend**:
- `data/bronze_layer/test_data.parquet` created
- `data/sttm/silver_sttm_{run_id[:8]}.csv` created

### 4.5 Phase 3: Silver Review

**Expected**:
- Shows "Review Silver Layer STTM"
- Transformation rules for cleansing (dedup, null fill, surrogate key injection)
- Rows selected by default

**Action**:
- Click "✅ Approve & Continue"

**Expected**:
- Page refreshes to Phase 4
- Status: "awaiting_gold_sttm_approval"

**Backend**:
- `data/silver_layer/test_data.parquet` created
- `data/sttm/gold_sttm_{run_id[:8]}.csv` created

### 4.6 Phase 4: Gold Review

**Expected**:
- Shows "Review Gold Layer STTM"
- Table creation rules (fact table, columns)

**Action**:
- Click "✅ Approve & Execute"

**Expected**:
- Spinner: "Generating report..."
- Page refreshes to Phase 5
- Status: "completed"

**Backend**:
- `data/gold_layer/` contains analytics tables
- `data/reports/report_{run_id[:8]}.html` generated

### 4.7 Phase 5: Report

**Expected**:
- Shows "Executive Report"
- Embedded HTML report with visualizations
- "📥 Download Report" and "🔄 Start New Analysis" buttons

**Action**:
1. Scroll through report, verify charts appear
2. Click "📥 Download Report" to save HTML

**Backend**:
- HTML file downloaded successfully
- Can open in browser offline

### 4.8 Verify Audit Trail

In sidebar, click "Audit Trail":
- Shows latest event (report generation)
- Scroll to see previous events (bronze, silver, gold phases)
- Each entry has: timestamp, agent, action, status

**Expected entries**:
```
1. bronze_sttm_generator — generate_sttm — status: success
2. bronze_agent — apply_rules — status: success
3. silver_sttm_generator — generate_sttm — status: success
4. silver_agent — apply_rules — status: success
5. gold_sttm_generator — generate_sttm — status: success
6. gold_agent — apply_rules — status: success
7. reporter_agent — generate_report — status: success
```

### 4.9 Verify Files Created

```bash
# List all generated files
ls -R data/         # macOS/Linux
dir /S data\        # Windows

# Expected directory structure
data/
├── landing/
│   └── test_data.csv (original)
├── profiles/
│   └── {run_id}.json
├── bronze_layer/
│   └── test_data.parquet
├── silver_layer/
│   └── test_data.parquet
├── gold_layer/
│   └── *.parquet (fact/dimension tables)
├── sttm/
│   ├── bronze_sttm_{run_id[:8]}.csv
│   ├── silver_sttm_{run_id[:8]}.csv
│   └── gold_sttm_{run_id[:8]}.csv
├── reports/
│   └── report_{run_id[:8]}.html
├── traces/
│   ├── trace_bronze_agent_{run_id[:8]}.json
│   ├── trace_silver_agent_{run_id[:8]}.json
│   ├── trace_gold_agent_{run_id[:8]}.json
│   └── trace_reporter_{run_id[:8]}.json
└── audit_logs/
    └── {run_id}.jsonl
```

### 4.10 Inspect Audit Log

```bash
# View audit trail (JSONL format, one JSON object per line)
cat data/audit_logs/{run_id}.jsonl    # macOS/Linux
type data\audit_logs\{run_id}.jsonl   # Windows

# Pretty-print with jq (if installed)
jq . data/audit_logs/{run_id}.jsonl
```

**Expected**: 7+ entries with timestamps, run_id, agent, action, status

### 4.11 Inspect Bronze/Silver/Gold Parquet

```bash
# Using pandas
python -c "
import pandas as pd
df = pd.read_parquet('data/bronze_layer/test_data.parquet')
print(df.head())
print(f'Shape: {df.shape}')
print(f'Columns: {list(df.columns)}')
"
```

**Expected**:
- Bronze: 7 rows (unchanged from source) + metadata columns
- Silver: 5-6 rows (deduplicated) + surrogate key
- Gold: Analytics-ready fact table

---

## 5. Final Verification Checklist

- [ ] `python --version` shows Python 3.11+
- [ ] Virtual environment activated (`(venv)` in prompt)
- [ ] `pip list` shows langchain, streamlit, pandas, etc.
- [ ] `python test_import.py` shows SUCCESS
- [ ] `pytest tests/ -v` shows 93 PASSED
- [ ] `.env` file exists with all API keys filled
- [ ] `streamlit run app/streamlit_app.py` starts without errors
- [ ] Phase 1: Upload test_data.csv and business question
- [ ] Phase 2: Approve Bronze rules
- [ ] Phase 3: Approve Silver rules
- [ ] Phase 4: Approve Gold rules
- [ ] Phase 5: Report displays and downloads
- [ ] Audit trail shows all 7+ events
- [ ] `data/` folder contains all expected files
- [ ] No stale Streamlit processes running (port 8501 clean)
- [ ] No duplicate column errors in STTM
- [ ] No JSON parsing errors from LLM
- [ ] ChromaDB `.chroma/` folder exists and accessible

---

## 6. Troubleshooting Flowchart

```
Error occurs?
│
├─→ ModuleNotFoundError?
│   └─→ Run: python test_import.py
│       └─→ If fails: pip install --force-reinstall -r requirements.txt
│
├─→ Port 8501 already in use?
│   └─→ Kill stale process (see Issue #4)
│       └─→ Restart: streamlit run app/streamlit_app.py
│
├─→ Model not found (404)?
│   └─→ Check: https://console.groq.com/docs/models
│       └─→ Update .env GROQ_MODEL
│           └─→ Restart Streamlit
│
├─→ Empty STTM file?
│   └─→ Check: agents/sttm_generator.py has reasoning_format="hidden"
│       └─→ Check: _invoke_llm_for_sttm_rows raises error (not silent)
│           └─→ Restart Streamlit and retry Phase 1
│
├─→ Same error after code fix?
│   └─→ Kill all stale processes (Windows: Get-CimInstance, macOS/Linux: lsof -i :8501)
│       └─→ Clear cache: rm -rf ~/.streamlit/cache
│           └─→ Restart: streamlit run app/streamlit_app.py
│
└─→ Something else?
    └─→ Check terminal traceback
        └─→ Google error message
            └─→ Check README.md FAQ
```

---

## 7. Quick Health Check Commands

Copy-paste these commands to verify everything is working:

```bash
# 1. All-in-one health check
python --version && \
echo "✓ Python OK" && \
python test_import.py && \
echo "✓ Imports OK" && \
pytest tests/test_audit.py -q && \
echo "✓ Tests OK" && \
echo "Ready to run: streamlit run app/streamlit_app.py"
```

---

## 8. Support & Debug

### Enable Debug Logging
```bash
# Run Streamlit with debug logging
streamlit run app/streamlit_app.py --logger.level=debug
```

### Check Agent Logs
Terminal shows all agent operations:
```
Agent: bronze_agent
Action: apply_rules
Result: 7 rows transformed
Trace: data/traces/trace_bronze_agent_abc12345.json
```

### View Trace Files (JSON)
```bash
# Pretty-print trace
python -c "
import json
with open('data/traces/trace_bronze_agent_abc12345.json') as f:
    trace = json.load(f)
    print(json.dumps(trace, indent=2))
"
```

### Check API Key Validity
```python
# Test Groq API key
from langchain_groq import ChatGroq
llm = ChatGroq(api_key="gsk_...", model="llama-3.3-70b-versatile")
response = llm.invoke("Hello")
print(response.content)
```

---

**Congratulations!** 🎉 If all checks pass, your IDAMP pipeline is ready for production.

Questions? See README.md FAQ section or check agent traceback in `data/traces/`.
