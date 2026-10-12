"""User management and session handling for multi-user pipeline support."""

import os
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json

from core.config import BASE_DIR
from core.audit import AuditLogger


@dataclass
class UserSession:
    """Represents a single user session."""
    username: str
    session_id: str
    started_at: str
    last_activity: str
    current_run_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class RunRecord:
    """Represents a single pipeline run by a user."""
    run_id: str
    username: str
    started_at: str
    completed_at: Optional[str]
    status: str  # "running", "completed", "failed"
    phase: str  # "raw", "bronze", "silver", "gold", "report"
    input_files: List[str]
    output_files: List[str]
    quality_score: Optional[float]
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class UserManager:
    """Manage user sessions and isolated data directories."""
    
    def __init__(self):
        """Initialize user manager."""
        self.users_dir = BASE_DIR / "users"
        self.users_dir.mkdir(exist_ok=True)
        self.users_file = self.users_dir / "users.json"
        self._ensure_users_file()
    
    def _ensure_users_file(self) -> None:
        """Ensure users.json exists."""
        if not self.users_file.exists():
            self.users_file.write_text(json.dumps({"users": []}, indent=2))
    
    def register_user(self, username: str) -> bool:
        """
        Register a new user or confirm existing user.
        
        Args:
            username: Unique username (alphanumeric, no spaces)
        
        Returns:
            True if registered (new or existing), False if invalid
        """
        # Validate username
        if not username or len(username) < 3:
            return False
        
        if not username.replace("_", "").replace("-", "").isalnum():
            return False
        
        # Load users
        users_data = json.loads(self.users_file.read_text())
        existing_users = [u["username"] for u in users_data.get("users", [])]
        
        # Check if user already exists
        if username in existing_users:
            return True
        
        # Create user directory structure
        user_dir = self.users_dir / username
        user_dir.mkdir(exist_ok=True)
        
        (user_dir / "data").mkdir(exist_ok=True)
        (user_dir / "data" / "landing").mkdir(exist_ok=True)
        (user_dir / "data" / "bronze_layer").mkdir(exist_ok=True)
        (user_dir / "data" / "silver_layer").mkdir(exist_ok=True)
        (user_dir / "data" / "gold_layer").mkdir(exist_ok=True)
        (user_dir / "data" / "profiles").mkdir(exist_ok=True)
        (user_dir / "data" / "sttm").mkdir(exist_ok=True)
        (user_dir / "data" / "traces").mkdir(exist_ok=True)
        (user_dir / "reports").mkdir(exist_ok=True)
        (user_dir / "audit_logs").mkdir(exist_ok=True)
        (user_dir / "run_history").mkdir(exist_ok=True)
        
        # Register user
        users_data["users"].append({
            "username": username,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": datetime.now(timezone.utc).isoformat(),
        })
        
        self.users_file.write_text(json.dumps(users_data, indent=2))
        
        return True
    
    def get_user_dir(self, username: str) -> Path:
        """
        Get user's base directory.
        
        Args:
            username: Username
        
        Returns:
            Path to user's directory
        """
        return self.users_dir / username
    
    def get_user_data_dir(self, username: str) -> Path:
        """Get user's data directory."""
        return self.get_user_dir(username) / "data"
    
    def get_user_reports_dir(self, username: str) -> Path:
        """Get user's reports directory."""
        return self.get_user_dir(username) / "reports"
    
    def get_user_audit_dir(self, username: str) -> Path:
        """Get user's audit logs directory."""
        return self.get_user_dir(username) / "audit_logs"
    
    def get_user_history_dir(self, username: str) -> Path:
        """Get user's run history directory."""
        return self.get_user_dir(username) / "run_history"
    
    def get_paths_for_user(self, username: str) -> Dict[str, Path]:
        """
        Get all important paths for a user.
        
        Args:
            username: Username
        
        Returns:
            Dict with keys: landing, bronze, silver, gold, profiles, sttm,
                           reports, audit_logs, traces
        """
        user_data_dir = self.get_user_data_dir(username)
        
        return {
            "base": self.get_user_dir(username),
            "landing": user_data_dir / "landing",
            "bronze": user_data_dir / "bronze_layer",
            "silver": user_data_dir / "silver_layer",
            "gold": user_data_dir / "gold_layer",
            "profiles": user_data_dir / "profiles",
            "sttm": user_data_dir / "sttm",
            "traces": user_data_dir / "data" / "traces",
            "reports": self.get_user_reports_dir(username),
            "audit_logs": self.get_user_audit_dir(username),
            "run_history": self.get_user_history_dir(username),
        }
    
    def record_run_start(
        self,
        username: str,
        run_id: str,
        input_files: List[str],
    ) -> None:
        """
        Record that a pipeline run has started.
        
        Args:
            username: Username
            run_id: Pipeline run ID
            input_files: List of input file paths
        """
        history_dir = self.get_user_history_dir(username)
        run_file = history_dir / f"{run_id}.json"
        
        run_record = RunRecord(
            run_id=run_id,
            username=username,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
            status="running",
            phase="raw",
            input_files=input_files,
            output_files=[],
            quality_score=None,
        )
        
        run_file.write_text(json.dumps(run_record.to_dict(), indent=2))
    
    def record_run_progress(
        self,
        username: str,
        run_id: str,
        phase: str,
        output_files: List[str],
        quality_score: Optional[float] = None,
    ) -> None:
        """
        Record progress of a running pipeline.
        
        Args:
            username: Username
            run_id: Pipeline run ID
            phase: Current phase (bronze, silver, gold, report)
            output_files: List of output file paths
            quality_score: Quality score (optional)
        """
        history_dir = self.get_user_history_dir(username)
        run_file = history_dir / f"{run_id}.json"
        
        if not run_file.exists():
            return
        
        run_data = json.loads(run_file.read_text())
        run_data["phase"] = phase
        run_data["output_files"] = output_files
        if quality_score is not None:
            run_data["quality_score"] = quality_score
        
        run_file.write_text(json.dumps(run_data, indent=2))
    
    def record_run_complete(
        self,
        username: str,
        run_id: str,
        output_files: List[str],
        quality_score: float,
    ) -> None:
        """
        Record that a pipeline run has completed successfully.
        
        Args:
            username: Username
            run_id: Pipeline run ID
            output_files: List of output file paths
            quality_score: Final quality score
        """
        history_dir = self.get_user_history_dir(username)
        run_file = history_dir / f"{run_id}.json"
        
        if not run_file.exists():
            return
        
        run_data = json.loads(run_file.read_text())
        run_data["status"] = "completed"
        run_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        run_data["output_files"] = output_files
        run_data["quality_score"] = quality_score
        run_data["phase"] = "report"
        
        run_file.write_text(json.dumps(run_data, indent=2))
    
    def record_run_failed(
        self,
        username: str,
        run_id: str,
        phase: str,
        error_message: str,
    ) -> None:
        """
        Record that a pipeline run has failed.
        
        Args:
            username: Username
            run_id: Pipeline run ID
            phase: Phase where failure occurred
            error_message: Error message
        """
        history_dir = self.get_user_history_dir(username)
        run_file = history_dir / f"{run_id}.json"
        
        if not run_file.exists():
            return
        
        run_data = json.loads(run_file.read_text())
        run_data["status"] = "failed"
        run_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        run_data["phase"] = phase
        run_data["error_message"] = error_message
        
        run_file.write_text(json.dumps(run_data, indent=2))
    
    def get_user_runs(
        self,
        username: str,
        limit: Optional[int] = None,
        status_filter: Optional[str] = None,
    ) -> List[RunRecord]:
        """
        Get all runs for a user.
        
        Args:
            username: Username
            limit: Maximum number of runs to return (default None = all)
            status_filter: Filter by status (running, completed, failed)
        
        Returns:
            List of RunRecord objects, newest first
        """
        history_dir = self.get_user_history_dir(username)
        
        if not history_dir.exists():
            return []
        
        runs = []
        for run_file in history_dir.glob("*.json"):
            try:
                run_data = json.loads(run_file.read_text())
                run = RunRecord(**run_data)
                
                if status_filter and run.status != status_filter:
                    continue
                
                runs.append(run)
            
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Sort by started_at (newest first)
        runs.sort(key=lambda r: r.started_at, reverse=True)
        
        if limit:
            runs = runs[:limit]
        
        return runs
    
    def get_user_run(self, username: str, run_id: str) -> Optional[RunRecord]:
        """
        Get a specific run record.
        
        Args:
            username: Username
            run_id: Run ID
        
        Returns:
            RunRecord if found, None otherwise
        """
        history_dir = self.get_user_history_dir(username)
        run_file = history_dir / f"{run_id}.json"
        
        if not run_file.exists():
            return None
        
        try:
            run_data = json.loads(run_file.read_text())
            return RunRecord(**run_data)
        
        except (json.JSONDecodeError, TypeError):
            return None
    
    def get_all_users(self) -> List[str]:
        """
        Get list of all registered users.
        
        Returns:
            List of usernames
        """
        try:
            users_data = json.loads(self.users_file.read_text())
            return [u["username"] for u in users_data.get("users", [])]
        
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def user_exists(self, username: str) -> bool:
        """Check if user is registered."""
        return username in self.get_all_users()
    
    def get_user_stats(self, username: str) -> Dict:
        """
        Get statistics for a user.
        
        Args:
            username: Username
        
        Returns:
            Dict with stats: total_runs, completed, failed, running, avg_quality
        """
        runs = self.get_user_runs(username)
        
        completed = [r for r in runs if r.status == "completed"]
        failed = [r for r in runs if r.status == "failed"]
        running = [r for r in runs if r.status == "running"]
        
        quality_scores = [r.quality_score for r in completed if r.quality_score]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        
        return {
            "total_runs": len(runs),
            "completed": len(completed),
            "failed": len(failed),
            "running": len(running),
            "avg_quality_score": round(avg_quality, 1),
            "last_run": runs[0].started_at if runs else None,
        }
    
    def cleanup_old_runs(
        self,
        username: str,
        days_to_keep: int = 30,
    ) -> int:
        """
        Delete run history older than specified days.
        
        Args:
            username: Username
            days_to_keep: Number of days to retain
        
        Returns:
            Number of runs deleted
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        history_dir = self.get_user_history_dir(username)
        
        if not history_dir.exists():
            return 0
        
        deleted_count = 0
        for run_file in history_dir.glob("*.json"):
            try:
                run_data = json.loads(run_file.read_text())
                started_at = datetime.fromisoformat(run_data["started_at"])
                
                if started_at < cutoff_date:
                    run_file.unlink()
                    deleted_count += 1
            
            except (json.JSONDecodeError, ValueError, KeyError):
                continue
        
        return deleted_count


# Singleton instance
_user_manager = None


def get_user_manager() -> UserManager:
    """Get or create user manager singleton."""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager
