<!-- Quick API Reference -->

# IDAMP REST API — Quick Reference

## 🚀 Start API Server

```bash
python app/run_api.py
```

Server: `http://localhost:8000`  
Docs: `http://localhost:8000/docs` ← Try endpoints here!

---

## 📋 API Endpoints Quick Map

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Check if API is running |
| POST | `/api/v1/runs/upload` | Upload file & start run |
| GET | `/api/v1/runs` | List all runs |
| GET | `/api/v1/runs/{run_id}` | Get run status |
| POST | `/api/v1/runs/{run_id}/approve` | Approve STTM at layer |
| GET | `/api/v1/runs/{run_id}/report` | Download final report |
| GET | `/api/v1/runs/{run_id}/artifacts/{type}` | Download artifact |
| POST | `/api/v1/runs/{run_id}/cancel` | Cancel run |
| DELETE | `/api/v1/runs/{run_id}` | Delete run |

---

## 🔥 Most Common Workflows

### Workflow 1: Upload → Track → Download

```bash
# 1️⃣ Upload file and get run_id
curl -X POST http://localhost:8000/api/v1/runs/upload \
  -F "file=@customers.csv" \
  -F "business_intent=Analyze customer value" \
  -F "user_email=me@company.com"

# Response:
# {
#   "run_id": "A1B2C3D4",
#   ...
# }

# 2️⃣ Check status repeatedly (polling)
curl http://localhost:8000/api/v1/runs/A1B2C3D4

# 3️⃣ When complete, download report
curl http://localhost:8000/api/v1/runs/A1B2C3D4/report -o report.html
```

### Workflow 2: Upload → Approve at Each Layer

```bash
# 1️⃣ Start run
RUN_ID="A1B2C3D4"

# 2️⃣ Approve Bronze STTM
curl -X POST http://localhost:8000/api/v1/runs/$RUN_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"layer":"bronze"}'

# 3️⃣ Approve Silver STTM
curl -X POST http://localhost:8000/api/v1/runs/$RUN_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"layer":"silver"}'

# 4️⃣ Approve Gold STTM
curl -X POST http://localhost:8000/api/v1/runs/$RUN_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"layer":"gold"}'
```

### Workflow 3: List and Manage Runs

```bash
# List all completed runs (most recent first)
curl "http://localhost:8000/api/v1/runs?status=completed&limit=20"

# List all running runs
curl "http://localhost:8000/api/v1/runs?status=running"

# Delete a run with its files
curl -X DELETE "http://localhost:8000/api/v1/runs/A1B2C3D4?delete_files=true"
```

---

## 📥 File Upload Examples

### Using cURL

```bash
# Basic upload
curl -X POST http://localhost:8000/api/v1/runs/upload \
  -F "file=@data.csv" \
  -F "business_intent=Analyze trends"

# With user email
curl -X POST http://localhost:8000/api/v1/runs/upload \
  -F "file=@data.xlsx" \
  -F "business_intent=Customer segmentation" \
  -F "user_email=john@company.com"
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/runs/upload",
    files={"file": open("data.csv", "rb")},
    data={
        "business_intent": "Analyze customer behavior",
        "user_email": "analyst@company.com"
    }
)

data = response.json()
run_id = data["run_id"]
print(f"Run started: {run_id}")
```

### Using JavaScript/Fetch

```javascript
const formData = new FormData();
formData.append("file", fileInput.files[0]);
formData.append("business_intent", "Find high-value customers");
formData.append("user_email", "analyst@company.com");

const response = await fetch("http://localhost:8000/api/v1/runs/upload", {
  method: "POST",
  body: formData
});

const data = await response.json();
console.log("Run ID:", data.run_id);
```

---

## ✅ Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Waiting to start |
| `running` | Currently processing |
| `completed` | Finished successfully |
| `failed` | Encountered error |
| `cancelled` | User cancelled |

---

## 🎯 Run Phases

| Phase | Description |
|-------|-------------|
| `upload` | File uploaded |
| `bronze_sttm` | Generating Bronze transformation rules |
| `bronze_load` | Loading data to Bronze layer |
| `silver_sttm` | Generating Silver transformation rules |
| `silver_load` | Loading data to Silver layer |
| `gold_sttm` | Generating Gold transformation rules |
| `gold_load` | Loading data to Gold layer |
| `report` | Generating executive report |

---

## 📥 Download Artifacts

### Report

```bash
curl http://localhost:8000/api/v1/runs/A1B2C3D4/report -o report.html
```

### STTM (Transformation Rules)

```bash
# Bronze STTM
curl http://localhost:8000/api/v1/runs/A1B2C3D4/artifacts/bronze_sttm -o bronze.json

# Silver STTM
curl http://localhost:8000/api/v1/runs/A1B2C3D4/artifacts/silver_sttm -o silver.json

# Gold STTM
curl http://localhost:8000/api/v1/runs/A1B2C3D4/artifacts/gold_sttm -o gold.json
```

### Profile (Data Analysis)

```bash
curl http://localhost:8000/api/v1/runs/A1B2C3D4/artifacts/profile -o profile.json
```

---

## 🔍 Status Check Examples

### Check Progress

```bash
curl http://localhost:8000/api/v1/runs/A1B2C3D4
```

Response shows:
```json
{
  "status": "running",
  "phase": "silver_load",
  "progress_percent": 65,
  "message": "Loading Silver layer..."
}
```

### Poll Until Complete (Python)

```python
import requests
import time

run_id = "A1B2C3D4"
api_url = f"http://localhost:8000/api/v1/runs/{run_id}"

while True:
    status = requests.get(api_url).json()
    print(f"{status['phase']}: {status['progress_percent']}%")
    
    if status["status"] in ["completed", "failed"]:
        break
    
    time.sleep(5)  # Wait 5 seconds before checking again
```

### Poll Until Complete (Bash/cURL)

```bash
#!/bin/bash

RUN_ID="A1B2C3D4"
API="http://localhost:8000/api/v1/runs/$RUN_ID"

while true; do
  STATUS=$(curl -s $API | jq -r '.status')
  PHASE=$(curl -s $API | jq -r '.phase')
  PROGRESS=$(curl -s $API | jq -r '.progress_percent')
  
  echo "[$PHASE] $PROGRESS%"
  
  if [[ "$STATUS" == "completed" ]] || [[ "$STATUS" == "failed" ]]; then
    echo "Run $STATUS"
    break
  fi
  
  sleep 5
done
```

---

## ✏️ Approve STTM

```bash
RUN_ID="A1B2C3D4"

# Approve Bronze
curl -X POST "http://localhost:8000/api/v1/runs/$RUN_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"layer":"bronze"}'

# Approve Silver
curl -X POST "http://localhost:8000/api/v1/runs/$RUN_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"layer":"silver"}'

# Approve Gold
curl -X POST "http://localhost:8000/api/v1/runs/$RUN_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"layer":"gold"}'
```

---

## 🚫 Cancel & Delete

### Cancel an In-Progress Run

```bash
curl -X POST "http://localhost:8000/api/v1/runs/A1B2C3D4/cancel"
```

### Delete a Run (keep files)

```bash
curl -X DELETE "http://localhost:8000/api/v1/runs/A1B2C3D4"
```

### Delete a Run (delete files too)

```bash
curl -X DELETE "http://localhost:8000/api/v1/runs/A1B2C3D4?delete_files=true"
```

---

## 📊 List Runs Examples

### All runs
```bash
curl "http://localhost:8000/api/v1/runs"
```

### Completed runs only
```bash
curl "http://localhost:8000/api/v1/runs?status=completed"
```

### Running runs
```bash
curl "http://localhost:8000/api/v1/runs?status=running"
```

### Failed runs
```bash
curl "http://localhost:8000/api/v1/runs?status=failed"
```

### Get up to 50 runs
```bash
curl "http://localhost:8000/api/v1/runs?limit=50"
```

---

## 🧪 Testing with Swagger UI

Best way to test all endpoints interactively:

1. Start API server: `python app/run_api.py`
2. Open browser: `http://localhost:8000/docs`
3. Try each endpoint with a web form
4. See live responses

---

## ⚠️ Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| Connection refused | API not running | `python app/run_api.py` |
| "File not found" | Artifact not generated yet | Wait for status to complete |
| "Run not found" | Wrong run_id | Check run_id is spelled exactly |
| Unsupported format | CSV/XLSX only | Upload `.csv` or `.xlsx` file |
| No response | Network issue | Check `http://localhost:8000/health` |

---

## 🔗 Integration Example: Python Script

```python
#!/usr/bin/env python3
"""Complete example: Upload → Track → Download"""

import requests
import time
import sys
from pathlib import Path

API = "http://localhost:8000/api/v1"

def main():
    # 1. Upload file
    print("📤 Uploading file...")
    response = requests.post(
        f"{API}/runs/upload",
        files={"file": open("data.csv", "rb")},
        data={"business_intent": "Analyze customer trends"}
    )
    
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.text}")
        sys.exit(1)
    
    data = response.json()
    run_id = data["run_id"]
    print(f"✅ Run started: {run_id}")
    
    # 2. Poll until complete
    print("⏳ Waiting for completion...")
    while True:
        status = requests.get(f"{API}/runs/{run_id}").json()
        print(f"  [{status['phase']}] {status['progress_percent']}%")
        
        if status["status"] in ["completed", "failed"]:
            break
        time.sleep(5)
    
    # 3. Download report
    if status["status"] == "completed":
        print("📥 Downloading report...")
        report = requests.get(f"{API}/runs/{run_id}/report")
        Path("report.html").write_bytes(report.content)
        print("✅ Report saved: report.html")
    else:
        print(f"❌ Run failed: {status['error_message']}")

if __name__ == "__main__":
    main()
```

Save as `example.py` and run:
```bash
python example.py
```

---

## 📖 Full Documentation

For complete endpoint documentation: [API_REFERENCE.md](API_REFERENCE.md)
