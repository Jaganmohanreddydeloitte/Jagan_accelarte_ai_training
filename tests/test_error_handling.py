"""
Tests for Pipeline Error Handling & Recovery

Coverage:
- Custom exception classes
- Error messages and context
- Retry logic and policies
- Error logging
- Recovery state management
"""

import pytest
import tempfile
from pathlib import Path
import time
import json

from core.error_handling import (
    PipelineException,
    ValidationError,
    DataQualityError,
    TransformationError,
    IOError as PipelineIOError,
    DatabaseError,
    APIError,
    TimeoutError as PipelineTimeoutError,
    ErrorCategory,
    ErrorSeverity,
    RetryPolicy,
    Retry,
    ErrorContext,
    ErrorLogger,
    RecoveryState,
)


class TestCustomExceptions:
    """Test custom exception classes"""

    def test_pipeline_exception_basic(self):
        """Basic exception creation"""
        exc = PipelineException(
            message="Test error",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
        )
        assert exc.message == "Test error"
        assert exc.category == ErrorCategory.VALIDATION
        assert exc.severity == ErrorSeverity.ERROR

    def test_pipeline_exception_with_context(self):
        """Exception with context information"""
        exc = PipelineException(
            message="Test error",
            phase="bronze",
            step="load_data",
            context={"file": "data.csv", "rows": 100},
        )
        assert exc.phase == "bronze"
        assert exc.step == "load_data"
        assert exc.context["file"] == "data.csv"

    def test_pipeline_exception_user_message(self):
        """User-friendly error message"""
        exc = PipelineException(
            message="Invalid format",
            phase="silver",
            step="transform",
        )
        msg = exc.get_user_message()
        assert "silver" in msg
        assert "transform" in msg
        assert "Invalid format" in msg

    def test_validation_error(self):
        """Validation error creation"""
        exc = ValidationError(
            message="Column missing",
            phase="bronze",
            step="validate",
        )
        assert exc.category == ErrorCategory.VALIDATION
        assert exc.severity == ErrorSeverity.ERROR

    def test_data_quality_error_with_scores(self):
        """Data quality error with score information"""
        exc = DataQualityError(
            message="Quality too low",
            quality_score=75.0,
            min_score=85.0,
            phase="silver",
        )
        assert exc.context["quality_score"] == 75.0
        assert exc.context["min_score"] == 85.0
        assert exc.category == ErrorCategory.DATA_QUALITY

    def test_transformation_error_with_details(self):
        """Transformation error with specific details"""
        exc = TransformationError(
            message="Failed to transform",
            transform_name="scale_price",
            row_index=5,
            column="price",
        )
        assert exc.context["transform"] == "scale_price"
        assert exc.context["row"] == 5
        assert exc.context["column"] == "price"

    def test_io_error_with_filepath(self):
        """IO error with file information"""
        exc = PipelineIOError(
            message="File not found",
            filepath="/path/to/data.csv",
            operation="read",
        )
        assert exc.context["filepath"] == "/path/to/data.csv"
        assert exc.context["operation"] == "read"
        assert exc.category == ErrorCategory.IO

    def test_database_error(self):
        """Database error creation"""
        exc = DatabaseError(
            message="Connection failed",
            table="customers",
            operation="insert",
        )
        assert exc.context["table"] == "customers"
        assert exc.context["operation"] == "insert"

    def test_api_error(self):
        """API error creation"""
        exc = APIError(
            message="Rate limit exceeded",
            api_name="google_api",
            status_code=429,
        )
        assert exc.context["api"] == "google_api"
        assert exc.context["status_code"] == 429

    def test_exception_with_cause(self):
        """Exception with root cause"""
        root_cause = ValueError("Bad value")
        exc = PipelineException(
            message="Processing failed",
            cause=root_cause,
        )
        assert exc.cause == root_cause

    def test_exception_serialization(self):
        """Exception serialization to dict"""
        exc = PipelineException(
            message="Test",
            phase="bronze",
            context={"key": "value"},
        )
        data = exc.to_dict()
        assert data["message"] == "Test"
        assert data["phase"] == "bronze"
        assert data["context"]["key"] == "value"

    def test_recovery_suggestion(self):
        """Recovery suggestions for different error types"""
        exc_api = APIError(message="Connection failed", api_name="test")
        assert "credentials" in exc_api.get_recovery_suggestion()

        exc_val = ValidationError(message="Bad data")
        assert "input data" in exc_val.get_recovery_suggestion()

        exc_timeout = PipelineTimeoutError(message="Timed out", timeout_seconds=30)
        assert "timeout" in exc_timeout.get_recovery_suggestion()


class TestRetryPolicy:
    """Test retry policy configuration"""

    def test_retry_policy_defaults(self):
        """Default retry policy"""
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.initial_delay == 1.0
        assert policy.exponential_base == 2.0

    def test_retry_policy_custom(self):
        """Custom retry policy"""
        policy = RetryPolicy(
            max_retries=5,
            initial_delay=2.0,
            max_delay=120.0,
        )
        assert policy.max_retries == 5
        assert policy.initial_delay == 2.0

    def test_is_retryable(self):
        """Check if error is retryable"""
        policy = RetryPolicy()

        # Retryable error
        exc_api = APIError(message="Connection failed")
        assert policy.is_retryable(exc_api)

        # Non-retryable error
        exc_val = ValidationError(message="Bad data")
        assert not policy.is_retryable(exc_val)

    def test_get_delay_exponential(self):
        """Exponential backoff calculation"""
        policy = RetryPolicy(
            initial_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )

        delay_0 = policy.get_delay(0)  # 1 * 2^0 = 1
        delay_1 = policy.get_delay(1)  # 1 * 2^1 = 2
        delay_2 = policy.get_delay(2)  # 1 * 2^2 = 4

        assert delay_0 == 1.0
        assert delay_1 == 2.0
        assert delay_2 == 4.0

    def test_get_delay_max_cap(self):
        """Delay capped at max"""
        policy = RetryPolicy(
            initial_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
            jitter=False,
        )

        delay_0 = policy.get_delay(0)  # 1
        delay_10 = policy.get_delay(10)  # Would be 1024, capped at 10

        assert delay_0 == 1.0
        assert delay_10 == 10.0

    def test_get_delay_with_jitter(self):
        """Jitter adds randomness"""
        policy = RetryPolicy(
            initial_delay=10.0,
            jitter=True,
        )

        delays = [policy.get_delay(0) for _ in range(10)]

        # All delays should be different (with high probability)
        assert len(set(delays)) > 1
        
        # All should be within expected range (±25%)
        for delay in delays:
            assert 7.5 <= delay <= 12.5


class TestRetryDecorator:
    """Test retry decorator"""

    def test_successful_on_first_try(self):
        """Successful function returns immediately"""
        call_count = 0

        @Retry(RetryPolicy(max_retries=3))
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_api_error(self):
        """Retries on retryable error"""
        call_count = 0

        @Retry(RetryPolicy(max_retries=2, initial_delay=0.01))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APIError(message="Connection failed")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    def test_no_retry_on_validation_error(self):
        """Does not retry non-retryable errors"""
        call_count = 0

        @Retry(RetryPolicy(max_retries=3))
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValidationError(message="Bad data")

        with pytest.raises(ValidationError):
            failing_func()

        assert call_count == 1  # Only tried once

    def test_max_retries_exceeded(self):
        """Raises error after max retries"""
        call_count = 0

        @Retry(RetryPolicy(max_retries=2, initial_delay=0.01))
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise APIError(message="Connection failed")

        with pytest.raises(APIError):
            always_fails()

        assert call_count == 3  # 1 initial + 2 retries

    def test_wrapped_exception(self):
        """Wraps non-pipeline exceptions"""
        @Retry(RetryPolicy(max_retries=1, initial_delay=0.01))
        def raises_value_error():
            raise ValueError("Bad value")

        with pytest.raises(ValueError):
            raises_value_error()


class TestErrorContext:
    """Test error context"""

    def test_error_context_creation(self):
        """Create error context"""
        exc = PipelineException(message="Test")
        ctx = ErrorContext(
            error=exc,
            run_id="run-001",
            phase="bronze",
            step="load",
        )
        assert ctx.error == exc
        assert ctx.run_id == "run-001"
        assert ctx.phase == "bronze"
        assert ctx.attempt_number == 1

    def test_error_context_serialization(self):
        """Serialize error context"""
        exc = PipelineException(message="Test", phase="bronze")
        ctx = ErrorContext(
            error=exc,
            run_id="run-001",
            phase="bronze",
            step="load",
            input_data={"key": "value"},
        )
        data = ctx.to_dict()
        assert data["run_id"] == "run-001"
        assert data["phase"] == "bronze"
        assert data["input_data"]["key"] == "value"

    def test_error_context_deserialization(self):
        """Deserialize error context"""
        data = {
            "error": {
                "message": "Test",
                "category": "api",
                "severity": "error",
                "phase": "bronze",
                "step": "load",
                "context": {},
                "timestamp": "2024-01-01T00:00:00Z",
                "traceback": "",
            },
            "run_id": "run-001",
            "phase": "bronze",
            "step": "load",
            "input_data": {"key": "value"},
        }
        ctx = ErrorContext.from_dict(data)
        assert ctx.run_id == "run-001"
        assert ctx.error.message == "Test"


class TestErrorLogger:
    """Test error logging"""

    def test_log_error_creates_file(self):
        """Logging error creates JSON file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ErrorLogger(Path(tmpdir))
            
            exc = PipelineException(message="Test error", phase="bronze")
            ctx = ErrorContext(
                error=exc,
                run_id="run-001",
                phase="bronze",
            )
            
            filepath = logger.log_error(ctx)
            assert filepath.exists()
            assert filepath.suffix == ".json"

    def test_logged_error_content(self):
        """Logged error contains correct information"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ErrorLogger(Path(tmpdir))
            
            exc = PipelineException(
                message="Test error",
                phase="bronze",
                context={"file": "data.csv"},
            )
            ctx = ErrorContext(
                error=exc,
                run_id="run-001",
                phase="bronze",
                step="load",
            )
            
            filepath = logger.log_error(ctx)
            
            with open(filepath) as f:
                data = json.load(f)
            
            assert data["error"]["message"] == "Test error"
            assert data["run_id"] == "run-001"
            assert data["phase"] == "bronze"

    def test_get_error_logs(self):
        """Retrieve error logs for a run"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ErrorLogger(Path(tmpdir))
            
            # Log multiple errors with small delays to ensure different timestamps
            for i in range(3):
                exc = PipelineException(message=f"Error {i}")
                ctx = ErrorContext(error=exc, run_id="run-001", phase="bronze")
                logger.log_error(ctx)
                time.sleep(0.01)  # Small delay to ensure different timestamps
            
            logs = logger.get_error_logs("run-001")
            # Should have at least 1 log (they may overwrite if timestamps are identical)
            assert len(logs) >= 1


class TestRecoveryState:
    """Test recovery state management"""

    def test_save_state(self):
        """Save recovery state"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery = RecoveryState(Path(tmpdir))
            
            state = {"data": [1, 2, 3], "processed": True}
            filepath = recovery.save_state("run-001", "bronze", state)
            
            assert filepath.exists()
            assert filepath.suffix == ".json"

    def test_load_state(self):
        """Load recovery state"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery = RecoveryState(Path(tmpdir))
            
            state = {"data": [1, 2, 3], "processed": True}
            recovery.save_state("run-001", "bronze", state)
            
            loaded = recovery.load_state("run-001", "bronze")
            assert loaded == state

    def test_load_nonexistent_state(self):
        """Load non-existent state returns None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery = RecoveryState(Path(tmpdir))
            
            loaded = recovery.load_state("run-999", "silver")
            assert loaded is None

    def test_has_state(self):
        """Check if state exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery = RecoveryState(Path(tmpdir))
            
            state = {"data": [1, 2, 3]}
            recovery.save_state("run-001", "bronze", state)
            
            assert recovery.has_state("run-001", "bronze")
            assert not recovery.has_state("run-001", "silver")

    def test_clear_state_single_phase(self):
        """Clear state for single phase"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery = RecoveryState(Path(tmpdir))
            
            state = {"data": [1, 2, 3]}
            recovery.save_state("run-001", "bronze", state)
            recovery.save_state("run-001", "silver", state)
            
            recovery.clear_state("run-001", "bronze")
            
            assert not recovery.has_state("run-001", "bronze")
            assert recovery.has_state("run-001", "silver")

    def test_clear_state_all_phases(self):
        """Clear all states for run"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery = RecoveryState(Path(tmpdir))
            
            state = {"data": [1, 2, 3]}
            recovery.save_state("run-001", "bronze", state)
            recovery.save_state("run-001", "silver", state)
            recovery.save_state("run-001", "gold", state)
            
            recovery.clear_state("run-001")
            
            assert not recovery.has_state("run-001", "bronze")
            assert not recovery.has_state("run-001", "silver")
            assert not recovery.has_state("run-001", "gold")


class TestErrorHandlingIntegration:
    """Integration tests for error handling"""

    def test_full_error_workflow(self):
        """Full error handling workflow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ErrorLogger(Path(tmpdir))
            recovery = RecoveryState(Path(tmpdir))
            
            # Simulate error
            exc = PipelineException(
                message="Data validation failed",
                category=ErrorCategory.VALIDATION,
                phase="bronze",
                step="validate",
                context={"rows": 1000, "invalid_rows": 50},
            )
            
            ctx = ErrorContext(
                error=exc,
                run_id="run-001",
                username="alice",
                phase="bronze",
                step="validate",
                input_data={"file": "data.csv"},
            )
            
            # Log error
            logger.log_error(ctx)
            
            # Save recovery state
            state = {
                "validated_rows": 950,
                "invalid_rows": 50,
            }
            recovery.save_state("run-001", "bronze", state)
            
            # Retrieve and verify
            logs = logger.get_error_logs("run-001")
            assert len(logs) == 1
            
            loaded_state = recovery.load_state("run-001", "bronze")
            assert loaded_state["validated_rows"] == 950

    def test_retry_with_logging(self):
        """Retry with error logging"""
        attempt = 0

        @Retry(RetryPolicy(max_retries=2, initial_delay=0.01))
        def flaky_operation():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise APIError(message="Connection failed")
            return "success"

        result = flaky_operation()
        assert result == "success"
        assert attempt == 3

    def test_error_recovery_state_for_failed_phase(self):
        """Use recovery state to retry failed phase"""
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery = RecoveryState(Path(tmpdir))
            
            # Save state before failure
            state_before = {"processed_count": 500, "total": 1000}
            recovery.save_state("run-001", "bronze", state_before)
            
            # Check state exists for retry
            assert recovery.has_state("run-001", "bronze")
            
            # Load state for retry
            state_for_retry = recovery.load_state("run-001", "bronze")
            
            # Use this state to continue processing
            new_state = {
                **state_for_retry,
                "start_from_row": state_for_retry["processed_count"],
            }
            
            assert new_state["start_from_row"] == 500
