# Performance Monitoring Guide

Complete guide to tracking execution time, memory usage, API calls, and costs in your pipeline.

---

## Overview

The performance monitoring system tracks:
- **Execution Time**: How long each agent and operation takes
- **Memory Usage**: Process memory and peak memory consumption
- **API Calls**: Count and details of LLM API calls
- **Cost Estimation**: Accurate pricing for all LLM providers

All metrics are collected during pipeline execution and can be viewed in Streamlit, exported for analysis, or compared across runs.

---

## Architecture

```
Pipeline Execution
        ↓
MetricsCollector (tracks everything)
        ↓
    ├─ TimingContext (⏱️ operation duration)
    ├─ Memory sampling (💾 process memory)
    └─ API call recording (📞 LLM calls)
        ↓
PerformanceMetrics (aggregated data)
        ↓
    ├─ Save to JSON (metrics_{run_id}.json)
    ├─ PerformanceAnalyzer (breakdown & analysis)
    └─ CostEstimator (pricing calculations)
        ↓
PerformanceUI (Streamlit display)
    ├─ Summary metrics
    ├─ Timeline visualization
    ├─ Agent breakdown
    ├─ Memory usage chart
    └─ Cost analysis
```

---

## Quick Start

### 1. Initialize Metrics Collection

```python
from core.performance_monitoring import MetricsCollector

# Create collector for this run
collector = MetricsCollector(run_id="run-001")
```

### 2. Track Operation Timing

#### Using Context Manager

```python
from core.performance_monitoring import TimingContext

with TimingContext(collector, agent="bronze", phase="landing", operation="load_data"):
    # Your operation here
    data = load_csv_file()
```

#### Using Decorator

```python
from core.performance_monitoring import track_time

@track_time(collector, agent="bronze", phase="landing")
def load_data():
    return pd.read_csv("data.csv")
```

### 3. Record Memory Samples

```python
# Automatically called in TimingContext, or manually:
collector.record_memory_sample(agent="bronze", phase="landing")
```

### 4. Record API Calls

```python
# When calling an LLM
response = llm.invoke(prompt)

collector.record_api_call(
    provider="google",
    model="gemini-2.5-flash",
    input_tokens=len(prompt.split()),
    output_tokens=len(response.split()),
    status_code=200,
    latency_seconds=1.2,
)
```

### 5. Display Metrics in Streamlit

```python
import streamlit as st
from core.performance_ui import PerformanceUI

PerformanceUI.initialize_session()

# ... after pipeline execution ...

metrics = collector.get_metrics()
PerformanceUI.render_full_performance_report(metrics)
```

### 6. Export Metrics

```python
# Save to JSON file
filepath = collector.save_to_json()

# Get summary
summary = collector.get_summary()
print(f"Total duration: {summary['total_duration_seconds']:.1f}s")
print(f"API calls: {summary['total_api_calls']}")
print(f"Estimated cost: ${sum(summary['agents'].values()):.4f}")
```

---

## Usage Patterns

### Pattern 1: Monitor Agent Execution

```python
def execute_bronze_phase(input_data):
    collector = MetricsCollector(run_id="run-001")
    
    with TimingContext(collector, "bronze", "landing", "validate"):
        validate_input(input_data)
    
    with TimingContext(collector, "bronze", "landing", "load"):
        data = load_data(input_data)
    
    with TimingContext(collector, "bronze", "landing", "profile"):
        profile = profile_data(data)
    
    collector.save_to_json()
    return data
```

### Pattern 2: Monitor LLM API Calls

```python
import time

def call_llm_with_monitoring(collector, prompt, model, provider):
    start = time.time()
    
    try:
        response = llm.invoke(prompt)
        latency = time.time() - start
        
        collector.record_api_call(
            provider=provider,
            model=model,
            input_tokens=len(prompt.split()),
            output_tokens=len(response.split()),
            status_code=200,
            latency_seconds=latency,
        )
        
        return response
    
    except Exception as e:
        latency = time.time() - start
        
        collector.record_api_call(
            provider=provider,
            model=model,
            input_tokens=len(prompt.split()),
            output_tokens=0,
            status_code=500,
            latency_seconds=latency,
            error=str(e),
        )
        
        raise
```

### Pattern 3: Analysis & Comparison

```python
from core.performance_monitoring import PerformanceAnalyzer
import json

# Load metrics from multiple runs
runs = []
for i in range(1, 4):
    with open(f"metrics/metrics_run-{i:03d}.json") as f:
        data = json.load(f)
    runs.append(data)

# Analyze performance trends
analyzer = PerformanceAnalyzer()

for run in runs:
    breakdown = analyzer.get_agent_breakdown(run)
    print(f"Run {run['run_id']}: {breakdown}")
```

### Pattern 4: Cost Estimation

```python
from core.performance_monitoring import CostEstimator

# Estimate single call cost
cost = CostEstimator.estimate_llm_cost(
    model="gpt-4o-mini",
    input_tokens=1000,
    output_tokens=500,
)
print(f"Estimated cost: ${cost:.4f}")

# Estimate total cost for run
total_cost = CostEstimator.estimate_total_cost(metrics.api_calls)
print(f"Total estimated cost: ${total_cost:.4f}")

# Cost breakdown by provider
breakdown = analyzer.estimate_cost_breakdown(metrics.api_calls)
for provider, cost in breakdown.items():
    print(f"{provider}: ${cost:.4f}")
```

---

## Core Classes

### MetricsCollector

Main class for collecting metrics.

```python
collector = MetricsCollector(run_id, metrics_dir=Path("metrics"))

# Record operations
collector.record_timing(agent, phase, operation, duration_seconds, status="success")
collector.record_memory_sample(agent, phase)
collector.record_api_call(provider, model, input_tokens, output_tokens, ...)

# Get data
metrics = collector.get_metrics()           # Get PerformanceMetrics
summary = collector.get_summary()           # Get dict summary

# Export
filepath = collector.save_to_json()         # Save to metrics/{run_id}.json
collector.finalize()                        # Mark run as complete
```

### TimingContext

Context manager for automatic timing.

```python
with TimingContext(collector, agent, phase, operation) as ctx:
    # Your code here
    ...

# Mark as skipped if operation was not run
ctx.mark_skipped()
```

If exception occurs, status is automatically "failed".

### CostEstimator

Estimates costs for LLM usage.

```python
# Single call cost
cost = CostEstimator.estimate_llm_cost(model, input_tokens, output_tokens)

# API call cost
cost = CostEstimator.estimate_api_call_cost(provider)

# Total cost for run
total = CostEstimator.estimate_total_cost(api_calls_list)
```

Cost data (per 1M tokens):
- **Gemini**: Input $0.075, Output $0.30
- **Groq**: Input $0.27, Output $0.81
- **OpenAI**: Input $0.15, Output $0.60
- **GitHub**: Input $0.15, Output $0.60

### PerformanceAnalyzer

Analyzes collected metrics.

```python
analyzer = PerformanceAnalyzer()

# Agent breakdown
breakdown = analyzer.get_agent_breakdown(metrics)
# → {"agent_name": {"total_time": 10.5, "operations": 3, "phases": {...}}}

# Slowest operations
slowest = analyzer.get_slowest_operations(metrics, limit=10)
# → [{"agent": "...", "operation": "...", "duration_seconds": 5.0, ...}]

# API call summary
summary = analyzer.get_api_call_summary(api_calls)
# → {"by_provider": {...}, "by_model": {...}, "total_calls": 5, "failed_calls": 0}

# Cost breakdown
costs = analyzer.estimate_cost_breakdown(api_calls)
# → {"google": 0.0050, "openai": 0.0075, ...}
```

### PerformanceUI

Streamlit components for displaying metrics.

```python
from core.performance_ui import PerformanceUI

PerformanceUI.initialize_session()

# Display full report
PerformanceUI.render_full_performance_report(metrics)

# Or individual components
PerformanceUI.render_summary_metrics(metrics)
PerformanceUI.render_execution_timeline(metrics)
PerformanceUI.render_agent_breakdown(metrics)
PerformanceUI.render_memory_usage(metrics)
PerformanceUI.render_api_calls_summary(metrics)

# Compare runs
runs = [metrics1, metrics2, metrics3]
PerformanceUI.render_metrics_comparison(runs)
```

---

## Data Structures

### TimingMetric

```python
@dataclass
class TimingMetric:
    agent: str
    phase: str
    operation: str
    start_time: str                 # UTC ISO format
    end_time: str
    duration_seconds: float
    status: str                     # "success", "failed", "skipped"
```

### MemoryMetric

```python
@dataclass
class MemoryMetric:
    agent: str
    phase: str
    timestamp: str                  # UTC ISO format
    process_memory_mb: float
    peak_memory_mb: float
    available_system_mb: float
```

### APICallMetric

```python
@dataclass
class APICallMetric:
    provider: str                   # "google", "openai", "groq", "github"
    timestamp: str                  # UTC ISO format
    model: str
    input_tokens: int
    output_tokens: int
    status_code: Optional[int] = None
    latency_seconds: Optional[float] = None
    error: Optional[str] = None
```

### PerformanceMetrics

```python
@dataclass
class PerformanceMetrics:
    run_id: str
    start_time: str                 # UTC ISO format
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    timings: List[TimingMetric] = field(default_factory=list)
    memory_samples: List[MemoryMetric] = field(default_factory=list)
    api_calls: List[APICallMetric] = field(default_factory=list)
```

---

## Export Format

### JSON Export

```json
{
  "run_id": "run-001",
  "start_time": "2024-10-07T18:06:45.877000+00:00",
  "end_time": "2024-10-07T18:07:02.342000+00:00",
  "duration_seconds": 16.465,
  "timings": [
    {
      "agent": "bronze",
      "phase": "landing",
      "operation": "load_data",
      "start_time": "2024-10-07T18:06:46.000000+00:00",
      "end_time": "2024-10-07T18:06:48.500000+00:00",
      "duration_seconds": 2.5,
      "status": "success"
    }
  ],
  "memory_samples": [
    {
      "agent": "bronze",
      "phase": "landing",
      "timestamp": "2024-10-07T18:06:48.500000+00:00",
      "process_memory_mb": 128.5,
      "peak_memory_mb": 256.0,
      "available_system_mb": 4096.0
    }
  ],
  "api_calls": [
    {
      "provider": "google",
      "timestamp": "2024-10-07T18:07:00.000000+00:00",
      "model": "gemini-2.5-flash",
      "input_tokens": 1000,
      "output_tokens": 500,
      "status_code": 200,
      "latency_seconds": 1.2,
      "error": null
    }
  ]
}
```

---

## Streamlit Integration

### Basic Integration

```python
import streamlit as st
from core.performance_monitoring import MetricsCollector
from core.performance_ui import PerformanceUI

# Initialize
PerformanceUI.initialize_session()
collector = MetricsCollector(st.session_state.run_id)

# Run pipeline
try:
    with st.spinner("Running pipeline..."):
        metrics = run_pipeline(collector)
    
    # Display results
    st.success("✅ Pipeline completed!")
    PerformanceUI.render_full_performance_report(metrics)

except Exception as e:
    st.error(f"❌ Pipeline failed: {e}")
```

### Performance Monitoring Tab

```python
import streamlit as st
from core.performance_ui import PerformanceUI

tabs = st.tabs(["Pipeline", "Performance", "Logs"])

with tabs[0]:
    # Pipeline UI
    ...

with tabs[1]:
    # Performance report
    metrics = PerformanceUI.get_current_metrics()
    if metrics:
        PerformanceUI.render_full_performance_report(metrics)
    else:
        st.info("Run pipeline to see performance metrics")

with tabs[2]:
    # Logs
    ...
```

---

## Configuration

### Environment Variables

```bash
# Metrics directory (default: metrics/)
export METRICS_DIR=./metrics

# Enable memory sampling (default: true)
export ENABLE_MEMORY_SAMPLING=true

# Enable cost tracking (default: true)
export ENABLE_COST_TRACKING=true
```

### Customize LLM Pricing

```python
from core.performance_monitoring import LLM_COSTS

# Update pricing
LLM_COSTS["custom-model"] = {
    "input": 0.10,      # per 1M tokens
    "output": 0.50,
}

collector.record_api_call(
    provider="custom",
    model="custom-model",
    input_tokens=1000,
    output_tokens=500,
)
```

---

## Best Practices

1. **Initialize early** — Create MetricsCollector before pipeline starts
2. **Record API calls immediately** — Don't wait for processing to complete
3. **Sample memory regularly** — Call record_memory_sample() at phase boundaries
4. **Finalize before export** — Call collector.finalize() to calculate duration
5. **Store run_id with metrics** — Makes it easy to match logs and metrics
6. **Archive old metrics** — Keep metrics/ directory manageable with cleanup
7. **Compare across runs** — Track performance improvements over time
8. **Monitor costs** — Review estimated costs to optimize LLM usage

---

## Troubleshooting

### Memory Sampling Fails

**Problem**: `record_memory_sample()` silently fails or returns zero values.

**Solution**: Check if psutil is installed:
```bash
pip install psutil
```

### Cost Estimates Seem Wrong

**Problem**: Estimated costs don't match actual API bills.

**Solution**: 
- Verify model names match LLM_COSTS dictionary
- Check if custom models need pricing configuration
- Some LLMs charge per-request instead of per-token

### Missing Timing Data

**Problem**: Some operations show 0 duration or are missing.

**Solution**:
- Ensure TimingContext is used for all timed operations
- Check that status is set correctly ("success", "failed", "skipped")
- Verify operation names are descriptive

### Large JSON Files

**Problem**: Metrics JSON files become very large after many runs.

**Solution**:
- Archive old metrics periodically
- Use PerformanceAnalyzer to extract summaries
- Consider time-based data retention

---

## Testing

Run tests with:
```bash
pytest tests/test_performance_monitoring.py -v
```

33 tests covering:
- Metric creation and serialization
- Timing and memory tracking
- API call recording
- Cost estimation
- Analysis and aggregation
- Streamlit UI components

---

## See Also

- [PERFORMANCE_MONITORING_QUICK_REFERENCE.md](PERFORMANCE_MONITORING_QUICK_REFERENCE.md) — API reference
- [core/performance_monitoring.py](core/performance_monitoring.py) — Core code
- [core/performance_ui.py](core/performance_ui.py) — Streamlit UI
- [tests/test_performance_monitoring.py](tests/test_performance_monitoring.py) — Tests

---

## Summary

The performance monitoring system provides:
✅ Automatic timing of all operations
✅ Memory usage tracking with peak detection
✅ Accurate cost estimation for LLM calls
✅ Detailed analysis and breakdowns
✅ Beautiful Streamlit visualizations
✅ JSON export for further analysis
✅ Multi-run comparison capabilities

**Status**: ✅ 33 tests passing (100%) — Production ready
