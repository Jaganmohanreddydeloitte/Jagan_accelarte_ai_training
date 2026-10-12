"""Tests for user management and multi-user support."""

import sys
from pathlib import Path
import json
import tempfile
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.user_manager import (
    UserManager,
    UserSession,
    RunRecord,
    get_user_manager,
)


class TestUserSession:
    """Test UserSession dataclass."""
    
    def test_create_session(self):
        """Test creating a user session."""
        session = UserSession(
            username="alice",
            session_id="sess-001",
            started_at="2024-01-01T00:00:00Z",
            last_activity="2024-01-01T00:05:00Z",
        )
        
        assert session.username == "alice"
        assert session.session_id == "sess-001"
    
    def test_session_to_dict(self):
        """Test converting session to dictionary."""
        session = UserSession(
            username="bob",
            session_id="sess-002",
            started_at="2024-01-01T00:00:00Z",
            last_activity="2024-01-01T00:05:00Z",
            current_run_id="run-001",
        )
        
        session_dict = session.to_dict()
        
        assert session_dict["username"] == "bob"
        assert session_dict["current_run_id"] == "run-001"


class TestRunRecord:
    """Test RunRecord dataclass."""
    
    def test_create_run_record(self):
        """Test creating a run record."""
        record = RunRecord(
            run_id="run-001",
            username="alice",
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T01:00:00Z",
            status="completed",
            phase="report",
            input_files=["file1.csv"],
            output_files=["report.html"],
            quality_score=95.0,
        )
        
        assert record.run_id == "run-001"
        assert record.status == "completed"
        assert record.quality_score == 95.0
    
    def test_run_record_to_dict(self):
        """Test converting run record to dictionary."""
        record = RunRecord(
            run_id="run-002",
            username="bob",
            started_at="2024-01-01T00:00:00Z",
            completed_at=None,
            status="running",
            phase="silver",
            input_files=["file1.csv"],
            output_files=[],
            quality_score=None,
        )
        
        record_dict = record.to_dict()
        
        assert isinstance(record_dict, dict)
        assert record_dict["run_id"] == "run-002"
        assert record_dict["status"] == "running"


class TestUserManagerInit:
    """Test UserManager initialization."""
    
    def test_init_creates_users_dir(self):
        """Test that initialization creates users directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock BASE_DIR
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                
                assert manager.users_dir.exists()
                assert manager.users_file.exists()
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_init_creates_users_file(self):
        """Test that users.json is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                
                assert manager.users_file.exists()
                
                # Verify it's valid JSON
                data = json.loads(manager.users_file.read_text())
                assert "users" in data
            
            finally:
                core.user_manager.BASE_DIR = original_base


class TestUserRegistration:
    """Test user registration."""
    
    def test_register_valid_user(self):
        """Test registering a valid user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                
                result = manager.register_user("alice")
                
                assert result is True
                assert manager.user_exists("alice")
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_register_creates_user_directories(self):
        """Test that registration creates user directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("bob")
                
                user_dir = manager.get_user_dir("bob")
                
                assert user_dir.exists()
                assert (user_dir / "data").exists()
                assert (user_dir / "data" / "landing").exists()
                assert (user_dir / "data" / "bronze_layer").exists()
                assert (user_dir / "data" / "silver_layer").exists()
                assert (user_dir / "data" / "gold_layer").exists()
                assert (user_dir / "reports").exists()
                assert (user_dir / "audit_logs").exists()
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_register_duplicate_user(self):
        """Test registering the same user twice."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                
                result1 = manager.register_user("charlie")
                result2 = manager.register_user("charlie")
                
                assert result1 is True
                assert result2 is True  # Still returns True
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_invalid_username_too_short(self):
        """Test that short usernames are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                
                result = manager.register_user("ab")  # Too short
                
                assert result is False
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_invalid_username_special_chars(self):
        """Test that usernames with special characters are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                
                result = manager.register_user("user@123")  # Invalid chars
                
                assert result is False
            
            finally:
                core.user_manager.BASE_DIR = original_base


class TestUserPaths:
    """Test user path management."""
    
    def test_get_user_dir(self):
        """Test getting user directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("diana")
                
                user_dir = manager.get_user_dir("diana")
                
                assert user_dir.name == "diana"
                assert user_dir.exists()
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_get_user_data_dir(self):
        """Test getting user data directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("eve")
                
                data_dir = manager.get_user_data_dir("eve")
                
                assert data_dir.name == "data"
                assert data_dir.exists()
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_get_paths_for_user(self):
        """Test getting all paths for a user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("frank")
                
                paths = manager.get_paths_for_user("frank")
                
                assert "base" in paths
                assert "landing" in paths
                assert "bronze" in paths
                assert "silver" in paths
                assert "gold" in paths
                assert "reports" in paths
            
            finally:
                core.user_manager.BASE_DIR = original_base


class TestRunRecording:
    """Test run recording functionality."""
    
    def test_record_run_start(self):
        """Test recording run start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("grace")
                
                manager.record_run_start("grace", "run-001", ["file1.csv"])
                
                run = manager.get_user_run("grace", "run-001")
                
                assert run is not None
                assert run.run_id == "run-001"
                assert run.status == "running"
                assert run.input_files == ["file1.csv"]
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_record_run_progress(self):
        """Test recording run progress."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("henry")
                
                manager.record_run_start("henry", "run-002", ["file1.csv"])
                manager.record_run_progress(
                    "henry",
                    "run-002",
                    "silver",
                    ["bronze.parquet"],
                    quality_score=90.0,
                )
                
                run = manager.get_user_run("henry", "run-002")
                
                assert run.phase == "silver"
                assert run.quality_score == 90.0
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_record_run_complete(self):
        """Test recording run completion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("iris")
                
                manager.record_run_start("iris", "run-003", ["file1.csv"])
                manager.record_run_complete(
                    "iris",
                    "run-003",
                    ["report.html"],
                    95.0,
                )
                
                run = manager.get_user_run("iris", "run-003")
                
                assert run.status == "completed"
                assert run.completed_at is not None
                assert run.quality_score == 95.0
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_record_run_failed(self):
        """Test recording run failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("jack")
                
                manager.record_run_start("jack", "run-004", ["file1.csv"])
                manager.record_run_failed(
                    "jack",
                    "run-004",
                    "bronze",
                    "Data validation failed",
                )
                
                run = manager.get_user_run("jack", "run-004")
                
                assert run.status == "failed"
                assert run.phase == "bronze"
                assert run.error_message == "Data validation failed"
            
            finally:
                core.user_manager.BASE_DIR = original_base


class TestRunHistory:
    """Test run history queries."""
    
    def test_get_user_runs(self):
        """Test getting all runs for a user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("kate")
                
                # Create multiple runs
                for i in range(3):
                    manager.record_run_start("kate", f"run-{i:03d}", ["file.csv"])
                
                runs = manager.get_user_runs("kate")
                
                assert len(runs) == 3
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_get_user_runs_with_limit(self):
        """Test getting limited runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("leo")
                
                # Create multiple runs
                for i in range(5):
                    manager.record_run_start("leo", f"run-{i:03d}", ["file.csv"])
                
                runs = manager.get_user_runs("leo", limit=2)
                
                assert len(runs) == 2
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_get_user_runs_by_status(self):
        """Test filtering runs by status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("mike")
                
                manager.record_run_start("mike", "run-001", ["file.csv"])
                manager.record_run_complete("mike", "run-001", ["report.html"], 95.0)
                
                manager.record_run_start("mike", "run-002", ["file.csv"])
                manager.record_run_failed("mike", "run-002", "bronze", "Error")
                
                completed_runs = manager.get_user_runs("mike", status_filter="completed")
                failed_runs = manager.get_user_runs("mike", status_filter="failed")
                
                assert len(completed_runs) == 1
                assert len(failed_runs) == 1
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_get_specific_run(self):
        """Test getting a specific run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("nancy")
                
                manager.record_run_start("nancy", "run-special", ["file.csv"])
                
                run = manager.get_user_run("nancy", "run-special")
                
                assert run is not None
                assert run.run_id == "run-special"
            
            finally:
                core.user_manager.BASE_DIR = original_base


class TestUserStats:
    """Test user statistics."""
    
    def test_get_user_stats(self):
        """Test getting user statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                manager.register_user("oscar")
                
                # Create some runs
                manager.record_run_start("oscar", "run-001", ["file.csv"])
                manager.record_run_complete("oscar", "run-001", ["report.html"], 95.0)
                
                manager.record_run_start("oscar", "run-002", ["file.csv"])
                manager.record_run_complete("oscar", "run-002", ["report.html"], 85.0)
                
                manager.record_run_start("oscar", "run-003", ["file.csv"])
                manager.record_run_failed("oscar", "run-003", "bronze", "Error")
                
                stats = manager.get_user_stats("oscar")
                
                assert stats["total_runs"] == 3
                assert stats["completed"] == 2
                assert stats["failed"] == 1
                assert stats["avg_quality_score"] == 90.0
            
            finally:
                core.user_manager.BASE_DIR = original_base


class TestGetAllUsers:
    """Test getting all users."""
    
    def test_get_all_users_empty(self):
        """Test getting users when none registered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                users = manager.get_all_users()
                
                assert users == []
            
            finally:
                core.user_manager.BASE_DIR = original_base
    
    def test_get_all_users_multiple(self):
        """Test getting multiple users."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import core.user_manager
            original_base = core.user_manager.BASE_DIR
            core.user_manager.BASE_DIR = Path(tmpdir)
            
            try:
                manager = UserManager()
                
                manager.register_user("alice")
                manager.register_user("bob")
                manager.register_user("charlie")
                
                users = manager.get_all_users()
                
                assert len(users) == 3
                assert "alice" in users
                assert "bob" in users
                assert "charlie" in users
            
            finally:
                core.user_manager.BASE_DIR = original_base


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
