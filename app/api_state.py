"""
Shared state manager for FastAPI and Streamlit UI.

This module provides a centralized state management system that allows:
- FastAPI endpoints to start pipeline runs
- Streamlit UI to check and display run status
- Both systems to access the same run history and artifacts
"""

import json
import threading
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from core.config import AUDIT_DIR


# ─── Enums ──────────────────────────────────────────────────────────────────

class RunStatus(str, Enum):
    """Pipeline run status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunPhase(str, Enum):
    """Current phase of pipeline execution."""
    UPLOAD = "upload"
    BRONZE_STTM = "bronze_sttm"
    BRONZE_LOAD = "bronze_load"
    SILVER_STTM = "silver_sttm"
    SILVER_LOAD = "silver_load"
    GOLD_STTM = "gold_sttm"
    GOLD_LOAD = "gold_load"
    REPORT = "report"


# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class RunMetadata:
    """Metadata for a single pipeline run."""
    run_id: str
    uploaded_at: str
    uploaded_by: str
    business_intent: str
    input_file: str
    input_format: str
    file_size_bytes: int
    num_records: int


@dataclass
class RunState:
    """Complete state for a pipeline run."""
    run_id: str
    status: RunStatus
    phase: RunPhase
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    
    # Artifacts
    profile_path: Optional[str] = None
    bronze_sttm_path: Optional[str] = None
    silver_sttm_path: Optional[str] = None
    gold_sttm_path: Optional[str] = None
    report_path: Optional[str] = None
    
    # Approval states
    bronze_sttm_approved: bool = False
    silver_sttm_approved: bool = False
    gold_sttm_approved: bool = False
    
    # Metadata
    metadata: Optional[RunMetadata] = None
    
    # Progress
    progress_percent: int = 0
    message: str = ""


# ─── State Manager ──────────────────────────────────────────────────────────

class APIStateManager:
    """Centralized state manager for pipeline runs (thread-safe)."""
    
    def __init__(self, state_dir: Path = AUDIT_DIR):
        """
        Initialize state manager.
        
        Args:
            state_dir: Directory to persist run states
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._runs: Dict[str, RunState] = {}
        self._load_all_runs()
    
    def _get_run_file(self, run_id: str) -> Path:
        """Get path for run state file."""
        return self.state_dir / f"run_{run_id}_state.json"
    
    def _load_all_runs(self) -> None:
        """Load all run states from disk."""
        for state_file in self.state_dir.glob("run_*_state.json"):
            try:
                with open(state_file) as f:
                    data = json.load(f)
                    # Reconstruct RunState from JSON
                    state = self._dict_to_run_state(data)
                    self._runs[state.run_id] = state
            except Exception as e:
                print(f"Error loading run state {state_file}: {e}")
    
    def _dict_to_run_state(self, data: Dict[str, Any]) -> RunState:
        """Convert dict to RunState dataclass."""
        if data.get("metadata"):
            metadata = RunMetadata(**data["metadata"])
        else:
            metadata = None
        
        return RunState(
            run_id=data["run_id"],
            status=RunStatus(data["status"]),
            phase=RunPhase(data["phase"]),
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error_message=data.get("error_message"),
            profile_path=data.get("profile_path"),
            bronze_sttm_path=data.get("bronze_sttm_path"),
            silver_sttm_path=data.get("silver_sttm_path"),
            gold_sttm_path=data.get("gold_sttm_path"),
            report_path=data.get("report_path"),
            bronze_sttm_approved=data.get("bronze_sttm_approved", False),
            silver_sttm_approved=data.get("silver_sttm_approved", False),
            gold_sttm_approved=data.get("gold_sttm_approved", False),
            metadata=metadata,
            progress_percent=data.get("progress_percent", 0),
            message=data.get("message", ""),
        )
    
    def _run_state_to_dict(self, state: RunState) -> Dict[str, Any]:
        """Convert RunState to dict for JSON serialization."""
        data = asdict(state)
        data["status"] = state.status.value
        data["phase"] = state.phase.value
        if state.metadata:
            data["metadata"] = asdict(state.metadata)
        return data
    
    def _save_run(self, state: RunState) -> None:
        """Persist run state to disk."""
        run_file = self._get_run_file(state.run_id)
        with open(run_file, "w") as f:
            json.dump(self._run_state_to_dict(state), f, indent=2)
    
    def create_run(
        self,
        run_id: str,
        business_intent: str,
        input_file: str,
        input_format: str,
        file_size_bytes: int,
        num_records: int,
        uploaded_by: str = "api",
    ) -> RunState:
        """
        Create a new run.
        
        Args:
            run_id: Unique run identifier
            business_intent: User's business question
            input_file: Name of uploaded file
            input_format: File format (csv, xlsx, etc.)
            file_size_bytes: Size of input file
            num_records: Number of records in file
            uploaded_by: User/system that uploaded (default: "api")
        
        Returns:
            Created RunState
        """
        with self._lock:
            now = datetime.utcnow().isoformat() + "Z"
            
            metadata = RunMetadata(
                run_id=run_id,
                uploaded_at=now,
                uploaded_by=uploaded_by,
                business_intent=business_intent,
                input_file=input_file,
                input_format=input_format,
                file_size_bytes=file_size_bytes,
                num_records=num_records,
            )
            
            state = RunState(
                run_id=run_id,
                status=RunStatus.PENDING,
                phase=RunPhase.UPLOAD,
                created_at=now,
                metadata=metadata,
            )
            
            self._runs[run_id] = state
            self._save_run(state)
            
            return state
    
    def get_run(self, run_id: str) -> Optional[RunState]:
        """Get run state by ID."""
        with self._lock:
            return self._runs.get(run_id)
    
    def list_runs(self, status: Optional[RunStatus] = None) -> List[RunState]:
        """
        List all runs, optionally filtered by status.
        
        Args:
            status: Filter by status (optional)
        
        Returns:
            List of RunState objects
        """
        with self._lock:
            runs = list(self._runs.values())
            if status:
                runs = [r for r in runs if r.status == status]
            # Sort by created_at descending (most recent first)
            runs.sort(key=lambda r: r.created_at, reverse=True)
            return runs
    
    def update_run(
        self,
        run_id: str,
        status: Optional[RunStatus] = None,
        phase: Optional[RunPhase] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        error_message: Optional[str] = None,
        profile_path: Optional[str] = None,
        bronze_sttm_path: Optional[str] = None,
        silver_sttm_path: Optional[str] = None,
        gold_sttm_path: Optional[str] = None,
        report_path: Optional[str] = None,
        bronze_sttm_approved: Optional[bool] = None,
        silver_sttm_approved: Optional[bool] = None,
        gold_sttm_approved: Optional[bool] = None,
        progress_percent: Optional[int] = None,
        message: Optional[str] = None,
    ) -> Optional[RunState]:
        """Update run state with new values."""
        with self._lock:
            if run_id not in self._runs:
                return None
            
            state = self._runs[run_id]
            
            if status is not None:
                state.status = status
            if phase is not None:
                state.phase = phase
            if started_at is not None:
                state.started_at = started_at
            if completed_at is not None:
                state.completed_at = completed_at
            if error_message is not None:
                state.error_message = error_message
            if profile_path is not None:
                state.profile_path = profile_path
            if bronze_sttm_path is not None:
                state.bronze_sttm_path = bronze_sttm_path
            if silver_sttm_path is not None:
                state.silver_sttm_path = silver_sttm_path
            if gold_sttm_path is not None:
                state.gold_sttm_path = gold_sttm_path
            if report_path is not None:
                state.report_path = report_path
            if bronze_sttm_approved is not None:
                state.bronze_sttm_approved = bronze_sttm_approved
            if silver_sttm_approved is not None:
                state.silver_sttm_approved = silver_sttm_approved
            if gold_sttm_approved is not None:
                state.gold_sttm_approved = gold_sttm_approved
            if progress_percent is not None:
                state.progress_percent = progress_percent
            if message is not None:
                state.message = message
            
            self._save_run(state)
            return state


# ─── Singleton Instance ─────────────────────────────────────────────────────

_state_manager = None


def get_state_manager() -> APIStateManager:
    """Get or create the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = APIStateManager()
    return _state_manager
