"""
Tests for core.audit module.

This module provides comprehensive testing for the AuditLogger class,
which handles JSONL-based audit logging for pipeline operations.
"""

import sys
import json
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from core.audit import AuditLogger
from core.config import AUDIT_DIR


class TestAuditLogger:
    """Tests for the AuditLogger class."""

    def test_log_creates_file(self, tmp_path, monkeypatch):
        """Test that logging creates a file with correct entry."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        run_id = "test-run-123"
        logger = AuditLogger(run_id)

        # Act
        logger.log(agent="test_agent", action="test_action", rationale="testing")

        # Assert
        expected_file = tmp_path / f"{run_id}.jsonl"
        assert expected_file.exists(), "Audit log file was not created"

        logs = logger.get_logs()
        assert len(logs) == 1, "Expected 1 log entry"
        assert logs[0]["agent"] == "test_agent"
        assert logs[0]["action"] == "test_action"
        assert logs[0]["run_id"] == run_id
        assert "timestamp" in logs[0]
        assert logs[0]["rationale"] == "testing"

    def test_multiple_logs_appended(self, tmp_path, monkeypatch):
        """Test that multiple logs are appended correctly."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        run_id = "test-run-456"
        logger = AuditLogger(run_id)

        # Act
        logger.log(agent="agent1", action="action1")
        logger.log(agent="agent2", action="action2", status="success")
        logger.log(agent="agent3", action="action3", phase="bronze")

        # Assert
        logs = logger.get_logs()
        assert len(logs) == 3, "Expected 3 log entries"

        # Verify each entry
        assert logs[0]["agent"] == "agent1"
        assert logs[1]["agent"] == "agent2"
        assert logs[1]["status"] == "success"
        assert logs[2]["agent"] == "agent3"
        assert logs[2]["phase"] == "bronze"

    def test_get_logs_empty_file(self, tmp_path, monkeypatch):
        """Test that get_logs() returns empty list for nonexistent run."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        run_id = "nonexistent-run"
        logger = AuditLogger(run_id)

        # Act
        logs = logger.get_logs()

        # Assert
        assert logs == [], "Expected empty list for nonexistent run"
        assert not (tmp_path / f"{run_id}.jsonl").exists()

    def test_log_with_arbitrary_kwargs(self, tmp_path, monkeypatch):
        """Test that arbitrary keyword arguments are stored in log."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        logger = AuditLogger("test-run")

        # Act
        logger.log(
            agent="profiler",
            action="profile_data",
            file_path="/data/sales.csv",
            rows=100,
            columns=5,
            quality_score=0.95,
        )

        # Assert
        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0]["file_path"] == "/data/sales.csv"
        assert logs[0]["rows"] == 100
        assert logs[0]["columns"] == 5
        assert logs[0]["quality_score"] == 0.95

    def test_log_timestamp_format(self, tmp_path, monkeypatch):
        """Test that timestamps are in UTC ISO format."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        logger = AuditLogger("test-run")

        # Act
        logger.log(agent="test", action="test_action")

        # Assert
        logs = logger.get_logs()
        timestamp = logs[0]["timestamp"]
        # Should be ISO format: YYYY-MM-DDTHH:MM:SS.XXXXXX+00:00
        assert "T" in timestamp, "Timestamp should be in ISO format"
        assert "+" in timestamp or "Z" in timestamp, "Timestamp should include timezone"

    def test_uuid_run_id_generation(self, tmp_path, monkeypatch):
        """Test that a unique run_id is generated when not provided."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)

        # Act
        logger1 = AuditLogger()
        logger2 = AuditLogger()

        # Assert
        assert logger1.run_id != logger2.run_id, "Generated run_ids should be unique"

    def test_log_file_path_construction(self, tmp_path, monkeypatch):
        """Test that log file path is constructed correctly."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        run_id = "test-run-789"
        logger = AuditLogger(run_id)

        # Act
        logger.log(agent="test", action="test_action")

        # Assert
        expected_path = tmp_path / f"{run_id}.jsonl"
        assert logger.log_file == expected_path
        assert expected_path.exists()

    def test_jsonl_format_validity(self, tmp_path, monkeypatch):
        """Test that the output is valid JSONL format."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        logger = AuditLogger("test-run")

        # Act
        logger.log(agent="agent1", action="action1")
        logger.log(agent="agent2", action="action2")

        # Assert - Read file directly and parse each line as JSON
        log_file = tmp_path / "test-run.jsonl"
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 2
            for line in lines:
                parsed = json.loads(line)
                assert "timestamp" in parsed
                assert "run_id" in parsed
                assert "agent" in parsed
                assert "action" in parsed

    def test_log_multiple_runs_separate_files(self, tmp_path, monkeypatch):
        """Test that different run_ids create separate log files."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        logger1 = AuditLogger("run-1")
        logger2 = AuditLogger("run-2")

        # Act
        logger1.log(agent="agent1", action="action1")
        logger2.log(agent="agent2", action="action2")

        # Assert
        file1 = tmp_path / "run-1.jsonl"
        file2 = tmp_path / "run-2.jsonl"
        assert file1.exists()
        assert file2.exists()

        logs1 = logger1.get_logs()
        logs2 = logger2.get_logs()
        assert logs1[0]["run_id"] == "run-1"
        assert logs2[0]["run_id"] == "run-2"

    def test_get_logs_preserves_data_types(self, tmp_path, monkeypatch):
        """Test that get_logs() preserves data types from JSON."""
        # Arrange
        monkeypatch.setattr("core.audit.AUDIT_DIR", tmp_path)
        logger = AuditLogger("test-run")

        # Act
        logger.log(
            agent="test",
            action="test",
            int_value=42,
            float_value=3.14,
            bool_value=True,
            list_value=[1, 2, 3],
            dict_value={"key": "value"},
        )

        # Assert
        logs = logger.get_logs()
        assert logs[0]["int_value"] == 42
        assert logs[0]["float_value"] == 3.14
        assert logs[0]["bool_value"] is True
        assert logs[0]["list_value"] == [1, 2, 3]
        assert logs[0]["dict_value"] == {"key": "value"}
