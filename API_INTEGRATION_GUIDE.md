<!-- API Integration Guide -->

# IDAMP REST API Integration Guide

This guide shows how to integrate the FastAPI REST endpoints into your existing applications and workflows.

## Table of Contents

1. [Running Both Services](#running-both-services)
2. [Sharing State Between API and UI](#sharing-state-between-api-and-ui)
3. [Integration with Existing Orchestrator](#integration-with-existing-orchestrator)
4. [Background Task Runner](#background-task-runner)
5. [Real-World Integration Examples](#real-world-integration-examples)
6. [Monitoring and Logging](#monitoring-and-logging)

---

## Running Both Services

### Option 1: Run in Separate Terminals

**Terminal 1 - Start API Server:**
```bash
python app/run_api.py
```

**Terminal 2 - Start Streamlit UI:**
```bash
streamlit run app/streamlit_app.py
```

Both services run independently but share state via `APIStateManager`.

### Option 2: Run with Docker Compose

Update your `docker-compose.yml` to include both services:

```yaml
version: "3.8"

services:
  # FastAPI server
  api:
    build: .
    command: python app/run_api.py
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GROQ_API_KEY=${GROQ_API_KEY}
    volumes:
      - ./data:/app/data
      - ./audit_logs:/app/audit_logs

  # Streamlit UI
  streamlit:
    build: .
    command: streamlit run app/streamlit_app.py
    ports:
      - "8501:8501"
    environment:
      - PYTHONUNBUFFERED=1
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GROQ_API_KEY=${GROQ_API_KEY}
    volumes:
      - ./data:/app/data
      - ./audit_logs:/app/audit_logs
    depends_on:
      - api
```

Then run:
```bash
docker-compose up -d api streamlit
```

### Option 3: Run Both in Single Python Process

Create `app/run_both.py`:

```python
#!/usr/bin/env python
"""Run both FastAPI and Streamlit in parallel."""

import subprocess
import sys
import time
from pathlib import Path

def run_both():
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    print("\n" + "="*70)
    print("🚀 Starting IDAMP - Both API and UI")
    print("="*70)
    
    # Start API in background
    print("\n📍 Starting API on http://localhost:8000")
    api_proc = subprocess.Popen(
        [sys.executable, "app/run_api.py"],
        cwd=project_root
    )
    
    # Wait for API to start
    time.sleep(2)
    
    # Start Streamlit
    print("📍 Starting UI on http://localhost:8501")
    streamlit_proc = subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py"],
        cwd=project_root
    )
    
    try:
        # Keep running until Streamlit exits
        streamlit_proc.wait()
    finally:
        api_proc.terminate()

if __name__ == "__main__":
    run_both()
```

Run:
```bash
python app/run_both.py
```

---

## Sharing State Between API and UI

### Architecture

Both systems use the same `APIStateManager`:

```
┌──────────────────────────────────────┐
│    Streamlit UI (Port 8501)          │
│    - Display run progress            │
│    - Show STTM for approval          │
│    - Download reports                │
└──────────────┬───────────────────────┘
               │
               ▼
        ┌──────────────────────────────────────┐
        │   APIStateManager (Shared)           │
        │   - In-memory run registry           │
        │   - Persistent JSON files            │
        │   - Thread-safe access               │
        └──────────────┬───────────────────────┘
               ▲       │
               │       ▼
┌──────────────┴───────────────────────┐
│    FastAPI Server (Port 8000)        │
│    - Upload files                    │
│    - Check status                    │
│    - Download reports                │
└──────────────────────────────────────┘
```

### How State Flows

1. **User uploads via API:**
   - API creates `RunState` in `APIStateManager`
   - Saves to `audit_logs/run_<id>_state.json`
   - Streamlit UI reads same state

2. **Pipeline executes:**
   - Orchestrator updates `APIStateManager`
   - Both API and UI see updates in real-time

3. **User queries via UI or API:**
   - Both access same `APIStateManager`
   - See identical progress/artifacts

### Code Example

```python
from app.api_state import get_state_manager, RunStatus, RunPhase

# Both API and UI use the same singleton
state_manager = get_state_manager()

# Create a run
run = state_manager.create_run(
    run_id="ABC123",
    business_intent="Analyze trends",
    input_file="data.csv",
    input_format="csv",
    file_size_bytes=1024,
    num_records=500,
    uploaded_by="api_user"
)

# Update from orchestrator
state_manager.update_run(
    run_id="ABC123",
    status=RunStatus.RUNNING,
    phase=RunPhase.BRONZE_STTM,
    progress_percent=25
)

# Query from API or UI
run = state_manager.get_run("ABC123")
print(f"Status: {run.status.value}")  # "running"
print(f"Phase: {run.phase.value}")    # "bronze_sttm"
```

---

## Integration with Existing Orchestrator

### Update Orchestrator to Use APIStateManager

In `agents/orchestrator.py`:

```python
from app.api_state import get_state_manager, RunStatus, RunPhase

def run_until_bronze_sttm(
    run_id: str,
    business_intent: str,
    input_file: str
):
    """Run pipeline stages, updating API state."""
    
    state_manager = get_state_manager()
    
    # Start
    state_manager.update_run(
        run_id,
        status=RunStatus.RUNNING,
        phase=RunPhase.UPLOAD,
        started_at=datetime.utcnow().isoformat() + "Z",
        progress_percent=10
    )
    
    try:
        # Run profiler
        state_manager.update_run(
            run_id,
            phase=RunPhase.UPLOAD,
            progress_percent=20,
            message="Analyzing data profile..."
        )
        profile_path = profile_dataset(input_file, run_id)
        state_manager.update_run(
            run_id,
            profile_path=str(profile_path),
            progress_percent=40
        )
        
        # Run Bronze agent
        state_manager.update_run(
            run_id,
            phase=RunPhase.BRONZE_STTM,
            progress_percent=50,
            message="Generating Bronze STTM..."
        )
        bronze_sttm = generate_bronze_sttm(input_file, profile_path)
        state_manager.update_run(
            run_id,
            bronze_sttm_path=str(bronze_sttm),
            progress_percent=80
        )
        
        # Completion
        state_manager.update_run(
            run_id,
            status=RunStatus.COMPLETED,
            progress_percent=100,
            completed_at=datetime.utcnow().isoformat() + "Z"
        )
        
        return bronze_sttm
        
    except Exception as e:
        state_manager.update_run(
            run_id,
            status=RunStatus.FAILED,
            error_message=str(e),
            completed_at=datetime.utcnow().isoformat() + "Z"
        )
        raise
```

---

## Background Task Runner

### Use Celery or APScheduler for Async Execution

Update `app/api.py` to handle file uploads asynchronously:

```python
from fastapi import BackgroundTasks
import threading

def _process_run_async(run_id: str, input_file: str, business_intent: str):
    """Process run in background thread."""
    try:
        from agents.orchestrator import run_until_bronze_sttm
        
        state_manager = get_state_manager()
        state_manager.update_run(
            run_id,
            status=RunStatus.RUNNING
        )
        
        # Execute pipeline
        result = run_until_bronze_sttm(run_id, business_intent, input_file)
        
        state_manager.update_run(
            run_id,
            status=RunStatus.COMPLETED,
            progress_percent=100
        )
    except Exception as e:
        state_manager = get_state_manager()
        state_manager.update_run(
            run_id,
            status=RunStatus.FAILED,
            error_message=str(e)
        )

@app.post("/api/v1/runs/upload")
async def upload_and_start_run(
    file: UploadFile = File(...),
    business_intent: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Upload file and start run in background."""
    
    # ... save file, create run ...
    
    # Start processing in background
    background_tasks.add_task(
        _process_run_async,
        run_id=run_id,
        input_file=file_path,
        business_intent=business_intent
    )
    
    return FileUploadResponse(...)
```

---

## Real-World Integration Examples

### Example 1: Scheduled Data Pipeline

```python
# jobs/scheduled_pipeline.py

import requests
import schedule
import time
from pathlib import Path

class PipelineScheduler:
    def __init__(self, api_base="http://localhost:8000/api/v1"):
        self.api = api_base
    
    def run_daily_analysis(self, csv_path: str, intent: str):
        """Run pipeline every morning at 9 AM."""
        
        # Upload file
        response = requests.post(
            f"{self.api}/runs/upload",
            files={"file": open(csv_path, "rb")},
            data={"business_intent": intent}
        )
        
        run_id = response.json()["run_id"]
        print(f"Started run {run_id}")
        
        # Wait for completion
        self._wait_for_completion(run_id)
        
        # Download report
        report = requests.get(f"{self.api}/runs/{run_id}/report")
        report_path = Path("reports") / f"daily_{run_id}.html"
        report_path.write_bytes(report.content)
        
        # Email report
        self._email_report(report_path)
    
    def _wait_for_completion(self, run_id: str, max_wait=3600):
        """Wait up to 1 hour for run to complete."""
        start = time.time()
        while time.time() - start < max_wait:
            status = requests.get(f"{self.api}/runs/{run_id}").json()
            if status["status"] in ["completed", "failed"]:
                return status
            time.sleep(10)
        raise TimeoutError(f"Run {run_id} did not complete within {max_wait}s")
    
    def _email_report(self, report_path: Path):
        """Email report to stakeholders."""
        import smtplib
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        # ... email logic ...

# Schedule execution
scheduler = PipelineScheduler()
schedule.every().day.at("09:00").do(
    scheduler.run_daily_analysis,
    csv_path="data/daily_extract.csv",
    intent="Analyze daily KPIs"
)

# Run scheduler
while True:
    schedule.run_pending()
    time.sleep(60)
```

### Example 2: Enterprise Data Portal

```python
# web_app/models.py - Django/Flask integration

class DataPipeline(models.Model):
    """Track pipeline runs in enterprise database."""
    run_id = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    business_intent = models.TextField()
    status = models.CharField(max_length=20)
    progress = models.IntegerField(default=0)
    report_path = models.CharField(max_length=500, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# web_app/views.py

def upload_dataset(request):
    """Django view to upload dataset via API."""
    
    if request.method == "POST":
        file = request.FILES["file"]
        intent = request.POST["business_intent"]
        
        # Call IDAMP API
        response = requests.post(
            "http://localhost:8000/api/v1/runs/upload",
            files={"file": file},
            data={"business_intent": intent}
        )
        
        data = response.json()
        run_id = data["run_id"]
        
        # Save to database
        pipeline = DataPipeline.objects.create(
            run_id=run_id,
            user=request.user,
            file_name=file.name,
            business_intent=intent,
            status="pending"
        )
        
        # Start background task to poll status
        poll_run_status.delay(run_id, pipeline.id)
        
        return redirect("pipeline_detail", run_id=run_id)

# Celery task to poll status
from celery import shared_task

@shared_task
def poll_run_status(run_id: str, pipeline_id: int):
    """Poll API for run status every 10 seconds."""
    
    pipeline = DataPipeline.objects.get(id=pipeline_id)
    
    while True:
        status = requests.get(
            f"http://localhost:8000/api/v1/runs/{run_id}"
        ).json()
        
        pipeline.status = status["status"]
        pipeline.progress = status["progress_percent"]
        pipeline.save()
        
        if status["status"] in ["completed", "failed"]:
            break
        
        time.sleep(10)
```

### Example 3: Webhook Integration

```python
# integrations/webhooks.py

import requests
from datetime import datetime

class WebhookNotifier:
    """Send notifications when runs complete."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def notify_completion(self, run_id: str):
        """Send webhook when run completes."""
        
        # Get final status
        status = requests.get(
            f"http://localhost:8000/api/v1/runs/{run_id}"
        ).json()
        
        # Download report
        report = requests.get(
            f"http://localhost:8000/api/v1/runs/{run_id}/report"
        )
        
        # Send webhook
        payload = {
            "event": "run_completed",
            "run_id": run_id,
            "status": status["status"],
            "timestamp": datetime.utcnow().isoformat(),
            "report_url": f"http://localhost:8000/api/v1/runs/{run_id}/report"
        }
        
        requests.post(self.webhook_url, json=payload)

# Usage in orchestrator
def run_and_notify(run_id: str, webhook_url: str):
    # ... execute pipeline ...
    notifier = WebhookNotifier(webhook_url)
    notifier.notify_completion(run_id)
```

---

## Monitoring and Logging

### Add Logging to API

Update `app/api.py`:

```python
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/api.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("idamp_api")

@app.post("/api/v1/runs/upload")
async def upload_and_start_run(...):
    logger.info(f"Upload request: {file.filename} for {business_intent}")
    
    try:
        # ... upload logic ...
        logger.info(f"Run created: {run_id}")
        return FileUploadResponse(...)
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise
```

### Metrics Collection

```python
# app/api_metrics.py

from prometheus_client import Counter, Histogram, generate_latest
import time

# Define metrics
runs_created = Counter("idamp_runs_created_total", "Total runs created")
runs_completed = Counter("idamp_runs_completed_total", "Total runs completed")
run_duration = Histogram("idamp_run_duration_seconds", "Run duration in seconds")
upload_size = Histogram("idamp_upload_size_bytes", "Upload file size")

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()

# Use in endpoints
@app.post("/api/v1/runs/upload")
async def upload_and_start_run(...):
    start = time.time()
    upload_size.observe(file_size)
    runs_created.inc()
    
    # ... logic ...
    
    run_duration.observe(time.time() - start)
    return response
```

---

## Testing

### Test API Endpoints

Create `tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.api import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200

def test_upload_file(tmp_path):
    # Create test file
    test_file = tmp_path / "test.csv"
    test_file.write_text("a,b\n1,2\n")
    
    # Upload
    with open(test_file) as f:
        response = client.post(
            "/api/v1/runs/upload",
            files={"file": f},
            data={
                "business_intent": "Test",
                "user_email": "test@test.com"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data

def test_list_runs():
    response = client.get("/api/v1/runs?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data
```

Run tests:
```bash
pytest tests/test_api.py -v
```

---

## Performance Tips

1. **Use connection pooling** for requests:
   ```python
   from requests.adapters import HTTPAdapter
   from urllib3.util.retry import Retry
   
   session = requests.Session()
   retry = Retry(total=3, backoff_factor=0.5)
   adapter = HTTPAdapter(max_retries=retry)
   session.mount("http://", adapter)
   ```

2. **Batch status checks**:
   ```python
   # Poll less frequently as run progresses
   if progress < 50:
       wait_time = 5   # Check every 5 seconds
   else:
       wait_time = 30  # Check every 30 seconds
   ```

3. **Use async for multiple runs**:
   ```python
   import asyncio
   import aiohttp
   
   async def check_all_runs(run_ids):
       async with aiohttp.ClientSession() as session:
           tasks = [
               session.get(f"http://localhost:8000/api/v1/runs/{rid}")
               for rid in run_ids
           ]
           return await asyncio.gather(*tasks)
   ```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| API and UI show different status | State not synced | Restart both services |
| File not found after upload | File path wrong | Check `audit_logs/run_*_state.json` |
| Runs not persisting | State files deleted | Check `audit_logs/` directory exists |
| Performance slow | Too many runs in memory | Use `?limit=` parameter, clean old runs |

---

## Next Steps

1. Start API: `python app/run_api.py`
2. Start UI: `streamlit run app/streamlit_app.py`
3. Try endpoints: `http://localhost:8000/docs`
4. Read [API_REFERENCE.md](API_REFERENCE.md) for full details
5. Use examples above for your integration
