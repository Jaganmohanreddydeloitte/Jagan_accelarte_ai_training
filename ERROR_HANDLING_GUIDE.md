# Pipeline Error Handling & Retry System - Complete Guide

Comprehensive error handling for IDAMP pipeline with custom exceptions, automatic retries, and error recovery.

---

## Overview

The error handling system provides:

✅ **Custom Exception Classes** — Domain-specific errors for different failure types
✅ **Automatic Retries** — Configurable retry with exponential backoff
✅ **Detailed Error Messages** — User-friendly messages with context
✅ **Error Logging** — Full error logs with stack traces and context
✅ **Recovery Management** — Save/load state to retry from failed step
✅ **Streamlit UI** — Display errors and recovery options in UI

---

## Quick Start

### 1. Raise Descriptive Errors

```python
from core.error_handling import (
    ValidationError,
    DataQualityError,
    TransformationError,
    APIError,
)

# Validation error
if not df.shape[0] > 0:
    raise ValidationError(
        message="Input dataframe is empty",
        phase="bronze",
        step="load_data",
        context={"expected_rows": ">0", "actual_rows": 0},
    )

# Data quality error
if quality_score < min_score:
    raise DataQualityError(
        message=f"Quality score too low",
        quality_score=quality_score,
        min_score=min_score,
        phase="silver",
        step="validate",
    )

# Transformation error
try:
    result = transform_function(value)
except Exception as e:
    raise TransformationError(
        message="Failed to apply transformation",
        transform_name="scale_price",
        row_index=5,
        column="price",
        phase="gold",
        step="transform",
        cause=e,
    )
```

### 2. Retry Failed Operations

```python
from core.error_handling import Retry, RetryPolicy

# Define retry policy
policy = RetryPolicy(
    max_retries=3,
    initial_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
)

# Use as decorator
@Retry(policy)
def fetch_from_api():
    # Will retry on API/timeout errors
    response = requests.get("https://api.example.com/data")
    return response.json()

result = fetch_from_api()  # Automatic retries
```

### 3. Log and Recover from Errors

```python
from core.error_handling import ErrorLogger, RecoveryState

error_logger = ErrorLogger(Path("error_logs"))
recovery = RecoveryState(Path("recovery_state"))

try:
    result = process_data(df)
except Exception as e:
    # Create error context
    error_context = ErrorContext(
        error=e,
        run_id="run-001",
        phase="bronze",
        step="process",
    )
    
    # Log error
    error_logger.log_error(error_context)
    
    # Save recovery state
    recovery.save_state("run-001", "bronze", {
        "processed_rows": 500,
        "total_rows": 1000,
    })
    
    # Later, load state and retry
    saved_state = recovery.load_state("run-001", "bronze")
    start_from_row = saved_state["processed_rows"]
    result = process_data(df.iloc[start_from_row:])
```

### 4. Display Errors in Streamlit

```python
import streamlit as st
from core.error_ui import PipelineErrorUI

# Initialize
PipelineErrorUI.initialize_session()

# Handle error
try:
    result = do_something()
except Exception as e:
    error_context = PipelineErrorUI.handle_error(
        error=e,
        run_id="run-001",
        phase="bronze",
        step="load_data",
        error_logger=error_logger,
    )
    
    # Show recovery options
    st.markdown("---")
    PipelineErrorUI.render_recovery_options(error_context)
```

---

## Exception Hierarchy

```
Exception
└── PipelineException (base class)
    ├── ValidationError           # Input validation failed
    ├── DataQualityError         # Quality check failed
    ├── TransformationError      # Data transformation failed
    ├── IOError                  # File I/O error
    ├── DatabaseError            # Database error
    ├── APIError                 # External API error
    ├── AuthenticationError      # Auth/permission error (implicit)
    └── TimeoutError             # Operation timed out
```

---

## Custom Exception Classes

### PipelineException (Base)

```python
from core.error_handling import PipelineException, ErrorCategory, ErrorSeverity

exc = PipelineException(
    message="Something went wrong",
    category=ErrorCategory.UNKNOWN,
    severity=ErrorSeverity.ERROR,
    phase="bronze",           # Which phase failed
    step="load_data",         # Which step failed
    context={                 # Additional context
        "file": "data.csv",
        "rows": 1000,
    },
    cause=original_exception, # Root cause
)

# Get user-friendly message
msg = exc.get_user_message()
# → "❌ in bronze > load_data: Something went wrong"

# Get recovery suggestion
suggestion = exc.get_recovery_suggestion()
# → "Check file paths and permissions"
```

### ValidationError

```python
from core.error_handling import ValidationError

raise ValidationError(
    message="Missing required column 'email'",
    phase="bronze",
    step="validate_schema",
    context={"missing_columns": ["email", "phone"]},
)
```

### DataQualityError

```python
from core.error_handling import DataQualityError

raise DataQualityError(
    message="Quality score below threshold",
    quality_score=75.0,
    min_score=85.0,
    phase="silver",
    step="quality_check",
)
```

### TransformationError

```python
from core.error_handling import TransformationError

raise TransformationError(
    message="Failed to transform value",
    transform_name="scale_price",
    row_index=42,
    column="price",
    phase="gold",
    step="apply_rules",
)
```

### IOError

```python
from core.error_handling import IOError as PipelineIOError

raise PipelineIOError(
    message="Failed to read file",
    filepath="/path/to/data.csv",
    operation="read",
    phase="bronze",
)
```

### DatabaseError

```python
from core.error_handling import DatabaseError

raise DatabaseError(
    message="Failed to insert records",
    table="customers",
    operation="insert",
    phase="gold",
)
```

### APIError

```python
from core.error_handling import APIError

raise APIError(
    message="API rate limit exceeded",
    api_name="google_api",
    status_code=429,
    phase="bronze",
)
```

### TimeoutError

```python
from core.error_handling import TimeoutError as PipelineTimeoutError

raise PipelineTimeoutError(
    message="Operation timed out",
    timeout_seconds=30,
    phase="silver",
)
```

---

## Retry Logic

### Retry Policy Configuration

```python
from core.error_handling import RetryPolicy

policy = RetryPolicy(
    max_retries=3,                 # 3 retry attempts (+ 1 initial = 4 total)
    initial_delay=1.0,             # Start with 1 second
    max_delay=60.0,                # Cap at 60 seconds
    exponential_base=2.0,          # Double delay each time
    jitter=True,                   # Add randomness to prevent thundering herd
    retryable_categories=[
        ErrorCategory.API,
        ErrorCategory.DATABASE,
        ErrorCategory.TIMEOUT,
        ErrorCategory.RESOURCE,
    ],
)

# Usage:
@Retry(policy)
def fetch_data():
    return requests.get("https://api.example.com/data").json()
```

### Exponential Backoff

```python
# With initial_delay=1.0, exponential_base=2.0:
# Attempt 1: Delay = 1 * 2^0 = 1 second
# Attempt 2: Delay = 1 * 2^1 = 2 seconds
# Attempt 3: Delay = 1 * 2^2 = 4 seconds
# Attempt 4: Delay = 1 * 2^3 = 8 seconds
```

### Retry Decorator

```python
from core.error_handling import Retry, RetryPolicy

policy = RetryPolicy(max_retries=3, initial_delay=1.0)

@Retry(policy)
def call_external_api():
    """This will be retried up to 3 times on retryable errors"""
    response = requests.get("https://api.example.com/data")
    if response.status_code != 200:
        raise APIError(
            message=f"API returned {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()

# Non-retryable errors fail immediately
@Retry(policy)
def validate_input(df):
    if df.empty:
        raise ValidationError("Input dataframe is empty")  # Not retried
    return df

# Retryable errors are retried
@Retry(policy)
def call_database():
    # APIError, DatabaseError, TimeoutError → RETRIED
    # ValidationError → NOT retried
    pass
```

---

## Error Logging

### Log Errors

```python
from core.error_handling import ErrorLogger, ErrorContext

logger = ErrorLogger(Path("error_logs"))

exc = PipelineException(
    message="Processing failed",
    phase="bronze",
)

ctx = ErrorContext(
    error=exc,
    run_id="run-001",
    username="alice",
    phase="bronze",
    step="load_data",
    input_data={"file": "data.csv"},
)

# Log to file
filepath = logger.log_error(ctx)
# Saved to: error_logs/error_run-001_20241007_174806.json
```

### Log Format

```json
{
  "error": {
    "message": "Processing failed",
    "category": "transformation",
    "severity": "error",
    "phase": "bronze",
    "step": "load_data",
    "context": {"file": "data.csv"},
    "timestamp": "2024-10-07T17:48:06.023Z",
    "traceback": "Traceback (most recent call last): ..."
  },
  "run_id": "run-001",
  "username": "alice",
  "phase": "bronze",
  "step": "load_data",
  "input_data": {"file": "data.csv"},
  "attempt_number": 1,
  "max_attempts": 3,
  "can_retry": true,
  "created_at": "2024-10-07T17:48:06.023Z"
}
```

### Retrieve Logs

```python
logger = ErrorLogger(Path("error_logs"))

# Get all error logs for a run
logs = logger.get_error_logs("run-001")

for log in logs:
    print(f"{log['created_at']}: {log['error']['message']}")
```

---

## Recovery State Management

### Save Recovery State

```python
from core.error_handling import RecoveryState

recovery = RecoveryState(Path("recovery_state"))

# Save state before processing
state = {
    "last_processed_row": 500,
    "checkpoint": "data_cleaned",
    "processed_count": 500,
    "total_count": 1000,
}

recovery.save_state("run-001", "bronze", state)
# Saved to: recovery_state/run-001_bronze_state.json
```

### Load Recovery State

```python
recovery = RecoveryState(Path("recovery_state"))

# Check if state exists
if recovery.has_state("run-001", "bronze"):
    # Load state
    state = recovery.load_state("run-001", "bronze")
    
    # Use to resume processing
    start_row = state["last_processed_row"]
    remaining_data = df.iloc[start_row:]
    result = process_data(remaining_data)
```

### Clear State

```python
recovery = RecoveryState(Path("recovery_state"))

# Clear specific phase
recovery.clear_state("run-001", "bronze")

# Clear all phases for run
recovery.clear_state("run-001")
```

---

## Streamlit Error UI

### Display Error

```python
from core.error_ui import PipelineErrorUI

# Handle error
try:
    result = do_something()
except Exception as e:
    error_context = PipelineErrorUI.handle_error(
        error=e,
        run_id="run-001",
        phase="bronze",
        step="load_data",
        username="alice",
        error_logger=error_logger,
    )
```

### Show Recovery Options

```python
# Render recovery interface
choice = PipelineErrorUI.render_recovery_options(error_context)

if choice == "retry":
    # Retry operation
    pass
elif choice == "skip":
    # Skip and continue
    pass
elif choice == "abort":
    # Abort pipeline
    pass
```

### Display Error History

```python
error_history = st.session_state.get(PipelineErrorUI.KEY_ERROR_HISTORY, [])

# Show table of errors
PipelineErrorUI.render_error_history(error_history, run_id="run-001")

# Show detailed view
PipelineErrorUI.render_error_display(error_history[-1])
```

### Recovery State Viewer

```python
# View available recovery states
PipelineErrorUI.render_recovery_state_viewer(Path("recovery_state"))
```

---

## Error Categories & Severity

### Error Categories

```python
from core.error_handling import ErrorCategory

ErrorCategory.VALIDATION          # Input validation
ErrorCategory.DATA_QUALITY        # Quality check
ErrorCategory.TRANSFORMATION      # Data transform
ErrorCategory.IO                  # File I/O
ErrorCategory.DATABASE            # Database
ErrorCategory.API                 # External API
ErrorCategory.AUTHENTICATION      # Auth/permission
ErrorCategory.RESOURCE            # Resource limit
ErrorCategory.TIMEOUT             # Timeout
ErrorCategory.UNKNOWN             # Unknown
```

### Error Severity

```python
from core.error_handling import ErrorSeverity

ErrorSeverity.INFO                # Information
ErrorSeverity.WARNING             # Warning
ErrorSeverity.ERROR               # Error
ErrorSeverity.CRITICAL            # Critical
```

---

## Complete Example

```python
import streamlit as st
import pandas as pd
from pathlib import Path

from core.error_handling import (
    ValidationError,
    DataQualityError,
    RetryPolicy,
    Retry,
    ErrorLogger,
    RecoveryState,
)
from core.error_ui import PipelineErrorUI

# Initialize
error_logger = ErrorLogger(Path("error_logs"))
recovery = RecoveryState(Path("recovery_state"))
PipelineErrorUI.initialize_session()

# Define retry policy
policy = RetryPolicy(max_retries=3, initial_delay=1.0)

# Retryable function
@Retry(policy)
def load_data_from_api():
    """Fetch data with automatic retries"""
    # Simulates API call that might fail
    return pd.DataFrame({"id": [1, 2, 3], "name": ["A", "B", "C"]})

# Process pipeline
try:
    # Step 1: Load data
    st.info("Step 1: Loading data...")
    try:
        df = load_data_from_api()
    except Exception as e:
        raise ValidationError(
            message="Failed to load data",
            phase="bronze",
            step="load_data",
            cause=e,
        )

    # Step 2: Validate
    st.info("Step 2: Validating data...")
    if df.empty:
        raise ValidationError(
            message="Input dataframe is empty",
            phase="bronze",
            step="validate",
            context={"expected_rows": ">0"},
        )

    # Save recovery state
    recovery.save_state("run-001", "bronze", {
        "loaded_rows": len(df),
        "stage": "validated",
    })

    # Step 3: Transform
    st.info("Step 3: Transforming data...")
    df["name"] = df["name"].str.upper()

    st.success("✅ Pipeline completed successfully!")

except Exception as e:
    # Handle error
    error_context = PipelineErrorUI.handle_error(
        error=e,
        run_id="run-001",
        phase="bronze",
        username="alice",
        error_logger=error_logger,
    )

    # Show recovery options
    st.markdown("---")
    choice = PipelineErrorUI.render_recovery_options(error_context)

    if choice == "retry":
        st.info("Retrying...")
        st.rerun()
    elif choice == "skip":
        st.warning("Skipping to next step...")
```

---

## Best Practices

### ✅ DO:

1. **Always provide context** — Include phase, step, and relevant data
2. **Use specific exceptions** — Don't always use PipelineException
3. **Add recovery suggestions** — Make errors actionable
4. **Log before raising** — Capture error state
5. **Save checkpoint state** — Enable recovery
6. **Test retry logic** — Ensure retries work
7. **Monitor error rates** — Track patterns

### ❌ DON'T:

1. Don't ignore errors — Always handle and log
2. Don't retry everything — Only retry transient errors
3. Don't expose stack traces to users — Use get_user_message()
4. Don't lose context — Pass phase/step info
5. Don't retry forever — Set max_retries limit
6. Don't forget to clean up state — Clear old recovery states

---

## Summary

✅ **Custom exceptions** provide domain-specific error handling
✅ **Retry logic** handles transient failures automatically
✅ **Detailed logging** captures full error context
✅ **Recovery state** enables resuming from failures
✅ **Streamlit UI** displays errors and recovery options
✅ **38 passing tests** ensure reliability

---

See [core/error_handling.py](core/error_handling.py) and [core/error_ui.py](core/error_ui.py) for implementation.
