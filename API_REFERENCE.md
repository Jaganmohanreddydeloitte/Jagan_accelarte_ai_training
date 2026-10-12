<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc to refresh. -->
**Table of Contents**

- [IDAMP REST API Reference](#idamp-rest-api-reference)
  - [Quick Start](#quick-start)
  - [API Architecture](#api-architecture)
  - [Authentication](#authentication)
  - [Base URL](#base-url)
  - [Endpoints](#endpoints)
    - [Health Check](#health-check)
    - [Upload File & Start Run](#upload-file--start-run)
    - [List Runs](#list-runs)
    - [Get Run Status](#get-run-status)
    - [Approve STTM](#approve-sttm)
    - [Download Report](#download-report)
    - [Download Artifact](#download-artifact)
    - [Cancel Run](#cancel-run)
    - [Delete Run](#delete-run)
    - [API Info](#api-info)
  - [Status Codes](#status-codes)
  - [Error Handling](#error-handling)
  - [Complete Examples](#complete-examples)
    - [Python Example](#python-example)
    - [JavaScript/Node.js Example](#javascriptnodejs-example)
    - [cURL Examples](#curl-examples)

<!-- markdown-toc end -->

# IDAMP REST API Reference

The IDAMP REST API provides programmatic access to the Agentic Medallion Pipeline, allowing external applications to:
- Start pipeline runs with CSV/XLSX files
- Track run progress in real-time
- Approve transformation rules at each layer
- Download reports and artifacts

## Quick Start

### 1. Start the API Server

```bash
python app/run_api.py
```

Server runs on `http://localhost:8000`

### 2. Interactive Documentation

Visit `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc` (ReDoc)

### 3. Try an Endpoint

```bash
# Check if API is running
curl http://localhost:8000/health
```

---

## API Architecture

```
┌─────────────────────────────────────────┐
│   External Application / Client         │
└──────────────┬──────────────────────────┘
               │ HTTP REST
               ▼
┌─────────────────────────────────────────┐
│   FastAPI Server (Port 8000)            │
│   ├─ Upload & Start Runs                │
│   ├─ Status Tracking                    │
│   ├─ STTM Approval                      │
│   └─ Report/Artifact Download           │
└──────────────┬──────────────────────────┘
               │ Shared State
               ▼
┌─────────────────────────────────────────┐
│   APIStateManager (Thread-Safe)         │
│   ├─ In-Memory Run Registry             │
│   ├─ Persistent State Files (JSON)      │
│   └─ Synchronized with Streamlit UI     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   Pipeline Orchestrator                 │
│   ├─ Bronze Agent                       │
│   ├─ Silver Agent                       │
│   ├─ Gold Agent                         │
│   └─ Report Agent                       │
└─────────────────────────────────────────┘
```

---

## Authentication

The API does **not require authentication** by default. For production, add authentication:

```python
from fastapi.security import HTTPBearer, HTTPAuthCredentials

security = HTTPBearer()

@app.get("/api/v1/runs")
async def list_runs(credentials: HTTPAuthCredentials = Depends(security)):
    token = credentials.credentials
    # Validate token here
    ...
```

---

## Base URL

```
http://localhost:8000
```

For remote servers:
```
http://<server-ip>:8000
http://<server-domain>:8000
```

---

## Endpoints

### Health Check

Check if the API server is running.

**Request:**
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-10-07T18:35:46.718000Z"
}
```

**Example:**
```bash
curl http://localhost:8000/health
```

---

### Upload File & Start Run

Upload a CSV/XLSX file and start a new pipeline run.

**Request:**
```http
POST /api/v1/runs/upload
Content-Type: multipart/form-data

file: <binary file content>
business_intent: <string>
user_email: <string (optional)>
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| file | File | Yes | CSV or XLSX file to process |
| business_intent | string | Yes | User's business question (e.g., "Find customer trends") |
| user_email | string | No | Email of user uploading (default: "api_user") |

**Response:**
```json
{
  "run_id": "A1B2C3D4",
  "message": "File uploaded successfully. Run A1B2C3D4 created.",
  "file_name": "customers.csv",
  "file_size_bytes": 1024576,
  "status": "pending"
}
```

**Status Codes:**
- 200: File uploaded, run created
- 400: Invalid file format or missing parameters
- 500: Server error during upload

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/runs/upload \
  -F "file=@customers.csv" \
  -F "business_intent=Analyze customer churn patterns" \
  -F "user_email=analyst@company.com"
```

---

### List Runs

List all pipeline runs, optionally filtered by status.

**Request:**
```http
GET /api/v1/runs?status=<status>&limit=<limit>
```

**Query Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| status | string | none | Filter by status: `pending`, `running`, `completed`, `failed`, `cancelled` |
| limit | integer | 20 | Max runs to return (1-100) |

**Response:**
```json
{
  "total_runs": 3,
  "runs": [
    {
      "run_id": "A1B2C3D4",
      "status": "completed",
      "phase": "report",
      "progress_percent": 100,
      "message": "Pipeline completed successfully",
      "created_at": "2024-10-07T10:00:00Z",
      "started_at": "2024-10-07T10:01:00Z",
      "completed_at": "2024-10-07T10:15:00Z",
      "error_message": null,
      "artifacts": {
        "profile": "/path/to/profile.json",
        "bronze_sttm": "/path/to/bronze_sttm.json",
        "silver_sttm": "/path/to/silver_sttm.json",
        "gold_sttm": "/path/to/gold_sttm.json",
        "report": "/path/to/report.html"
      }
    }
  ]
}
```

**Example:**
```bash
# List all completed runs
curl "http://localhost:8000/api/v1/runs?status=completed&limit=10"

# List all runs
curl "http://localhost:8000/api/v1/runs?limit=50"
```

---

### Get Run Status

Get the current status and progress of a specific run.

**Request:**
```http
GET /api/v1/runs/{run_id}
```

**Path Parameters:**
| Name | Type | Description |
|------|------|-------------|
| run_id | string | Run ID from upload endpoint |

**Response:**
```json
{
  "run_id": "A1B2C3D4",
  "status": "running",
  "phase": "silver_load",
  "progress_percent": 65,
  "message": "Loading Silver layer data...",
  "created_at": "2024-10-07T10:00:00Z",
  "started_at": "2024-10-07T10:01:00Z",
  "completed_at": null,
  "error_message": null,
  "artifacts": {
    "profile": "/path/to/profile.json",
    "bronze_sttm": "/path/to/bronze_sttm.json",
    "silver_sttm": null,
    "gold_sttm": null,
    "report": null
  }
}
```

**Status Codes:**
- 200: Success
- 404: Run not found

**Example:**
```bash
curl http://localhost:8000/api/v1/runs/A1B2C3D4
```

---

### Approve STTM

Approve the transformation rules (STTM) at a specific layer.

**Request:**
```http
POST /api/v1/runs/{run_id}/approve
Content-Type: application/json

{
  "layer": "bronze"
}
```

**Path Parameters:**
| Name | Type | Description |
|------|------|-------------|
| run_id | string | Run ID |

**Request Body:**
| Name | Type | Values | Description |
|------|------|--------|-------------|
| layer | string | `bronze`, `silver`, `gold` | Layer to approve |

**Response:**
```json
{
  "run_id": "A1B2C3D4",
  "layer": "bronze",
  "approved": true,
  "message": "BRONZE STTM approved"
}
```

**Status Codes:**
- 200: Approval recorded
- 400: Invalid layer
- 404: Run not found

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/runs/A1B2C3D4/approve \
  -H "Content-Type: application/json" \
  -d '{"layer": "bronze"}'
```

---

### Download Report

Download the final HTML report for a completed run.

**Request:**
```http
GET /api/v1/runs/{run_id}/report
```

**Path Parameters:**
| Name | Type | Description |
|------|------|-------------|
| run_id | string | Run ID |

**Response:**
- File download (HTML)

**Status Codes:**
- 200: Report file
- 404: Report not available

**Example:**
```bash
curl http://localhost:8000/api/v1/runs/A1B2C3D4/report -o report.html
```

---

### Download Artifact

Download a specific artifact (STTM, profile, etc.) from a run.

**Request:**
```http
GET /api/v1/runs/{run_id}/artifacts/{artifact_type}
```

**Path Parameters:**
| Name | Type | Values | Description |
|------|------|--------|-------------|
| run_id | string | - | Run ID |
| artifact_type | string | `profile`, `bronze_sttm`, `silver_sttm`, `gold_sttm`, `report` | Type of artifact |

**Response:**
- File download

**Status Codes:**
- 200: Artifact file
- 400: Unknown artifact type
- 404: Artifact not available

**Example:**
```bash
# Download Bronze STTM
curl http://localhost:8000/api/v1/runs/A1B2C3D4/artifacts/bronze_sttm -o bronze_sttm.json

# Download Profile
curl http://localhost:8000/api/v1/runs/A1B2C3D4/artifacts/profile -o profile.json
```

---

### Cancel Run

Cancel an in-progress pipeline run.

**Request:**
```http
POST /api/v1/runs/{run_id}/cancel
```

**Path Parameters:**
| Name | Type | Description |
|------|------|-------------|
| run_id | string | Run ID |

**Response:**
```json
{
  "run_id": "A1B2C3D4",
  "status": "cancelled",
  "message": "Run cancellation requested"
}
```

**Status Codes:**
- 200: Cancellation requested
- 400: Cannot cancel completed run
- 404: Run not found

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/runs/A1B2C3D4/cancel
```

---

### Delete Run

Delete a run and optionally delete associated files.

**Request:**
```http
DELETE /api/v1/runs/{run_id}?delete_files=false
```

**Path Parameters:**
| Name | Type | Description |
|------|------|-------------|
| run_id | string | Run ID |

**Query Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| delete_files | boolean | false | Also delete data files |

**Response:**
```json
{
  "run_id": "A1B2C3D4",
  "deleted": true,
  "message": "Run deleted (files deleted: true)"
}
```

**Status Codes:**
- 200: Run deleted
- 404: Run not found

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/runs/A1B2C3D4?delete_files=true"
```

---

### API Info

Get API metadata and endpoint listing.

**Request:**
```http
GET /api/v1/info
```

**Response:**
```json
{
  "api_name": "IDAMP REST API",
  "version": "1.0.0",
  "description": "Intent-Driven Agentic Medallion Pipeline API",
  "base_url": "http://localhost:8000/api/v1",
  "endpoints": {
    "POST /runs/upload": "Upload file and start new run",
    "GET /runs": "List all runs",
    "GET /runs/{run_id}": "Get run status",
    "POST /runs/{run_id}/approve": "Approve STTM at layer",
    "GET /runs/{run_id}/report": "Download final report",
    "GET /runs/{run_id}/artifacts/{type}": "Download artifact",
    "POST /runs/{run_id}/cancel": "Cancel run",
    "DELETE /runs/{run_id}": "Delete run",
    "GET /info": "This endpoint"
  }
}
```

**Example:**
```bash
curl http://localhost:8000/api/v1/info
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error |

---

## Error Handling

All errors return JSON with `detail` field:

```json
{
  "detail": "Run 'XYZ' not found"
}
```

**Common errors:**

```json
{
  "detail": "Unsupported file format: doc. Use CSV or XLSX."
}
```

```json
{
  "detail": "Run 'XYZ' not found"
}
```

```json
{
  "detail": "Invalid status: pending_review. Use: pending, running, completed, failed, cancelled"
}
```

---

## Complete Examples

### Python Example

```python
import requests
from pathlib import Path

API_BASE = "http://localhost:8000/api/v1"

# 1. Upload file and start run
files = {"file": open("customers.csv", "rb")}
data = {
    "business_intent": "Identify high-value customer segments",
    "user_email": "analyst@company.com"
}
response = requests.post(f"{API_BASE}/runs/upload", files=files, data=data)
run_data = response.json()
run_id = run_data["run_id"]
print(f"Started run: {run_id}")

# 2. Poll for status until completion
import time
while True:
    status = requests.get(f"{API_BASE}/runs/{run_id}").json()
    print(f"Status: {status['status']}, Progress: {status['progress_percent']}%")
    
    if status["status"] in ["completed", "failed"]:
        break
    time.sleep(5)

# 3. Approve STTM at Bronze layer
approval = requests.post(
    f"{API_BASE}/runs/{run_id}/approve",
    json={"layer": "bronze"}
)
print(f"Approval: {approval.json()['message']}")

# 4. Download final report
report = requests.get(f"{API_BASE}/runs/{run_id}/report")
with open("report.html", "wb") as f:
    f.write(report.content)
print("Report saved")
```

### JavaScript/Node.js Example

```javascript
const API_BASE = "http://localhost:8000/api/v1";

// 1. Upload file
async function startRun(file, intent) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("business_intent", intent);
  formData.append("user_email", "analyst@company.com");
  
  const response = await fetch(`${API_BASE}/runs/upload`, {
    method: "POST",
    body: formData
  });
  
  return await response.json();
}

// 2. Poll for status
async function checkStatus(runId) {
  const response = await fetch(`${API_BASE}/runs/${runId}`);
  return await response.json();
}

// 3. Approve STTM
async function approveSttm(runId, layer) {
  const response = await fetch(`${API_BASE}/runs/${runId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layer })
  });
  return await response.json();
}

// 4. Download report
async function downloadReport(runId) {
  const response = await fetch(`${API_BASE}/runs/${runId}/report`);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

// Example usage
const fileInput = document.querySelector("input[type='file']");
const { run_id } = await startRun(fileInput.files[0], "Analyze trends");
console.log(`Started run: ${run_id}`);
```

### cURL Examples

**Upload and start:**
```bash
curl -X POST http://localhost:8000/api/v1/runs/upload \
  -F "file=@data.csv" \
  -F "business_intent=Find patterns" \
  -F "user_email=user@company.com"
```

**Get status:**
```bash
curl http://localhost:8000/api/v1/runs/A1B2C3D4
```

**List completed runs:**
```bash
curl "http://localhost:8000/api/v1/runs?status=completed&limit=20"
```

**Approve Bronze STTM:**
```bash
curl -X POST http://localhost:8000/api/v1/runs/A1B2C3D4/approve \
  -H "Content-Type: application/json" \
  -d '{"layer":"bronze"}'
```

**Download report:**
```bash
curl http://localhost:8000/api/v1/runs/A1B2C3D4/report -o report.html
```

**Download Bronze STTM:**
```bash
curl http://localhost:8000/api/v1/runs/A1B2C3D4/artifacts/bronze_sttm \
  -o bronze_sttm.json
```

**Cancel run:**
```bash
curl -X POST http://localhost:8000/api/v1/runs/A1B2C3D4/cancel
```

**Delete run with files:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/runs/A1B2C3D4?delete_files=true"
```

---

## Integration with Streamlit UI

The REST API shares state with the Streamlit UI via `APIStateManager`:

```
Streamlit UI ←→ APIStateManager ←→ REST API
       ↓                            ↓
  session state                 Persistent JSON
  (in-browser)                  (audit_logs/)
```

Both systems access the same run history and can start/track the same runs.

---

## Running Both Services

Start both API and Streamlit UI in separate terminals:

**Terminal 1 - API Server:**
```bash
python app/run_api.py
# Server runs on http://localhost:8000
```

**Terminal 2 - Streamlit UI:**
```bash
streamlit run app/streamlit_app.py
# UI runs on http://localhost:8501
```

Now you can:
- Upload files via API or UI
- Approve STTMs from API while tracking in UI
- Download reports from API or UI
- Both systems share the same run history

---

## Troubleshooting

**"Connection refused"**
- Ensure API server is running: `python app/run_api.py`

**"File not found"**
- Check run_id is correct
- Verify file was downloaded before report/artifact was generated

**"Run not found"**
- Verify run_id matches exactly (case-sensitive)
- Check run exists: `curl http://localhost:8000/api/v1/runs`

**CORS errors in JavaScript**
- API has CORS enabled by default
- For production, configure `allow_origins` in `app/api.py`

---

## Next Steps

1. Install FastAPI: `pip install -r requirements.txt`
2. Start API: `python app/run_api.py`
3. Try endpoints: http://localhost:8000/docs
4. Integrate into your application using examples above
