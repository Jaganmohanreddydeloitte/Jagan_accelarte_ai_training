# Data Quality Checks for IDAMP Pipeline

Complete guide to automated data quality validation between medallion layers.

---

## Overview

The data quality module (`core/data_quality.py`) provides automated checks that run after each layer (Bronze, Silver, Gold) to ensure data integrity, detect anomalies, and fail the pipeline if quality is too low.

### Key Features

- ✅ **Null value detection** — Identify missing data and critical columns
- ✅ **Row count validation** — Detect data loss between layers  
- ✅ **Duplicate detection** — Find unexpected duplicate rows
- ✅ **Anomaly detection** — Identify numeric outliers using statistical analysis
- ✅ **Data type validation** — Verify columns have expected types
- ✅ **Value range checks** — Ensure values fall within acceptable ranges
- ✅ **Required column verification** — Check that essential columns exist
- ✅ **Quality scoring** — Calculate 0-100 quality score
- ✅ **Pipeline failure** — Stop pipeline if quality is too low
- ✅ **Audit logging** — All quality checks logged to audit trail
- ✅ **UI reporting** — Display quality issues in Streamlit dashboard

---

## Architecture

### Quality Scoring System

**Score Calculation (0-100):**
- Start at 100 points
- Deduct points based on issue severity:
  - **CRITICAL:** -10 points each (e.g., missing required columns)
  - **ERROR:** -5 points each (e.g., unexpected data types)
  - **WARNING:** -1 point each (e.g., null values above threshold)
  - **INFO:** -0.1 points each (e.g., minor anomalies)

**Example:**
```
100 (perfect score)
-  10 (1 critical issue: column missing)
-   5 (1 error issue: wrong data type)
-   3 (3 warning issues: nulls in columns)
=  82 (final score)

Threshold: 80 → PASS ✅
```

### Issue Severity Levels

| Severity | Impact | Example | Action |
|----------|--------|---------|--------|
| **CRITICAL** | Pipeline stops | Required column missing | Fail immediately |
| **ERROR** | Data unusable | All values wrong type | Review & retry |
| **WARNING** | Minor issue | Nulls exceed threshold | Review, consider continuing |
| **INFO** | FYI only | Numeric anomaly detected | Log for analysis |

---

## Core Components

### DataQualityChecker Class

```python
from core.data_quality import DataQualityChecker

# Initialize checker for a layer
checker = DataQualityChecker(run_id="pipeline-001", layer_name="bronze")

# Run validation
df = pd.read_parquet("data/bronze/customers.parquet")
quality_score = checker.validate(
    df,
    min_score=80.0,
    max_null_pct=5.0,
    critical_columns=["customer_id"],
    expected_rows=1000,
)

# Check results
if quality_score.passed:
    print(f"✅ Data quality passed: {quality_score.overall_score}/100")
else:
    print(f"❌ Data quality failed: {quality_score.overall_score}/100")
    for issue in quality_score.issues:
        print(f"  [{issue.severity}] {issue.message}")
```

### QualityScore Object

```python
@dataclass
class QualityScore:
    layer: str                  # "bronze", "silver", or "gold"
    total_rows: int            # Number of rows checked
    total_columns: int         # Number of columns
    issues: List[QualityIssue] # List of problems found
    overall_score: float       # 0-100 quality score
    passed: bool               # True if score >= min_score
    timestamp: str             # ISO format timestamp
```

### QualityIssue Object

```python
@dataclass
class QualityIssue:
    severity: str              # "critical", "error", "warning", "info"
    category: str              # "null_values", "row_count", "duplicates", etc.
    message: str               # Human-readable description
    affected_rows: int         # How many rows affected
    affected_columns: List[str] # Which columns affected
    value: Optional[float]     # Actual value found
    threshold: Optional[float] # Expected threshold
```

---

## Check Types

### 1. Null Value Checks

Detect missing data and validate critical columns.

```python
checker.check_null_values(
    df,
    max_null_pct=5.0,                    # Max nulls allowed (%)
    critical_columns=["customer_id"],    # Must not have nulls
)
```

**Example Issues:**
```
[WARNING] Column 'email' has 12% nulls (threshold: 5%)
[CRITICAL] Column 'customer_id' is critical but has 3 nulls (0.1%)
```

### 2. Row Count Validation

Detect data loss between layers.

```python
checker.check_row_count(
    df,
    min_rows=1,              # Minimum acceptable rows
    max_rows=1000000,        # Maximum acceptable rows
    expected_rows=50000,     # Expected row count (within 10% tolerance)
)
```

**Example Issues:**
```
[CRITICAL] Only 0 rows (minimum: 1)
[WARNING] 55,000 rows differs from expected 50,000 (tolerance: 5,000)
```

### 3. Duplicate Detection

Identify unexpected duplicate rows.

```python
checker.check_duplicates(
    df,
    key_columns=["customer_id", "transaction_id"],  # Check these columns
    max_duplicate_pct=1.0,  # Max % duplicates allowed
)
```

**Example Issues:**
```
[WARNING] 347 duplicate rows (2.1%, threshold: 1%)
```

### 4. Numeric Anomaly Detection

Find outliers in numeric columns using statistical analysis (Z-score).

```python
checker.check_numeric_anomalies(
    df,
    std_dev_threshold=3.0,  # Outliers > 3 std devs from mean
)
```

**Example Issues:**
```
[INFO] Column 'transaction_amount' has 12 outliers (0.8%) beyond 3 std devs
```

### 5. Data Type Validation

Verify columns have expected data types.

```python
checker.check_data_types(
    df,
    expected_types={
        "customer_id": "int",
        "name": "str",
        "created_at": "datetime",
    }
)
```

**Example Issues:**
```
[ERROR] Column 'customer_id' has type str (expected int)
[ERROR] Column 'email' not found (expected object)
```

### 6. Value Range Checking

Ensure numeric values fall within acceptable ranges.

```python
checker.check_value_ranges(
    df,
    ranges={
        "age": (0, 150),
        "transaction_amount": (0, 1000000),
        "discount_pct": (0, 100),
    }
)
```

**Example Issues:**
```
[WARNING] Column 'age' has 5 values below minimum 0
[WARNING] Column 'discount_pct' has 2 values above maximum 100
```

### 7. Required Column Verification

Ensure essential columns exist.

```python
checker.check_required_columns(
    df,
    required_columns=["customer_id", "email", "created_at"],
)
```

**Example Issues:**
```
[CRITICAL] Required column 'customer_id' is missing
[CRITICAL] Required column 'email' is missing
```

---

## Integration Points

### Phase 1: After Profiler

Check raw data is readable and not corrupted.

```python
from core.data_quality import DataQualityChecker

df_raw = pd.read_csv("uploads/customers.csv")
checker = DataQualityChecker(run_id, "raw")
quality = checker.validate(df_raw, min_score=70.0, min_rows=1)

if not quality.passed:
    raise ValueError(f"Raw data quality too low: {quality.overall_score}/100")
```

### Phase 2: After Bronze

Verify data types are enforced and metadata added.

```python
df_bronze = pd.read_parquet("data/bronze/customers.parquet")
checker = DataQualityChecker(run_id, "bronze")
quality = checker.validate(
    df_bronze,
    min_score=85.0,
    critical_columns=["_load_timestamp", "_source_file"],
    expected_rows=None,  # No expectation yet
)

if not quality.passed:
    st.error(f"Bronze quality failed: {quality.overall_score}/100")
    for issue in quality.issues:
        st.write(f"  [{issue.severity}] {issue.message}")
```

### Phase 3: After Silver

Verify cleaning was effective.

```python
df_silver = pd.read_parquet("data/silver/customers.parquet")
checker = DataQualityChecker(run_id, "silver")
quality = checker.validate(
    df_silver,
    min_score=90.0,
    max_null_pct=2.0,  # Stricter after cleaning
    critical_columns=["customer_id"],
    dup_max_duplicate_pct=0.1,  # After dedup
)

if not quality.passed:
    raise ValueError(f"Silver quality failed: {quality.overall_score}/100")
```

### Phase 4: After Gold

Verify analytics tables are ready for reporting.

```python
gold_tables = ["customers", "orders", "products"]
for table_name in gold_tables:
    df_gold = pd.read_parquet(f"data/gold/{table_name}.parquet")
    checker = DataQualityChecker(run_id, f"gold_{table_name}")
    quality = checker.validate(
        df_gold,
        min_score=95.0,  # Strictest for analytics
        max_null_pct=0.0,  # No nulls in analytics
        critical_columns=["_surrogate_key"],
    )
    
    if not quality.passed:
        logger.log("data_quality", "gold_validation_failed", 
                  table=table_name, score=quality.overall_score)
```

---

## UI Integration (Streamlit)

Display quality reports in the web interface.

### Phase Completion Screen

```python
import streamlit as st
from core.data_quality import DataQualityChecker

# After bronze processing
df_bronze = pd.read_parquet(bronze_output_path)
checker = DataQualityChecker(run_id, "bronze")
quality = checker.validate(df_bronze, min_score=85.0)

# Display quality report
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Quality Score", f"{quality.overall_score:.0f}/100")
with col2:
    st.metric("Total Rows", f"{quality.total_rows:,}")
with col3:
    st.metric("Total Columns", quality.total_columns)

# Show issues
if quality.issues:
    st.subheader("Quality Issues")
    for issue in quality.issues:
        severity_color = {
            "critical": "🔴",
            "error": "🟠",
            "warning": "🟡",
            "info": "⚪",
        }
        emoji = severity_color.get(issue.severity, "❓")
        st.warning(f"{emoji} [{issue.severity}] {issue.message}")
else:
    st.success("✅ No quality issues found")

# Show pass/fail status
if quality.passed:
    st.success(f"✅ Quality check PASSED ({quality.overall_score}/100)")
else:
    st.error(f"❌ Quality check FAILED ({quality.overall_score}/100)")
```

### Quality Dashboard Tab

```python
st.subheader("Data Quality Report")

# Load all quality checks from audit trail
quality_logs = load_quality_logs_from_audit(run_id)

# Chart quality scores over phases
phases = [log["layer"] for log in quality_logs]
scores = [log["score"] for log in quality_logs]

st.line_chart(data=pd.DataFrame({
    "Phase": phases,
    "Quality Score": scores,
}))

# Detailed issues table
st.subheader("All Quality Issues")
all_issues = []
for log in quality_logs:
    for issue in log.get("issues", []):
        all_issues.append({
            "Phase": log["layer"],
            "Severity": issue["severity"],
            "Category": issue["category"],
            "Message": issue["message"],
            "Affected Rows": issue.get("affected_rows", 0),
        })

st.dataframe(pd.DataFrame(all_issues), use_container_width=True)
```

---

## Pipeline Failure Logic

### Fail the Pipeline if Quality is Too Low

```python
# In agents/orchestrator.py
def run_gold_and_report(
    silver_output_paths: list[str],
    gold_sttm_path: str,
    run_id: str,
) -> dict:
    """Execute Gold layer with quality gate."""
    logger = AuditLogger(run_id)
    
    try:
        # Generate Gold tables
        gold_output_paths = execute_gold(
            silver_output_paths,
            gold_sttm_path,
            run_id,
        )
        
        # ✨ NEW: Quality check
        total_rows_before = 0
        for gold_path in gold_output_paths:
            df = pd.read_parquet(gold_path)
            
            # Check quality
            checker = DataQualityChecker(run_id, f"gold_{Path(gold_path).stem}")
            quality = checker.validate(
                df,
                min_score=95.0,  # Strict for analytics
                max_null_pct=0.0,  # No nulls in analytics
            )
            
            # Log quality result
            logger.log(
                "data_quality",
                "gold_quality_check",
                table=Path(gold_path).stem,
                score=quality.overall_score,
                passed=quality.passed,
                issues=len(quality.issues),
            )
            
            # Fail pipeline if quality too low
            if not quality.passed:
                raise ValueError(
                    f"Gold layer quality too low for {Path(gold_path).stem}: "
                    f"{quality.overall_score}/100 (required: 95.0)"
                )
            
            total_rows_before += quality.total_rows
        
        # Continue with reporting
        return {
            "status": "success",
            "gold_tables": gold_output_paths,
            "quality_passed": True,
        }
    
    except ValueError as quality_error:
        # Quality check failed
        logger.log(
            "data_quality",
            "gold_quality_failed",
            error=str(quality_error),
        )
        raise
```

---

## Configuration

### Default Thresholds (Bronze Layer)

```python
BRONZE_DEFAULTS = {
    "min_score": 80.0,           # Minimum quality score
    "max_null_pct": 10.0,        # Max null percentage
    "max_duplicate_pct": 5.0,    # Max duplicate percentage
    "std_dev_threshold": 3.0,    # Outlier detection (std devs)
    "min_rows": 1,               # Minimum row count
}
```

### Default Thresholds (Silver Layer)

```python
SILVER_DEFAULTS = {
    "min_score": 90.0,           # Stricter than Bronze
    "max_null_pct": 2.0,         # After cleaning
    "max_duplicate_pct": 0.1,    # After dedup
    "critical_columns": ["id"],  # Must not have nulls
}
```

### Default Thresholds (Gold Layer)

```python
GOLD_DEFAULTS = {
    "min_score": 95.0,           # Strictest (analytics-ready)
    "max_null_pct": 0.0,         # No nulls in analytics
    "max_duplicate_pct": 0.0,    # No duplicates
    "critical_columns": ["_surrogate_key"],
}
```

### Custom Configuration via .env (Future)

```bash
# In .env (for future enhancement)
DATA_QUALITY_BRONZE_MIN_SCORE=80.0
DATA_QUALITY_SILVER_MIN_SCORE=90.0
DATA_QUALITY_GOLD_MIN_SCORE=95.0
DATA_QUALITY_MAX_NULL_PCT=5.0
DATA_QUALITY_FAIL_ON_CRITICAL=true
```

---

## Audit Trail Logging

All quality checks are logged to `audit_logs/{run_id}.jsonl`.

### Example Audit Log Entry

```json
{
  "timestamp": "2024-01-10T15:30:45.123456Z",
  "run_id": "pipeline-001",
  "agent": "data_quality",
  "action": "bronze_validation",
  "score": 92.5,
  "passed": true,
  "issue_count": 2,
  "critical_issues": 0,
  "error_issues": 0,
  "warning_issues": 2,
  "issues": [
    {
      "severity": "warning",
      "category": "null_values",
      "message": "Column 'email' has 5.2% nulls (threshold: 5%)",
      "affected_rows": 52,
      "affected_columns": ["email"],
      "value": 5.2,
      "threshold": 5.0
    }
  ]
}
```

### Query Quality Logs

```bash
# View all quality checks in a run
cat audit_logs/pipeline-001.jsonl | grep data_quality

# Get summary statistics
grep "data_quality" audit_logs/pipeline-001.jsonl | \
  jq '.score' | \
  stats

# Find all critical issues
grep "data_quality" audit_logs/pipeline-001.jsonl | \
  jq 'select(.critical_issues > 0)'
```

---

## Testing

### Run Quality Tests

```bash
pytest tests/test_data_quality.py -v

# With coverage
pytest tests/test_data_quality.py --cov=core.data_quality --cov-report=html

# Specific test class
pytest tests/test_data_quality.py::TestNullValuesCheck -v
```

### Test Results

```
35 passed, 1 warning in 1.18s ✅

Test Coverage:
  - QualityIssue dataclass (3 tests)
  - QualityScore dataclass (2 tests)
  - Null value checking (3 tests)
  - Row count validation (5 tests)
  - Duplicate detection (2 tests)
  - Numeric anomalies (2 tests)
  - Data type validation (2 tests)
  - Value range checking (3 tests)
  - Required columns (2 tests)
  - Score calculation (4 tests)
  - Full validation flow (4 tests)
  - Summary generation (2 tests)
  - Initialization (1 test)
```

---

## Examples

### Example 1: Simple Validation

```python
from core.data_quality import DataQualityChecker
import pandas as pd

# Load data
df = pd.read_parquet("data/bronze/customers.parquet")

# Check quality
checker = DataQualityChecker("run-123", "bronze")
quality = checker.validate(df, min_score=80.0)

# Report
print(quality.get_summary())
print(f"Score: {quality.overall_score}/100")
print(f"Passed: {quality.passed}")
```

### Example 2: Custom Checks

```python
checker = DataQualityChecker("run-123", "silver")

# Run specific checks
checker.check_null_values(df, critical_columns=["customer_id"])
checker.check_duplicates(df, key_columns=["customer_id"])
checker.check_value_ranges(df, ranges={"age": (0, 150)})

# Calculate score
score = checker.calculate_score(critical_weight=10, warning_weight=1)
print(f"Quality score: {score}/100")
```

### Example 3: Integration with Agent

```python
def execute_silver(
    input_files: list[str],
    sttm_path: str,
    run_id: str,
) -> list[str]:
    """Execute Silver layer with quality gate."""
    # ... silver processing ...
    
    output_paths = []
    for output_path in output_files:
        df = pd.read_parquet(output_path)
        
        # Check quality
        checker = DataQualityChecker(run_id, "silver")
        quality = checker.validate(df, min_score=90.0, max_null_pct=2.0)
        
        if not quality.passed:
            raise ValueError(f"Silver quality failed: {quality.overall_score}/100")
        
        output_paths.append(output_path)
    
    return output_paths
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `Quality score 0/100` | All checks failed | Review data schema and types |
| `Numeric anomalies not detected` | std_dev_threshold too high | Lower threshold (default 3.0) |
| `All nulls marked critical` | critical_columns includes columns with expected nulls | Review critical_columns list |
| `Row count warning` | Data loss between layers | Check transformation logic |
| `Duplicates marked as error` | Duplicate keys allowed | Adjust max_duplicate_pct |
| `Pipeline fails unexpectedly` | min_score threshold too strict | Lower threshold temporarily for testing |

---

## Best Practices

1. **Start Lenient (Bronze), End Strict (Gold)**
   - Bronze: 80+ score
   - Silver: 90+ score
   - Gold: 95+ score

2. **Define Critical Columns Early**
   - What columns must never have nulls?
   - Document in STTM or agent prompts

3. **Set Realistic Thresholds**
   - 0-5% nulls often acceptable
   - 0-1% duplicates acceptable
   - Adjust based on domain

4. **Review Failed Checks**
   - Don't automatically retry
   - Understand root cause
   - Fix data or thresholds accordingly

5. **Log Everything**
   - All quality checks go to audit trail
   - Trace issues back to source
   - Build data lineage

6. **Monitoring & Alerts**
   - Email alerts on critical failures
   - Dashboard for quality trends
   - Set up weekly quality reports

---

## Summary

✅ **The data quality module provides:**
- 7 check types covering common data issues
- Automatic anomaly detection
- Quality scoring (0-100)
- Pipeline failure gates
- Comprehensive audit logging
- Streamlit UI integration
- 35 passing tests

**You can now:**
1. Automatically validate data at each layer
2. Detect anomalies (outliers, nulls, duplicates)
3. Fail the pipeline if quality is too low
4. Report issues in the UI
5. Track data quality over time via audit logs

Happy quality checking! 🎯
