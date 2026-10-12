# Integration Guide: Performance Monitoring in Pipeline

This guide shows how to integrate performance monitoring into your existing pipeline agents.

---

## Architecture Overview

```
                    orchestrator.py
                          ↓
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
   Bronze Agent      Silver Agent      Gold Agent
   (+ monitoring)    (+ monitoring)    (+ monitoring)
        ↓                 ↓                 ↓
   MetricsCollector  MetricsCollector  MetricsCollector
        ↓                 ↓                 ↓
   metrics/metrics_run-001.json (aggregated)
        ↓
   Streamlit App
        ↓
   PerformanceUI Dashboard
```

---

## Step 1: Add MetricsCollector to Orchestrator

**File: `orchestrator.py`**

```python
from core.performance_monitoring import MetricsCollector
from pathlib import Path

def run_until_bronze_sttm(user_intent, run_id):
    """Run pipeline up to Bronze STTM generation."""
    
    # Initialize metrics collection
    collector = MetricsCollector(run_id, metrics_dir=Path("metrics"))
    
    try:
        # Pass to agents
        landing_data = landing_agent.execute(
            user_intent=user_intent,
            run_id=run_id,
            collector=collector,  # ← Add this
        )
        
        profile_data = profiler_agent.execute(
            landing_data=landing_data,
            run_id=run_id,
            collector=collector,  # ← Add this
        )
        
        sttm_data = sttm_agent.execute(
            landing_data=landing_data,
            profile_data=profile_data,
            run_id=run_id,
            collector=collector,  # ← Add this
        )
        
        return sttm_data
    
    finally:
        # Save metrics
        collector.finalize()
        collector.save_to_json()
        
        # Log summary
        summary = collector.get_summary()
        print(f"✅ Phase completed in {summary['total_duration_seconds']:.1f}s")
        print(f"   API calls: {summary['total_api_calls']}")
```

---

## Step 2: Add Monitoring to Bronze Agent

**File: `agents/bronze_agent.py`**

```python
from core.performance_monitoring import TimingContext, track_time

class BronzeAgent:
    
    def execute(self, user_intent, run_id, collector):
        """Execute Bronze phase with monitoring."""
        
        # Phase-level timing
        with TimingContext(collector, "bronze", "phase", "execute"):
            
            # Load data
            with TimingContext(collector, "bronze", "landing", "load_data"):
                data = self._load_data(user_intent)
            
            # Validate
            with TimingContext(collector, "bronze", "landing", "validate"):
                self._validate_data(data)
            
            # Store
            with TimingContext(collector, "bronze", "landing", "store"):
                self._store_data(data)
        
        return data
    
    @track_time(collector, agent="bronze", phase="profile")
    def profile_data(self, data):
        """Profile with decorator."""
        return data.describe()
```

---

## Step 3: Add LLM Monitoring

**File: `agents/bronze_agent.py` or `agents/sttm_generator.py`**

```python
from core.performance_monitoring import MetricsCollector
import time

def call_llm_with_monitoring(collector, prompt, model, provider):
    """Helper to call LLM and track metrics."""
    
    start = time.time()
    
    try:
        # Call LLM
        response = llm_instance.invoke(prompt)
        latency = time.time() - start
        
        # Record metrics
        input_tokens = len(prompt.split())
        output_tokens = len(response.split())
        
        collector.record_api_call(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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


# In STTM generator
class STTMGenerator:
    
    def generate_sttm(self, data, collector):
        """Generate STTM with monitoring."""
        
        with TimingContext(collector, "sttm_gen", "generation", "invoke_llm"):
            sttm = call_llm_with_monitoring(
                collector=collector,
                prompt=self._make_prompt(data),
                model="gemini-2.5-flash",
                provider="google",
            )
        
        return sttm
```

---

## Step 4: Add Memory Sampling

**File: `agents/base_agent.py`**

```python
class BaseAgent:
    """Base class for all agents with monitoring."""
    
    def execute_phase(self, data, phase_name, collector):
        """Execute with automatic memory sampling."""
        
        with TimingContext(collector, self.name, phase_name, "execute"):
            
            # Do work
            result = self.process(data)
            
            # Sample memory after operation
            collector.record_memory_sample(self.name, phase_name)
        
        return result
```

---

## Step 5: Display in Streamlit App

**File: `app/streamlit_app.py`**

```python
import streamlit as st
from core.performance_ui import PerformanceUI
from core.performance_monitoring import MetricsCollector
import json
from pathlib import Path

# Initialize
PerformanceUI.initialize_session()

st.title("🏅 Agentic Medallion Pipeline")

tabs = st.tabs(["Pipeline", "Performance", "Logs"])

with tabs[0]:
    st.markdown("### 🚀 Run Pipeline")
    user_intent = st.text_area("Business question:")
    
    if st.button("Start Pipeline"):
        run_id = st.session_state.get("run_id", "run-001")
        
        with st.spinner("Running pipeline..."):
            try:
                # Import and run
                from orchestrator import run_until_bronze_sttm
                
                result = run_until_bronze_sttm(user_intent, run_id)
                st.success("✅ Pipeline completed!")
                
                # Load and display metrics
                metrics_file = Path("metrics") / f"metrics_{run_id}.json"
                if metrics_file.exists():
                    with open(metrics_file) as f:
                        metrics_data = json.load(f)
                    
                    # Store for display
                    PerformanceUI.set_current_metrics(metrics_data)
            
            except Exception as e:
                st.error(f"❌ Error: {e}")

with tabs[1]:
    st.markdown("### 📊 Performance Report")
    
    # Load latest metrics
    metrics_dir = Path("metrics")
    if metrics_dir.exists():
        latest_metric = max(metrics_dir.glob("*.json"), default=None)
        
        if latest_metric:
            with open(latest_metric) as f:
                metrics_data = json.load(f)
            
            # Create PerformanceMetrics from dict
            from core.performance_monitoring import (
                PerformanceMetrics,
                TimingMetric,
                MemoryMetric,
                APICallMetric,
            )
            
            metrics = PerformanceMetrics(
                run_id=metrics_data["run_id"],
                start_time=metrics_data["start_time"],
                end_time=metrics_data["end_time"],
                duration_seconds=metrics_data["duration_seconds"],
                timings=[TimingMetric(**t) for t in metrics_data["timings"]],
                memory_samples=[MemoryMetric(**m) for m in metrics_data["memory_samples"]],
                api_calls=[APICallMetric(**a) for a in metrics_data["api_calls"]],
            )
            
            PerformanceUI.render_full_performance_report(metrics)
        else:
            st.info("Run pipeline to see performance metrics")
    else:
        st.info("No metrics available yet")

with tabs[2]:
    st.markdown("### 📋 Logs & Export")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 View Metrics JSON"):
            if latest_metric:
                with open(latest_metric) as f:
                    data = json.load(f)
                st.json(data)
    
    with col2:
        if st.button("📥 Download Metrics"):
            if latest_metric:
                with open(latest_metric) as f:
                    content = f.read()
                st.download_button(
                    label="Download",
                    data=content,
                    file_name=latest_metric.name,
                    mime="application/json",
                )
    
    with col3:
        if st.button("🔄 Compare Runs"):
            metrics_files = list(Path("metrics").glob("*.json"))
            if len(metrics_files) >= 2:
                st.info(f"Found {len(metrics_files)} runs")
                # Compare logic here
```

---

## Step 6: Monitoring Checklist

### Bronze Agent
- [ ] Import MetricsCollector
- [ ] Add `collector` parameter to execute()
- [ ] Wrap operations with TimingContext
- [ ] Call collector.record_api_call() for LLM calls
- [ ] Call collector.record_memory_sample() after operations

### Silver Agent
- [ ] Add monitoring same as Bronze
- [ ] Track transformation operations
- [ ] Record API calls for any LLM-based transformations

### Gold Agent
- [ ] Add monitoring same as Bronze
- [ ] Track aggregation operations
- [ ] Record API calls

### Reporter Agent
- [ ] Track chart generation time
- [ ] Track SQL execution time
- [ ] Record any API calls

### Orchestrator
- [ ] Create MetricsCollector(run_id)
- [ ] Pass to all agents
- [ ] Call collector.finalize() and save_to_json() at end
- [ ] Log summary statistics

### Streamlit App
- [ ] Initialize PerformanceUI session
- [ ] Add Performance tab
- [ ] Load and display metrics after pipeline run
- [ ] Show comparison view for multiple runs

---

## Common Patterns

### Pattern 1: Full Phase Monitoring

```python
def run_phase(collector, phase_name):
    with TimingContext(collector, "agent", phase_name, "execute"):
        # All operations for phase
        pass
    
    # Memory sample after phase
    collector.record_memory_sample("agent", phase_name)
```

### Pattern 2: Optional Monitoring

```python
def execute(data, collector=None):
    if collector:
        with TimingContext(collector, "agent", "phase", "op"):
            result = process(data)
    else:
        result = process(data)
    
    return result
```

### Pattern 3: Nested Operations

```python
with TimingContext(collector, agent, phase, "phase"):
    with TimingContext(collector, agent, phase, "step1"):
        do_step1()
    
    with TimingContext(collector, agent, phase, "step2"):
        do_step2()
    
    # Total phase time = sum of steps
```

---

## Testing Monitoring Code

```python
def test_agent_with_monitoring():
    """Test agent with metrics collection."""
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create collector
        collector = MetricsCollector(
            "test-run",
            metrics_dir=Path(tmpdir),
        )
        
        # Run agent
        agent = BronzeAgent()
        result = agent.execute(
            user_intent="Test",
            run_id="test-run",
            collector=collector,
        )
        
        # Verify metrics
        assert len(collector.metrics.timings) > 0
        assert len(collector.metrics.memory_samples) > 0
        
        # Save and verify file
        filepath = collector.save_to_json()
        assert filepath.exists()
```

---

## Environment Setup

Add to `requirements.txt`:

```
psutil>=5.9.0          # Memory monitoring
plotly>=5.0.0          # Charts
pandas>=1.3.0          # Data handling
streamlit>=1.25.0      # UI
```

Install:
```bash
pip install psutil plotly pandas
```

---

## Performance Baselines

Track these metrics to optimize over time:

| Phase | Baseline | Target | Goal |
|-------|----------|--------|------|
| Bronze Landing | 10s | 8s | Optimize I/O |
| Profiling | 15s | 12s | Batch processing |
| STTM Gen | 30s | 20s | Reduce LLM calls |
| Silver Transform | 20s | 15s | Vectorize ops |
| Gold Aggregation | 10s | 8s | Index tables |
| **Total** | **85s** | **65s** | **50s** |

---

## Next Steps

1. **Integrate monitoring** into each agent (2-3 hours)
2. **Deploy to staging** (1 hour)
3. **Run baseline metrics** for each phase (2-3 hours)
4. **Analyze bottlenecks** (2 hours)
5. **Optimize** identified slow operations (varies)
6. **Monitor** improvements over time (ongoing)

---

## Support

- **Questions?** See [PERFORMANCE_MONITORING_GUIDE.md](PERFORMANCE_MONITORING_GUIDE.md)
- **API lookup?** See [PERFORMANCE_MONITORING_QUICK_REFERENCE.md](PERFORMANCE_MONITORING_QUICK_REFERENCE.md)
- **Tests?** Run `pytest tests/test_performance_monitoring.py -v`

---

**Status**: ✅ Ready to integrate into pipeline
