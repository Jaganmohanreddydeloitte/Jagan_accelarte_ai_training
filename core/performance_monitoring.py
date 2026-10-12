"""
Performance monitoring for pipeline agents.

Tracks execution time, memory usage, API calls, and LLM costs.
"""

import time
import json
import psutil
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from functools import wraps
from threading import Lock


# Cost estimates per 1M input tokens (as of 2024)
LLM_COSTS = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},  # per 1M tokens
    "llama-3.3-70b-versatile": {"input": 0.27, "output": 0.81},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1-mini": {"input": 0.15, "output": 0.60},
}

# API call cost (flat rate)
API_CALL_COSTS = {
    "google": 0.0001,
    "openai": 0.0001,
    "groq": 0.0001,
    "github": 0.0001,
}


@dataclass
class TimingMetric:
    """Records timing for a single operation."""
    agent: str
    phase: str
    operation: str
    start_time: str  # UTC ISO format
    end_time: str
    duration_seconds: float
    status: str  # "success", "failed", "skipped"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryMetric:
    """Records memory usage during operation."""
    agent: str
    phase: str
    timestamp: str  # UTC ISO format
    process_memory_mb: float
    peak_memory_mb: float
    available_system_mb: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class APICallMetric:
    """Records an API call."""
    provider: str  # "google", "openai", "groq", "github"
    timestamp: str  # UTC ISO format
    model: str
    input_tokens: int
    output_tokens: int
    status_code: Optional[int] = None
    latency_seconds: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics for a run."""
    run_id: str
    start_time: str  # UTC ISO format
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    timings: List[TimingMetric] = field(default_factory=list)
    memory_samples: List[MemoryMetric] = field(default_factory=list)
    api_calls: List[APICallMetric] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "timings": [t.to_dict() for t in self.timings],
            "memory_samples": [m.to_dict() for m in self.memory_samples],
            "api_calls": [a.to_dict() for a in self.api_calls],
        }


class MetricsCollector:
    """Collects performance metrics during pipeline execution."""
    
    def __init__(self, run_id: str, metrics_dir: Optional[Path] = None):
        """
        Initialize metrics collector.
        
        Args:
            run_id: Unique identifier for this run
            metrics_dir: Directory to save metrics (default: metrics/)
        """
        self.run_id = run_id
        self.metrics_dir = metrics_dir or Path("metrics")
        self.metrics_dir.mkdir(exist_ok=True)
        
        self.metrics = PerformanceMetrics(
            run_id=run_id,
            start_time=datetime.now(timezone.utc).isoformat(),
        )
        
        self._lock = Lock()
        self._process = psutil.Process()
        self._peak_memory_mb = 0.0
    
    def record_timing(
        self,
        agent: str,
        phase: str,
        operation: str,
        duration_seconds: float,
        status: str = "success",
    ) -> None:
        """Record execution time for an operation."""
        with self._lock:
            metric = TimingMetric(
                agent=agent,
                phase=phase,
                operation=operation,
                start_time=datetime.now(timezone.utc).isoformat(),
                end_time=datetime.now(timezone.utc).isoformat(),
                duration_seconds=duration_seconds,
                status=status,
            )
            self.metrics.timings.append(metric)
    
    def record_memory_sample(self, agent: str, phase: str) -> None:
        """Record current memory usage."""
        try:
            process_memory = self._process.memory_info().rss / (1024 * 1024)  # MB
            self._peak_memory_mb = max(self._peak_memory_mb, process_memory)
            
            available_memory = psutil.virtual_memory().available / (1024 * 1024)  # MB
            
            with self._lock:
                metric = MemoryMetric(
                    agent=agent,
                    phase=phase,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    process_memory_mb=round(process_memory, 2),
                    peak_memory_mb=round(self._peak_memory_mb, 2),
                    available_system_mb=round(available_memory, 2),
                )
                self.metrics.memory_samples.append(metric)
        except Exception as e:
            pass  # Silently fail if memory monitoring not available
    
    def record_api_call(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        status_code: Optional[int] = None,
        latency_seconds: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record an LLM API call."""
        with self._lock:
            metric = APICallMetric(
                provider=provider,
                timestamp=datetime.now(timezone.utc).isoformat(),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                status_code=status_code,
                latency_seconds=latency_seconds,
                error=error,
            )
            self.metrics.api_calls.append(metric)
    
    def finalize(self) -> None:
        """Mark run as complete."""
        self.metrics.end_time = datetime.now(timezone.utc).isoformat()
        
        if self.metrics.start_time and self.metrics.end_time:
            start = datetime.fromisoformat(self.metrics.start_time)
            end = datetime.fromisoformat(self.metrics.end_time)
            self.metrics.duration_seconds = (end - start).total_seconds()
    
    def save_to_json(self) -> Path:
        """Save metrics to JSON file."""
        self.finalize()
        
        filepath = self.metrics_dir / f"metrics_{self.run_id}.json"
        with open(filepath, "w") as f:
            json.dump(self.metrics.to_dict(), f, indent=2)
        
        return filepath
    
    def get_metrics(self) -> PerformanceMetrics:
        """Get current metrics snapshot."""
        return self.metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        self.finalize()
        
        total_api_calls = len(self.metrics.api_calls)
        total_input_tokens = sum(c.input_tokens for c in self.metrics.api_calls)
        total_output_tokens = sum(c.output_tokens for c in self.metrics.api_calls)
        
        peak_memory = (
            max((m.peak_memory_mb for m in self.metrics.memory_samples), default=0)
            if self.metrics.memory_samples
            else 0
        )
        
        agent_times = {}
        for timing in self.metrics.timings:
            if timing.agent not in agent_times:
                agent_times[timing.agent] = 0
            agent_times[timing.agent] += timing.duration_seconds
        
        return {
            "run_id": self.run_id,
            "total_duration_seconds": self.metrics.duration_seconds or 0,
            "total_api_calls": total_api_calls,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "peak_memory_mb": round(peak_memory, 2),
            "agents": agent_times,
        }


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(
        self,
        collector: MetricsCollector,
        agent: str,
        phase: str,
        operation: str,
    ):
        self.collector = collector
        self.agent = agent
        self.phase = phase
        self.operation = operation
        self.start_time = None
        self.status = "success"
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is not None:
            self.status = "failed"
        
        self.collector.record_timing(
            agent=self.agent,
            phase=self.phase,
            operation=self.operation,
            duration_seconds=duration,
            status=self.status,
        )
        self.collector.record_memory_sample(self.agent, self.phase)
    
    def mark_skipped(self):
        """Mark operation as skipped."""
        self.status = "skipped"


def track_time(collector: MetricsCollector, agent: str, phase: str):
    """
    Decorator to automatically track operation timing.
    
    Usage:
        @track_time(collector, "bronze_agent", "landing")
        def process_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation = func.__name__
            with TimingContext(collector, agent, phase, operation):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class CostEstimator:
    """Estimates costs for LLM usage."""
    
    @staticmethod
    def estimate_llm_cost(
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Estimate cost for LLM API call.
        
        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        
        Returns:
            Estimated cost in USD (or 0 if model not found)
        """
        if model not in LLM_COSTS:
            return 0.0
        
        costs = LLM_COSTS[model]
        
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        
        return round(input_cost + output_cost, 6)
    
    @staticmethod
    def estimate_api_call_cost(provider: str) -> float:
        """Estimate cost for API call."""
        return API_CALL_COSTS.get(provider, 0.0)
    
    @staticmethod
    def estimate_total_cost(api_calls: List[APICallMetric]) -> float:
        """Estimate total cost for all API calls in a run."""
        total = 0.0
        
        for call in api_calls:
            if call.error:
                continue  # Don't charge for failed calls
            
            # LLM cost
            if call.provider in ["openai", "google", "groq", "github"]:
                model_cost = CostEstimator.estimate_llm_cost(
                    call.model,
                    call.input_tokens,
                    call.output_tokens,
                )
                total += model_cost
            
            # API call cost
            api_cost = CostEstimator.estimate_api_call_cost(call.provider)
            total += api_cost
        
        return round(total, 6)


class PerformanceAnalyzer:
    """Analyzes performance metrics."""
    
    @staticmethod
    def get_agent_breakdown(metrics: PerformanceMetrics) -> Dict[str, Dict[str, Any]]:
        """Get breakdown by agent."""
        breakdown = {}
        
        for timing in metrics.timings:
            if timing.agent not in breakdown:
                breakdown[timing.agent] = {
                    "total_time": 0,
                    "operations": 0,
                    "phases": {},
                }
            
            breakdown[timing.agent]["total_time"] += timing.duration_seconds
            breakdown[timing.agent]["operations"] += 1
            
            phase = timing.phase
            if phase not in breakdown[timing.agent]["phases"]:
                breakdown[timing.agent]["phases"][phase] = 0
            breakdown[timing.agent]["phases"][phase] += timing.duration_seconds
        
        return breakdown
    
    @staticmethod
    def get_slowest_operations(
        metrics: PerformanceMetrics,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get slowest operations."""
        operations = [
            {
                "agent": t.agent,
                "phase": t.phase,
                "operation": t.operation,
                "duration_seconds": t.duration_seconds,
                "status": t.status,
            }
            for t in metrics.timings
        ]
        
        return sorted(
            operations,
            key=lambda x: x["duration_seconds"],
            reverse=True,
        )[:limit]
    
    @staticmethod
    def get_api_call_summary(api_calls: List[APICallMetric]) -> Dict[str, Any]:
        """Summarize API calls."""
        by_provider = {}
        by_model = {}
        
        for call in api_calls:
            if call.error:
                continue
            
            # By provider
            if call.provider not in by_provider:
                by_provider[call.provider] = {
                    "count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            
            by_provider[call.provider]["count"] += 1
            by_provider[call.provider]["input_tokens"] += call.input_tokens
            by_provider[call.provider]["output_tokens"] += call.output_tokens
            
            # By model
            if call.model not in by_model:
                by_model[call.model] = {
                    "count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            
            by_model[call.model]["count"] += 1
            by_model[call.model]["input_tokens"] += call.input_tokens
            by_model[call.model]["output_tokens"] += call.output_tokens
        
        return {
            "by_provider": by_provider,
            "by_model": by_model,
            "total_calls": len(api_calls),
            "failed_calls": sum(1 for c in api_calls if c.error),
        }
    
    @staticmethod
    def estimate_cost_breakdown(
        api_calls: List[APICallMetric],
    ) -> Dict[str, float]:
        """Estimate costs by provider."""
        costs = {}
        
        for call in api_calls:
            if call.error:
                continue
            
            if call.provider not in costs:
                costs[call.provider] = 0.0
            
            llm_cost = CostEstimator.estimate_llm_cost(
                call.model,
                call.input_tokens,
                call.output_tokens,
            )
            api_cost = CostEstimator.estimate_api_call_cost(call.provider)
            
            costs[call.provider] += llm_cost + api_cost
        
        return {k: round(v, 6) for k, v in costs.items()}
