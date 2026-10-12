"""
Tests for performance monitoring module.
"""

import pytest
import time
import json
from pathlib import Path
from datetime import datetime, timezone

from core.performance_monitoring import (
    MetricsCollector,
    TimingMetric,
    MemoryMetric,
    APICallMetric,
    PerformanceMetrics,
    TimingContext,
    CostEstimator,
    PerformanceAnalyzer,
    track_time,
)


class TestTimingMetric:
    """Tests for TimingMetric dataclass."""
    
    def test_create_timing_metric(self):
        """Create a timing metric."""
        metric = TimingMetric(
            agent="bronze_agent",
            phase="landing",
            operation="load_data",
            start_time="2024-01-01T10:00:00+00:00",
            end_time="2024-01-01T10:00:05+00:00",
            duration_seconds=5.0,
            status="success",
        )
        
        assert metric.agent == "bronze_agent"
        assert metric.duration_seconds == 5.0
        assert metric.status == "success"
    
    def test_timing_metric_to_dict(self):
        """Convert timing metric to dict."""
        metric = TimingMetric(
            agent="agent",
            phase="phase",
            operation="op",
            start_time="2024-01-01T10:00:00+00:00",
            end_time="2024-01-01T10:00:05+00:00",
            duration_seconds=5.0,
            status="success",
        )
        
        data = metric.to_dict()
        assert data["agent"] == "agent"
        assert data["duration_seconds"] == 5.0


class TestMemoryMetric:
    """Tests for MemoryMetric dataclass."""
    
    def test_create_memory_metric(self):
        """Create a memory metric."""
        metric = MemoryMetric(
            agent="bronze_agent",
            phase="landing",
            timestamp="2024-01-01T10:00:00+00:00",
            process_memory_mb=128.5,
            peak_memory_mb=256.0,
            available_system_mb=4096.0,
        )
        
        assert metric.agent == "bronze_agent"
        assert metric.process_memory_mb == 128.5
        assert metric.peak_memory_mb == 256.0


class TestAPICallMetric:
    """Tests for APICallMetric dataclass."""
    
    def test_create_api_call_metric(self):
        """Create an API call metric."""
        metric = APICallMetric(
            provider="google",
            timestamp="2024-01-01T10:00:00+00:00",
            model="gemini-2.5-flash",
            input_tokens=100,
            output_tokens=50,
            status_code=200,
            latency_seconds=0.5,
        )
        
        assert metric.provider == "google"
        assert metric.input_tokens == 100
        assert metric.output_tokens == 50
    
    def test_api_call_metric_with_error(self):
        """Create API call with error."""
        metric = APICallMetric(
            provider="openai",
            timestamp="2024-01-01T10:00:00+00:00",
            model="gpt-4o-mini",
            input_tokens=0,
            output_tokens=0,
            status_code=429,
            error="Rate limit exceeded",
        )
        
        assert metric.error == "Rate limit exceeded"


class TestMetricsCollector:
    """Tests for MetricsCollector class."""
    
    def test_initialize_collector(self, tmp_path):
        """Initialize metrics collector."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        assert collector.run_id == "run-001"
        assert collector.metrics_dir == tmp_path
        assert tmp_path.exists()
    
    def test_record_timing(self, tmp_path):
        """Record operation timing."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_timing(
            agent="bronze",
            phase="landing",
            operation="load",
            duration_seconds=2.5,
            status="success",
        )
        
        assert len(collector.metrics.timings) == 1
        assert collector.metrics.timings[0].agent == "bronze"
        assert collector.metrics.timings[0].duration_seconds == 2.5
    
    def test_record_multiple_timings(self, tmp_path):
        """Record multiple timings."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        for i in range(5):
            collector.record_timing(
                agent=f"agent_{i}",
                phase="phase",
                operation="op",
                duration_seconds=float(i),
            )
        
        assert len(collector.metrics.timings) == 5
    
    def test_record_memory_sample(self, tmp_path):
        """Record memory usage."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_memory_sample("agent", "phase")
        
        assert len(collector.metrics.memory_samples) >= 1
        metric = collector.metrics.memory_samples[0]
        assert metric.process_memory_mb > 0
        assert metric.peak_memory_mb > 0
    
    def test_record_api_call(self, tmp_path):
        """Record API call."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_api_call(
            provider="google",
            model="gemini-2.5-flash",
            input_tokens=100,
            output_tokens=50,
            status_code=200,
            latency_seconds=1.2,
        )
        
        assert len(collector.metrics.api_calls) == 1
        assert collector.metrics.api_calls[0].provider == "google"
    
    def test_record_failed_api_call(self, tmp_path):
        """Record failed API call."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_api_call(
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=0,
            output_tokens=0,
            status_code=429,
            error="Rate limit",
        )
        
        assert collector.metrics.api_calls[0].error == "Rate limit"
    
    def test_save_to_json(self, tmp_path):
        """Save metrics to JSON file."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_timing("agent", "phase", "op", 1.0)
        filepath = collector.save_to_json()
        
        assert filepath.exists()
        
        with open(filepath) as f:
            data = json.load(f)
        
        assert data["run_id"] == "run-001"
        assert len(data["timings"]) == 1
    
    def test_get_summary(self, tmp_path):
        """Get metrics summary."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_timing("bronze", "phase", "op", 2.0)
        collector.record_timing("silver", "phase", "op", 3.0)
        collector.record_api_call("google", "gemini", 100, 50)
        collector.record_memory_sample("agent", "phase")
        
        summary = collector.get_summary()
        
        assert summary["run_id"] == "run-001"
        assert summary["total_api_calls"] == 1
        assert summary["total_input_tokens"] == 100
        assert "bronze" in summary["agents"]
        assert summary["agents"]["bronze"] == 2.0


class TestTimingContext:
    """Tests for TimingContext manager."""
    
    def test_timing_context_success(self, tmp_path):
        """Timing context for successful operation."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        with TimingContext(
            collector,
            agent="agent",
            phase="phase",
            operation="op",
        ):
            time.sleep(0.1)
        
        assert len(collector.metrics.timings) == 1
        assert collector.metrics.timings[0].status == "success"
        assert collector.metrics.timings[0].duration_seconds >= 0.1
    
    def test_timing_context_failure(self, tmp_path):
        """Timing context for failed operation."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        try:
            with TimingContext(collector, "agent", "phase", "op"):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        assert collector.metrics.timings[0].status == "failed"
    
    def test_timing_context_skipped(self, tmp_path):
        """Mark operation as skipped."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        with TimingContext(collector, "agent", "phase", "op") as ctx:
            ctx.mark_skipped()
        
        assert collector.metrics.timings[0].status == "skipped"


class TestTrackTimeDecorator:
    """Tests for track_time decorator."""
    
    def test_track_time_decorator(self, tmp_path):
        """Decorate function with timing."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        @track_time(collector, "agent", "phase")
        def do_work():
            time.sleep(0.05)
            return "done"
        
        result = do_work()
        
        assert result == "done"
        assert len(collector.metrics.timings) == 1
    
    def test_track_time_with_args(self, tmp_path):
        """Decorator preserves function args."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        @track_time(collector, "agent", "phase")
        def add(a, b):
            return a + b
        
        result = add(2, 3)
        
        assert result == 5


class TestCostEstimator:
    """Tests for cost estimation."""
    
    def test_estimate_gemini_cost(self):
        """Estimate cost for Gemini API."""
        cost = CostEstimator.estimate_llm_cost(
            model="gemini-2.5-flash",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        
        # 0.075 + 0.30 = 0.375
        assert abs(cost - 0.375) < 0.001
    
    def test_estimate_openai_cost(self):
        """Estimate cost for OpenAI API."""
        cost = CostEstimator.estimate_llm_cost(
            model="gpt-4o-mini",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        
        # 0.15 + 0.60 = 0.75
        assert abs(cost - 0.75) < 0.001
    
    def test_estimate_groq_cost(self):
        """Estimate cost for Groq API."""
        cost = CostEstimator.estimate_llm_cost(
            model="llama-3.3-70b-versatile",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        
        # 0.27 + 0.81 = 1.08
        assert abs(cost - 1.08) < 0.001
    
    def test_unknown_model_returns_zero(self):
        """Unknown model returns 0 cost."""
        cost = CostEstimator.estimate_llm_cost(
            model="unknown-model",
            input_tokens=1000,
            output_tokens=500,
        )
        
        assert cost == 0.0
    
    def test_api_call_cost(self):
        """Estimate API call cost."""
        cost = CostEstimator.estimate_api_call_cost("google")
        
        assert cost == 0.0001
    
    def test_total_cost_estimation(self):
        """Estimate total cost for multiple calls."""
        api_calls = [
            APICallMetric(
                provider="google",
                timestamp="2024-01-01T10:00:00+00:00",
                model="gemini-2.5-flash",
                input_tokens=1000,
                output_tokens=500,
            ),
            APICallMetric(
                provider="openai",
                timestamp="2024-01-01T10:01:00+00:00",
                model="gpt-4o-mini",
                input_tokens=1000,
                output_tokens=500,
            ),
        ]
        
        total = CostEstimator.estimate_total_cost(api_calls)
        
        # Both costs should be small but non-zero
        assert total > 0
    
    def test_failed_call_not_charged(self):
        """Failed API calls not charged."""
        api_calls = [
            APICallMetric(
                provider="google",
                timestamp="2024-01-01T10:00:00+00:00",
                model="gemini-2.5-flash",
                input_tokens=1000,
                output_tokens=500,
                error="Failed",
            ),
        ]
        
        total = CostEstimator.estimate_total_cost(api_calls)
        
        # Failed calls are skipped entirely (no charge)
        assert total == 0.0


class TestPerformanceAnalyzer:
    """Tests for performance analysis."""
    
    def test_agent_breakdown(self, tmp_path):
        """Get agent performance breakdown."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_timing("agent1", "phase", "op1", 2.0)
        collector.record_timing("agent1", "phase", "op2", 3.0)
        collector.record_timing("agent2", "phase", "op1", 1.0)
        
        analyzer = PerformanceAnalyzer()
        breakdown = analyzer.get_agent_breakdown(collector.metrics)
        
        assert len(breakdown) == 2
        assert breakdown["agent1"]["total_time"] == 5.0
        assert breakdown["agent1"]["operations"] == 2
        assert breakdown["agent2"]["total_time"] == 1.0
    
    def test_slowest_operations(self, tmp_path):
        """Get slowest operations."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        for i in range(10):
            collector.record_timing("agent", "phase", f"op_{i}", float(i + 1))
        
        analyzer = PerformanceAnalyzer()
        slowest = analyzer.get_slowest_operations(collector.metrics, limit=3)
        
        assert len(slowest) == 3
        assert slowest[0]["duration_seconds"] == 10.0
        assert slowest[1]["duration_seconds"] == 9.0
    
    def test_api_call_summary(self, tmp_path):
        """Get API call summary."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_api_call("google", "gemini", 100, 50)
        collector.record_api_call("google", "gemini", 150, 75)
        collector.record_api_call("openai", "gpt-4o-mini", 200, 100)
        
        analyzer = PerformanceAnalyzer()
        summary = analyzer.get_api_call_summary(collector.metrics.api_calls)
        
        assert summary["total_calls"] == 3
        assert summary["by_provider"]["google"]["count"] == 2
        assert summary["by_provider"]["google"]["input_tokens"] == 250
    
    def test_cost_breakdown(self, tmp_path):
        """Get cost breakdown by provider."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        collector.record_api_call("google", "gemini-2.5-flash", 1000, 500)
        collector.record_api_call("openai", "gpt-4o-mini", 1000, 500)
        
        analyzer = PerformanceAnalyzer()
        costs = analyzer.estimate_cost_breakdown(collector.metrics.api_calls)
        
        assert "google" in costs
        assert "openai" in costs
        assert costs["google"] > 0
        assert costs["openai"] > 0


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""
    
    def test_create_performance_metrics(self):
        """Create performance metrics."""
        metrics = PerformanceMetrics(
            run_id="run-001",
            start_time="2024-01-01T10:00:00+00:00",
        )
        
        assert metrics.run_id == "run-001"
        assert len(metrics.timings) == 0
    
    def test_metrics_to_dict(self):
        """Convert metrics to dict."""
        metrics = PerformanceMetrics(
            run_id="run-001",
            start_time="2024-01-01T10:00:00+00:00",
            end_time="2024-01-01T10:00:10+00:00",
            duration_seconds=10,
        )
        
        data = metrics.to_dict()
        
        assert data["run_id"] == "run-001"
        assert data["duration_seconds"] == 10
        assert isinstance(data["timings"], list)


class TestIntegration:
    """Integration tests."""
    
    def test_full_monitoring_workflow(self, tmp_path):
        """Full workflow: collect, analyze, export."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        # Simulate operations
        for agent in ["bronze", "silver", "gold"]:
            for i in range(3):
                with TimingContext(collector, agent, f"phase_{i}", f"op_{i}"):
                    time.sleep(0.01)
                collector.record_memory_sample(agent, f"phase_{i}")
                collector.record_api_call(
                    "google",
                    "gemini-2.5-flash",
                    100 + i,
                    50 + i,
                )
        
        # Get metrics
        metrics = collector.get_metrics()
        summary = collector.get_summary()
        
        assert summary["total_api_calls"] == 9
        assert len(metrics.timings) == 9
        
        # Save and reload
        filepath = collector.save_to_json()
        assert filepath.exists()
        
        with open(filepath) as f:
            data = json.load(f)
        
        assert data["run_id"] == "run-001"
        assert len(data["timings"]) == 9
    
    def test_monitoring_with_decorator(self, tmp_path):
        """Monitoring with decorator."""
        collector = MetricsCollector("run-001", metrics_dir=tmp_path)
        
        @track_time(collector, "test", "phase")
        def slow_function():
            time.sleep(0.05)
            return "result"
        
        result = slow_function()
        
        assert result == "result"
        assert len(collector.metrics.timings) == 1
        assert collector.metrics.timings[0].duration_seconds >= 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
