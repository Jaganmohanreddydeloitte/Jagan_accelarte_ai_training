"""
Pipeline Error Handling & Retry System

Provides:
- Custom exception classes for different error types
- Automatic retry logic with exponential backoff
- Detailed error messages with context
- Error logging with full stack traces
- Recovery state management
"""

import logging
import traceback
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional, List, Dict
from datetime import datetime, timezone
from pathlib import Path
import json
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "info"           # Informational, can ignore
    WARNING = "warning"     # Warning, but can continue
    ERROR = "error"         # Error, operation failed
    CRITICAL = "critical"   # Critical, pipeline stops


class ErrorCategory(Enum):
    """Error categories for better routing/handling"""
    VALIDATION = "validation"           # Input validation failed
    DATA_QUALITY = "data_quality"       # Quality check failed
    TRANSFORMATION = "transformation"   # Data transformation failed
    IO = "io"                           # File I/O error
    DATABASE = "database"               # Database error
    API = "api"                         # External API error
    AUTHENTICATION = "authentication"   # Auth/permission error
    RESOURCE = "resource"               # Resource exhausted
    TIMEOUT = "timeout"                 # Operation timed out
    UNKNOWN = "unknown"                 # Unknown error


class PipelineException(Exception):
    """Base exception for all pipeline errors"""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.phase = phase
        self.step = step
        self.context = context or {}
        self.cause = cause
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.traceback = traceback.format_exc()

        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for logging"""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "phase": self.phase,
            "step": self.step,
            "context": self.context,
            "timestamp": self.timestamp,
            "traceback": self.traceback,
        }

    def get_user_message(self) -> str:
        """Get user-friendly error message"""
        location = ""
        if self.phase:
            location = f"in {self.phase}"
            if self.step:
                location += f" > {self.step}"
            location += ": "

        return f"❌ {location}{self.message}"

    def get_recovery_suggestion(self) -> Optional[str]:
        """Get suggestion for error recovery"""
        suggestions = {
            ErrorCategory.VALIDATION: "Check your input data format and try again",
            ErrorCategory.DATA_QUALITY: "Review the quality report and fix data issues",
            ErrorCategory.TRANSFORMATION: "Review transformation rules and verify input data",
            ErrorCategory.IO: "Check file paths and permissions",
            ErrorCategory.DATABASE: "Check database connection and try again later",
            ErrorCategory.API: "Check API credentials and rate limits, try again",
            ErrorCategory.AUTHENTICATION: "Check your credentials and permissions",
            ErrorCategory.RESOURCE: "Free up resources or reduce data size",
            ErrorCategory.TIMEOUT: "Try again or increase timeout duration",
        }
        return suggestions.get(self.category)


class ValidationError(PipelineException):
    """Raised when input validation fails"""

    def __init__(
        self,
        message: str,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            phase=phase,
            step=step,
            context=context,
            cause=cause,
        )


class DataQualityError(PipelineException):
    """Raised when data quality check fails"""

    def __init__(
        self,
        message: str,
        quality_score: Optional[float] = None,
        min_score: Optional[float] = None,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        ctx = context or {}
        if quality_score is not None:
            ctx["quality_score"] = quality_score
        if min_score is not None:
            ctx["min_score"] = min_score

        super().__init__(
            message=message,
            category=ErrorCategory.DATA_QUALITY,
            severity=ErrorSeverity.ERROR,
            phase=phase,
            step=step,
            context=ctx,
            cause=cause,
        )


class TransformationError(PipelineException):
    """Raised when data transformation fails"""

    def __init__(
        self,
        message: str,
        transform_name: Optional[str] = None,
        row_index: Optional[int] = None,
        column: Optional[str] = None,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        ctx = context or {}
        if transform_name:
            ctx["transform"] = transform_name
        if row_index is not None:
            ctx["row"] = row_index
        if column:
            ctx["column"] = column

        super().__init__(
            message=message,
            category=ErrorCategory.TRANSFORMATION,
            severity=ErrorSeverity.ERROR,
            phase=phase,
            step=step,
            context=ctx,
            cause=cause,
        )


class IOError(PipelineException):
    """Raised when file I/O operations fail"""

    def __init__(
        self,
        message: str,
        filepath: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        ctx = context or {}
        if filepath:
            ctx["filepath"] = str(filepath)
        if operation:
            ctx["operation"] = operation

        super().__init__(
            message=message,
            category=ErrorCategory.IO,
            severity=ErrorSeverity.ERROR,
            phase=phase,
            step=step,
            context=ctx,
            cause=cause,
        )


class DatabaseError(PipelineException):
    """Raised when database operations fail"""

    def __init__(
        self,
        message: str,
        table: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        ctx = context or {}
        if table:
            ctx["table"] = table
        if operation:
            ctx["operation"] = operation

        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.ERROR,
            phase=phase,
            step=step,
            context=ctx,
            cause=cause,
        )


class APIError(PipelineException):
    """Raised when external API calls fail"""

    def __init__(
        self,
        message: str,
        api_name: Optional[str] = None,
        status_code: Optional[int] = None,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        ctx = context or {}
        if api_name:
            ctx["api"] = api_name
        if status_code:
            ctx["status_code"] = status_code

        super().__init__(
            message=message,
            category=ErrorCategory.API,
            severity=ErrorSeverity.ERROR,
            phase=phase,
            step=step,
            context=ctx,
            cause=cause,
        )


class TimeoutError(PipelineException):
    """Raised when operation times out"""

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[int] = None,
        phase: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        ctx = context or {}
        if timeout_seconds:
            ctx["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.ERROR,
            phase=phase,
            step=step,
            context=ctx,
            cause=cause,
        )


@dataclass
class RetryPolicy:
    """Configuration for retry logic"""
    max_retries: int = 3                    # Maximum number of retries
    initial_delay: float = 1.0              # Initial delay in seconds
    max_delay: float = 60.0                 # Maximum delay in seconds
    exponential_base: float = 2.0           # Exponential backoff base
    jitter: bool = True                     # Add random jitter to delay
    retryable_categories: List[ErrorCategory] = field(
        default_factory=lambda: [
            ErrorCategory.API,
            ErrorCategory.DATABASE,
            ErrorCategory.TIMEOUT,
            ErrorCategory.RESOURCE,
        ]
    )

    def is_retryable(self, error: PipelineException) -> bool:
        """Check if error should be retried"""
        return error.category in self.retryable_categories

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt (exponential backoff)"""
        import random
        
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            # Add random jitter (±25%)
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(delay, 0)


class Retry:
    """Retry decorator for functions"""

    def __init__(self, policy: RetryPolicy = None):
        self.policy = policy or RetryPolicy()

    def __call__(self, func: Callable) -> Callable:
        """Decorator for retryable functions"""
        def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(self.policy.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except PipelineException as e:
                    last_error = e
                    
                    if not self.policy.is_retryable(e):
                        raise  # Don't retry non-retryable errors
                    
                    if attempt < self.policy.max_retries:
                        delay = self.policy.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed, retrying in {delay:.1f}s: {e.message}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"All {self.policy.max_retries + 1} attempts failed")
                
                except Exception as e:
                    # Wrap non-pipeline exceptions
                    pipeline_error = PipelineException(
                        message=str(e),
                        cause=e,
                    )
                    
                    if not self.policy.is_retryable(pipeline_error):
                        raise e
                    
                    if attempt < self.policy.max_retries:
                        delay = self.policy.get_delay(attempt)
                        logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.1f}s")
                        time.sleep(delay)
                    else:
                        raise e
            
            raise last_error if last_error else Exception("Unknown error")
        
        return wrapper


@dataclass
class ErrorContext:
    """Context information about an error"""
    error: PipelineException
    run_id: str
    username: Optional[str] = None
    phase: Optional[str] = None
    step: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    attempt_number: int = 1
    max_attempts: int = 3
    can_retry: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "error": self.error.to_dict(),
            "run_id": self.run_id,
            "username": self.username,
            "phase": self.phase,
            "step": self.step,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "attempt_number": self.attempt_number,
            "max_attempts": self.max_attempts,
            "can_retry": self.can_retry,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorContext":
        """Deserialize from dict"""
        # Reconstruct error
        error_data = data.pop("error")
        error = PipelineException(
            message=error_data["message"],
            category=ErrorCategory(error_data["category"]),
            severity=ErrorSeverity(error_data["severity"]),
            phase=error_data.get("phase"),
            step=error_data.get("step"),
            context=error_data.get("context"),
        )
        
        return cls(error=error, **data)


class ErrorLogger:
    """Log errors with full context"""

    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path("error_logs")
        self.log_dir.mkdir(exist_ok=True)

    def log_error(self, error_context: ErrorContext) -> Path:
        """Log error to file and return filepath"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        # Create filename
        filename = f"error_{error_context.run_id}_{timestamp}.json"
        filepath = self.log_dir / filename

        # Write to file
        with open(filepath, "w") as f:
            json.dump(error_context.to_dict(), f, indent=2, default=str)

        logger.error(
            f"Error logged: {error_context.error.message}",
            extra={
                "run_id": error_context.run_id,
                "phase": error_context.phase,
                "filepath": str(filepath),
            }
        )

        return filepath

    def log_retry(
        self,
        error_context: ErrorContext,
        attempt: int,
        delay: float,
    ) -> None:
        """Log a retry attempt"""
        logger.warning(
            f"Retry attempt {attempt}/{error_context.max_attempts} after {delay:.1f}s: {error_context.error.message}",
            extra={
                "run_id": error_context.run_id,
                "phase": error_context.phase,
                "attempt": attempt,
            }
        )

    def log_recovery(self, error_context: ErrorContext, recovery_action: str) -> None:
        """Log recovery action"""
        logger.info(
            f"Recovery action: {recovery_action}",
            extra={
                "run_id": error_context.run_id,
                "phase": error_context.phase,
            }
        )

    def get_error_logs(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all error logs for a run"""
        logs = []
        
        for filepath in self.log_dir.glob(f"error_{run_id}_*.json"):
            with open(filepath) as f:
                logs.append(json.load(f))
        
        return sorted(logs, key=lambda x: x["created_at"], reverse=True)


class RecoveryState:
    """Manages recovery state for failed operations"""

    def __init__(self, state_dir: Path = None):
        self.state_dir = state_dir or Path("recovery_state")
        self.state_dir.mkdir(exist_ok=True)

    def save_state(
        self,
        run_id: str,
        phase: str,
        state: Dict[str, Any],
    ) -> Path:
        """Save recovery state to file"""
        filepath = self.state_dir / f"{run_id}_{phase}_state.json"
        
        with open(filepath, "w") as f:
            json.dump(
                {
                    "run_id": run_id,
                    "phase": phase,
                    "state": state,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
                default=str,
            )
        
        logger.info(f"Recovery state saved: {filepath}")
        return filepath

    def load_state(self, run_id: str, phase: str) -> Optional[Dict[str, Any]]:
        """Load recovery state from file"""
        filepath = self.state_dir / f"{run_id}_{phase}_state.json"
        
        if not filepath.exists():
            return None
        
        try:
            with open(filepath) as f:
                data = json.load(f)
                logger.info(f"Recovery state loaded: {filepath}")
                return data.get("state")
        except Exception as e:
            logger.error(f"Error loading recovery state: {e}")
            return None

    def clear_state(self, run_id: str, phase: Optional[str] = None) -> None:
        """Clear recovery state"""
        if phase:
            filepath = self.state_dir / f"{run_id}_{phase}_state.json"
            if filepath.exists():
                filepath.unlink()
        else:
            # Clear all states for run
            for filepath in self.state_dir.glob(f"{run_id}_*_state.json"):
                filepath.unlink()
        
        logger.info(f"Recovery state cleared for {run_id}")

    def has_state(self, run_id: str, phase: str) -> bool:
        """Check if recovery state exists"""
        filepath = self.state_dir / f"{run_id}_{phase}_state.json"
        return filepath.exists()
