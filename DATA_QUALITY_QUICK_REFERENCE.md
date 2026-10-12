# Data Quality - Quick Reference

## Core Module

```python
from core.data_quality import DataQualityChecker

checker = DataQualityChecker(run_id="run-001", layer_name="bronze")
quality = checker.validate(df, min_score=85.0)
```

## Check Types

| Check | Method | Example |
|-------|--------|---------|
| Null values | `check_null_values()` | 5% nulls in column |
| Row count | `check_row_count()` | Lost rows between layers |
| Duplicates | `check_duplicates()` | 2% duplicate rows |
| Anomalies | `check_numeric_anomalies()` | Outliers > 3 std devs |
| Data types | `check_data_types()` | Wrong column type |
| Value ranges | `check_value_ranges()` | Values outside bounds |
| Required cols | `check_required_columns()` | Missing column |

## Quality Scoring

**Score Calculation:**
- Start: 100 points
- CRITICAL: -10 pts each
- ERROR: -5 pts each
- WARNING: -1 pt each
- INFO: -0.1 pts each

**Thresholds:**
| Layer | Min Score | Max Nulls | Duplicates |
|-------|-----------|-----------|-----------|
| Bronze | 85% | 10% | 5% |
| Silver | 90% | 2% | 0.1% |
| Gold | 95% | 0% | 0% |

## Common Issues

```python
# Check for nulls
checker.check_null_values(
    df,
    max_null_pct=5.0,
    critical_columns=["id"],
)

# Check row count
checker.check_row_count(
    df,
    min_rows=1,
    expected_rows=50000,  # within 10% tolerance
)

# Check duplicates
checker.check_duplicates(
    df,
    key_columns=["customer_id"],
    max_duplicate_pct=1.0,
)

# Check anomalies
checker.check_numeric_anomalies(
    df,
    std_dev_threshold=3.0,
)

# Check types
checker.check_data_types(
    df,
    expected_types={"id": "int", "name": "str"},
)

# Check ranges
checker.check_value_ranges(
    df,
    ranges={"age": (0, 150)},
)

# Check required
checker.check_required_columns(
    df,
    required_columns=["id", "email"],
)
```

## Full Validation

```python
# Automatic all checks
quality = checker.validate(
    df,
    min_score=85.0,
    max_null_pct=5.0,
    max_duplicate_pct=1.0,
    critical_columns=["id"],
    expected_types={"id": "int"},
    ranges={"age": (0, 150)},
    required_columns=["id"],
)

# Check results
print(f"Score: {quality.overall_score}/100")
print(f"Passed: {quality.passed}")
print(f"Issues: {len(quality.issues)}")

for issue in quality.issues:
    print(f"  [{issue.severity}] {issue.message}")
```

## Fail Pipeline

```python
if not quality.passed:
    raise ValueError(
        f"Quality too low: {quality.overall_score}/100 "
        f"(required: 85.0)"
    )
```

## Streamlit UI

```python
import streamlit as st

# Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Quality", f"{quality.overall_score:.0f}/100")
with col2:
    st.metric("Rows", f"{quality.total_rows:,}")
with col3:
    st.metric("Issues", len(quality.issues))

# Issues table
if quality.issues:
    st.subheader("Quality Issues")
    for issue in quality.issues:
        st.warning(f"[{issue.severity}] {issue.message}")
else:
    st.success("✅ No issues")

# Pass/fail
if quality.passed:
    st.success("✅ Quality PASSED")
else:
    st.error("❌ Quality FAILED")
```

## Audit Logging

All checks logged to `audit_logs/{run_id}.jsonl`:

```bash
# View quality checks
grep "data_quality" audit_logs/run-001.jsonl | jq .

# Extract scores
grep "data_quality" audit_logs/run-001.jsonl | jq '.score'

# Find failures
grep "data_quality" audit_logs/*.jsonl | jq 'select(.passed == false)'
```

## Tests

```bash
# Run all tests
pytest tests/test_data_quality.py -v

# Run specific test
pytest tests/test_data_quality.py::TestNullValuesCheck -v

# With coverage
pytest tests/test_data_quality.py --cov=core.data_quality --cov-report=html
```

**Results:** 35/35 tests passing ✅

## Integration Points

### After Bronze
```python
df = pd.read_parquet("data/bronze/table.parquet")
checker = DataQualityChecker(run_id, "bronze")
quality = checker.validate(df, min_score=85.0)
if not quality.passed:
    raise ValueError(f"Bronze failed: {quality.overall_score}/100")
```

### After Silver
```python
df = pd.read_parquet("data/silver/table.parquet")
checker = DataQualityChecker(run_id, "silver")
quality = checker.validate(df, min_score=90.0, max_null_pct=2.0)
if not quality.passed:
    raise ValueError(f"Silver failed: {quality.overall_score}/100")
```

### After Gold
```python
df = pd.read_parquet("data/gold/table.parquet")
checker = DataQualityChecker(run_id, "gold_table")
quality = checker.validate(df, min_score=95.0, max_null_pct=0.0)
if not quality.passed:
    raise ValueError(f"Gold failed: {quality.overall_score}/100")
```

## Result Dataclass

```python
@dataclass
class QualityScore:
    layer: str                  # "bronze", "silver", "gold"
    total_rows: int            # Row count
    total_columns: int         # Column count
    issues: List[QualityIssue] # Problems found
    overall_score: float       # 0-100
    passed: bool               # score >= min_score
    timestamp: str             # ISO timestamp
    
    # Methods:
    # to_dict() → serializable dict
```

## Issue Dataclass

```python
@dataclass
class QualityIssue:
    severity: str              # "critical", "error", "warning", "info"
    category: str              # "null_values", "row_count", etc.
    message: str               # Human description
    affected_rows: int         # Count
    affected_columns: List[str] # Column names
    value: Optional[float]     # Actual value
    threshold: Optional[float] # Expected value
    
    # Methods:
    # to_dict() → serializable dict
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Score 0/100 | All checks failed | Review schema |
| No anomalies detected | Threshold too high | Lower std_dev_threshold |
| Too many warnings | Thresholds too strict | Increase max_null_pct |
| Pipeline fails unexpectedly | min_score too high | Lower for testing |

## Best Practices

1. **Progressive Strictness**
   - Bronze: 80-85 (lenient)
   - Silver: 90 (strict)
   - Gold: 95 (very strict)

2. **Define Critical Columns**
   - Never null: IDs, dates
   - Uniqueness: customer_id, email

3. **Set Realistic Thresholds**
   - 5-10% nulls ok in raw
   - 0-1% duplicates ok after cleaning

4. **Review Failures**
   - Understand root cause
   - Fix data or thresholds
   - Don't ignore critical issues

5. **Monitor Trends**
   - Track scores over time
   - Set up alerts
   - Review weekly

---

**Documentation:** [DATA_QUALITY_GUIDE.md](DATA_QUALITY_GUIDE.md)
**Implementation:** [core/data_quality.py](core/data_quality.py)
**Tests:** [tests/test_data_quality.py](tests/test_data_quality.py)

**35/35 tests passing ✅**
