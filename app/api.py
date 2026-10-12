"""
FastAPI REST API for programmatic access to the Agentic Medallion Pipeline.

This API allows external applications to:
- Upload files and start pipeline runs
- Check run status and progress
- Download reports and artifacts
- List run history

The API shares state with the Streamlit UI via APIStateManager.
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse as FastAPIFileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.config import LANDING_DIR, REPORTS_DIR
from app.api_state import (
    get_state_manager,
    RunState,
    RunStatus,
    RunPhase,
    RunMetadata,
)


# ─── Create FastAPI App ──────────────────────────────────────────────────────

app = FastAPI(
    title="IDAMP REST API",
    description="Intent-Driven Agentic Medallion Pipeline API",
    version="1.0.0",
)

# Enable CORS for external applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Models ────────────────────────────────────────────────────────

class FileUploadResponse(BaseModel):
    """Response from file upload endpoint."""
    run_id: str = Field(..., description="Unique run ID")
    message: str
    file_name: str
    file_size_bytes: int
    status: str = "pending"


class RunStatusResponse(BaseModel):
    """Response from status check endpoint."""
    run_id: str
    status: str
    phase: str
    progress_percent: int
    message: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    artifacts: Optional[dict] = None


class RunListResponse(BaseModel):
    """Response from list runs endpoint."""
    total_runs: int
    runs: List[RunStatusResponse]


class ReportDownloadResponse(BaseModel):
    """Response confirming report is ready for download."""
    run_id: str
    report_path: str
    file_size_bytes: int
    ready: bool


class ApprovalRequest(BaseModel):
    """Request to approve STTM at a layer."""
    run_id: str = Field(..., description="Run ID")
    layer: str = Field(..., description="Layer: bronze, silver, or gold")


class ApprovalResponse(BaseModel):
    """Response from approval request."""
    run_id: str
    layer: str
    approved: bool
    message: str


# ─── Helper Functions ───────────────────────────────────────────────────────

def _get_run_or_404(run_id: str) -> RunState:
    """Get run state or raise 404."""
    state_manager = get_state_manager()
    run = state_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


def _save_uploaded_file(upload_file: UploadFile, run_id: str, dest_dir: Path) -> tuple[str, int]:
    """
    Save uploaded file to destination directory.
    
    Returns:
        (file_path, file_size_bytes)
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Use original filename, prefixed with run_id
    filename = f"{run_id}_{upload_file.filename}"
    file_path = dest_dir / filename
    
    # Read uploaded content
    content = upload_file.file.read()
    file_size = len(content)
    
    # Write to disk
    with open(file_path, "wb") as f:
        f.write(content)
    
    return str(file_path), file_size


def _count_records(file_path: str) -> int:
    """
    Count records in uploaded file (approximate).
    
    For CSV/XLSX, counts rows. For other formats, returns 0.
    """
    if file_path.endswith(".csv"):
        import pandas as pd
        try:
            df = pd.read_csv(file_path)
            return len(df)
        except Exception:
            return 0
    elif file_path.endswith(".xlsx"):
        import pandas as pd
        try:
            df = pd.read_excel(file_path)
            return len(df)
        except Exception:
            return 0
    return 0


def _run_state_to_response(state: RunState) -> RunStatusResponse:
    """Convert RunState to API response format."""
    artifacts = None
    if any([
        state.profile_path,
        state.bronze_sttm_path,
        state.silver_sttm_path,
        state.gold_sttm_path,
        state.report_path,
    ]):
        artifacts = {
            "profile": state.profile_path,
            "bronze_sttm": state.bronze_sttm_path,
            "silver_sttm": state.silver_sttm_path,
            "gold_sttm": state.gold_sttm_path,
            "report": state.report_path,
        }
    
    return RunStatusResponse(
        run_id=state.run_id,
        status=state.status.value,
        phase=state.phase.value,
        progress_percent=state.progress_percent,
        message=state.message,
        created_at=state.created_at,
        started_at=state.started_at,
        completed_at=state.completed_at,
        error_message=state.error_message,
        artifacts=artifacts,
    )


# ─── Health Check ───────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ─── Upload & Start Run ──────────────────────────────────────────────────────

@app.post("/api/v1/runs/upload", response_model=FileUploadResponse)
async def upload_and_start_run(
    file: UploadFile = File(..., description="CSV or XLSX file to process"),
    business_intent: str = Form(..., description="What business question to answer?"),
    user_email: Optional[str] = Form(None, description="User email (optional)"),
) -> FileUploadResponse:
    """
    Upload a data file and start a new pipeline run.
    
    Args:
        file: CSV or XLSX file
        business_intent: User's business question (e.g., "Analyze customer churn")
        user_email: Email of user who uploaded (optional)
    
    Returns:
        FileUploadResponse with run_id and status
    
    Example:
        curl -X POST http://localhost:8000/api/v1/runs/upload \\
          -F "file=@data.csv" \\
          -F "business_intent=Find customer trends" \\
          -F "user_email=user@example.com"
    """
    state_manager = get_state_manager()
    
    # Generate unique run ID
    run_id = str(uuid.uuid4())[:8].upper()
    
    # Determine file format
    file_format = Path(file.filename).suffix.lstrip(".").lower()
    if file_format not in ["csv", "xlsx", "xls"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_format}. Use CSV or XLSX."
        )
    
    try:
        # Save uploaded file
        file_path, file_size = _save_uploaded_file(file, run_id, LANDING_DIR)
        
        # Count records
        num_records = _count_records(file_path)
        
        # Create run in state manager
        run_state = state_manager.create_run(
            run_id=run_id,
            business_intent=business_intent,
            input_file=file.filename,
            input_format=file_format,
            file_size_bytes=file_size,
            num_records=num_records,
            uploaded_by=user_email or "api_user",
        )
        
        return FileUploadResponse(
            run_id=run_id,
            message=f"File uploaded successfully. Run {run_id} created.",
            file_name=file.filename,
            file_size_bytes=file_size,
            status=run_state.status.value,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ─── Check Run Status ────────────────────────────────────────────────────────

@app.get("/api/v1/runs/{run_id}", response_model=RunStatusResponse)
async def get_run_status(run_id: str) -> RunStatusResponse:
    """
    Get the current status of a pipeline run.
    
    Args:
        run_id: Run ID from upload endpoint
    
    Returns:
        RunStatusResponse with current phase, progress, and artifacts
    
    Example:
        curl http://localhost:8000/api/v1/runs/A1B2C3D4
    """
    run = _get_run_or_404(run_id)
    return _run_state_to_response(run)


# ─── List Runs ──────────────────────────────────────────────────────────────

@app.get("/api/v1/runs", response_model=RunListResponse)
async def list_runs(
    status: Optional[str] = Query(None, description="Filter by status: pending, running, completed, failed, cancelled"),
    limit: int = Query(20, ge=1, le=100, description="Max runs to return"),
) -> RunListResponse:
    """
    List all pipeline runs, optionally filtered by status.
    
    Args:
        status: Optional status filter
        limit: Maximum runs to return (default: 20)
    
    Returns:
        RunListResponse with list of runs
    
    Example:
        curl "http://localhost:8000/api/v1/runs?status=completed&limit=10"
    """
    state_manager = get_state_manager()
    
    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = RunStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Use: pending, running, completed, failed, cancelled"
            )
    
    # Get runs
    runs = state_manager.list_runs(status=status_filter)
    runs = runs[:limit]  # Limit results
    
    return RunListResponse(
        total_runs=len(runs),
        runs=[_run_state_to_response(r) for r in runs],
    )


# ─── Approve STTM ───────────────────────────────────────────────────────────

@app.post("/api/v1/runs/{run_id}/approve", response_model=ApprovalResponse)
async def approve_sttm(
    run_id: str,
    request: ApprovalRequest,
) -> ApprovalResponse:
    """
    Approve STTM (transformation rules) at a specific layer.
    
    Args:
        run_id: Run ID
        request: ApprovalRequest with layer (bronze, silver, gold)
    
    Returns:
        ApprovalResponse confirming approval
    
    Example:
        curl -X POST http://localhost:8000/api/v1/runs/A1B2C3D4/approve \\
          -H "Content-Type: application/json" \\
          -d '{"layer": "bronze"}'
    """
    state_manager = get_state_manager()
    run = _get_run_or_404(run_id)
    
    layer = request.layer.lower()
    if layer not in ["bronze", "silver", "gold"]:
        raise HTTPException(
            status_code=400,
            detail="Layer must be 'bronze', 'silver', or 'gold'"
        )
    
    # Update approval state
    if layer == "bronze":
        state_manager.update_run(run_id, bronze_sttm_approved=True)
    elif layer == "silver":
        state_manager.update_run(run_id, silver_sttm_approved=True)
    elif layer == "gold":
        state_manager.update_run(run_id, gold_sttm_approved=True)
    
    return ApprovalResponse(
        run_id=run_id,
        layer=layer,
        approved=True,
        message=f"{layer.upper()} STTM approved",
    )


# ─── Download Report ────────────────────────────────────────────────────────

@app.get("/api/v1/runs/{run_id}/report")
async def download_report(run_id: str):
    """
    Download the final report for a completed run.
    
    Args:
        run_id: Run ID
    
    Returns:
        File download or error if report not ready
    
    Example:
        curl http://localhost:8000/api/v1/runs/A1B2C3D4/report -o report.html
    """
    run = _get_run_or_404(run_id)
    
    if not run.report_path:
        raise HTTPException(
            status_code=404,
            detail=f"Report not available. Run status: {run.status.value}"
        )
    
    report_file = Path(run.report_path)
    if not report_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Report file not found on disk"
        )
    
    return FastAPIFileResponse(
        path=report_file,
        filename=report_file.name,
        media_type="text/html",
    )


# ─── Download Artifact ──────────────────────────────────────────────────────

@app.get("/api/v1/runs/{run_id}/artifacts/{artifact_type}")
async def download_artifact(run_id: str, artifact_type: str):
    """
    Download a specific artifact from a run.
    
    Args:
        run_id: Run ID
        artifact_type: Type of artifact (profile, bronze_sttm, silver_sttm, gold_sttm, report)
    
    Returns:
        File download
    
    Example:
        curl http://localhost:8000/api/v1/runs/A1B2C3D4/artifacts/bronze_sttm -o sttm.json
    """
    run = _get_run_or_404(run_id)
    
    # Map artifact type to run attribute
    artifact_attr = {
        "profile": "profile_path",
        "bronze_sttm": "bronze_sttm_path",
        "silver_sttm": "silver_sttm_path",
        "gold_sttm": "gold_sttm_path",
        "report": "report_path",
    }.get(artifact_type)
    
    if not artifact_attr:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown artifact type: {artifact_type}"
        )
    
    artifact_path = getattr(run, artifact_attr)
    if not artifact_path:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact '{artifact_type}' not available for run {run_id}"
        )
    
    artifact_file = Path(artifact_path)
    if not artifact_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Artifact file not found: {artifact_path}"
        )
    
    return FastAPIFileResponse(
        path=artifact_file,
        filename=artifact_file.name,
    )


# ─── Cancel Run ──────────────────────────────────────────────────────────────

@app.post("/api/v1/runs/{run_id}/cancel", response_model=dict)
async def cancel_run(run_id: str) -> dict:
    """
    Cancel an in-progress pipeline run.
    
    Args:
        run_id: Run ID
    
    Returns:
        JSON with cancellation status
    
    Example:
        curl -X POST http://localhost:8000/api/v1/runs/A1B2C3D4/cancel
    """
    state_manager = get_state_manager()
    run = _get_run_or_404(run_id)
    
    if run.status == RunStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel completed run"
        )
    
    state_manager.update_run(
        run_id,
        status=RunStatus.CANCELLED,
        message="Cancelled by API request",
    )
    
    return {
        "run_id": run_id,
        "status": "cancelled",
        "message": "Run cancellation requested",
    }


# ─── Delete Run ──────────────────────────────────────────────────────────────

@app.delete("/api/v1/runs/{run_id}", response_model=dict)
async def delete_run(run_id: str, delete_files: bool = False) -> dict:
    """
    Delete a run from state manager (optionally delete files).
    
    Args:
        run_id: Run ID
        delete_files: Whether to delete associated data files
    
    Returns:
        JSON with deletion status
    
    Example:
        curl -X DELETE "http://localhost:8000/api/v1/runs/A1B2C3D4?delete_files=true"
    """
    state_manager = get_state_manager()
    run = _get_run_or_404(run_id)
    
    # Optionally delete associated files
    if delete_files:
        for artifact_path in [
            run.profile_path,
            run.bronze_sttm_path,
            run.silver_sttm_path,
            run.gold_sttm_path,
            run.report_path,
        ]:
            if artifact_path and Path(artifact_path).exists():
                try:
                    Path(artifact_path).unlink()
                except Exception as e:
                    print(f"Failed to delete {artifact_path}: {e}")
    
    # Delete state file
    state_file = state_manager._get_run_file(run_id)
    if state_file.exists():
        state_file.unlink()
    
    return {
        "run_id": run_id,
        "deleted": True,
        "message": f"Run deleted (files deleted: {delete_files})",
    }


# ─── API Metadata ────────────────────────────────────────────────────────────

@app.get("/api/v1/info")
async def api_info():
    """Get API information and available endpoints."""
    return {
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
            "GET /info": "This endpoint",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
