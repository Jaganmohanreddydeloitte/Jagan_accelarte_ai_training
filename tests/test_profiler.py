"""
Tests for agents.profiler module.

TEST STRATEGY:
- Test the profiler agent's ability to analyze CSV files and generate profiles
- Mock the LLM to avoid API calls
- Verify JSON output structure and content validation
- Test single and multiple file profiling
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from agents.profiler import profile_dataset, profile_multiple_datasets, _inspect_files, _compute_stats
from core.config import PROFILES_DIR


# ─── Helper Functions ───────────────────────────────────────────────────────

def _make_test_csv(tmp_path, filename, rows=5, include_nulls=False):
    """Create a test CSV file with mixed data types and quality issues."""
    data = {
        "customer_id": [1001, 1002, 1003, 1004, 1005][:rows],
        "name": ["Alice Johnson", "Bob Smith", "Charlie Brown", "Diana Prince", "Eve Wilson"][:rows],
        "age": [25, 32, 28, 45, 31][:rows],
        "salary": [50000.0, 75000.0, 65000.0, 95000.0, 70000.0][:rows],
        "join_date": ["2020-01-15", "2019-06-20", "2021-03-10", "2018-11-05", "2022-02-28"][:rows],
        "department": ["Sales", "Engineering", "Sales", "Management", "HR"][:rows],
    }

    if include_nulls:
        # Add some NaN values
        data["age"][1] = None
        data["salary"][3] = None

    df = pd.DataFrame(data)
    csv_path = tmp_path / filename
    df.to_csv(csv_path, index=False)
    return str(csv_path)


# ─── Test Classes ───────────────────────────────────────────────────────────

class TestInspectFiles:
    """Tests for the _inspect_files helper function."""

    def test_inspect_single_file(self, tmp_path):
        """Test that _inspect_files correctly inspects a CSV file."""
        # Arrange
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=3)

        # Act
        result = _inspect_files([csv_path])

        # Assert
        assert csv_path in result
        assert result[csv_path]["shape"] == (3, 6)  # 3 rows, 6 columns
        assert "customer_id" in result[csv_path]["columns"]
        assert result[csv_path]["sample_values"]["name"][0] == "Alice Johnson"

    def test_inspect_multiple_files(self, tmp_path):
        """Test that _inspect_files inspects multiple files."""
        # Arrange
        csv_path1 = _make_test_csv(tmp_path, "customers1.csv", rows=2)
        csv_path2 = _make_test_csv(tmp_path, "customers2.csv", rows=3)

        # Act
        result = _inspect_files([csv_path1, csv_path2])

        # Assert
        assert len(result) == 2
        assert result[csv_path1]["shape"] == (2, 6)
        assert result[csv_path2]["shape"] == (3, 6)

    def test_inspect_nonexistent_file(self, tmp_path):
        """Test that _inspect_files handles nonexistent files gracefully."""
        # Arrange
        nonexistent = str(tmp_path / "nonexistent.csv")

        # Act
        result = _inspect_files([nonexistent])

        # Assert
        assert "error" in result[nonexistent]


class TestComputeStats:
    """Tests for the _compute_stats helper function."""

    def test_compute_stats_basic(self, tmp_path):
        """Test that _compute_stats computes correct statistics."""
        # Arrange
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=5)

        # Act
        result = _compute_stats([csv_path])

        # Assert
        assert csv_path in result
        assert "customer_id" in result[csv_path]
        assert result[csv_path]["customer_id"]["dtype"] == "int64"
        assert result[csv_path]["customer_id"]["unique_count"] == 5
        assert result[csv_path]["customer_id"]["null_count"] == 0

    def test_compute_stats_numeric_columns(self, tmp_path):
        """Test that numeric column statistics are computed."""
        # Arrange
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=5)

        # Act
        result = _compute_stats([csv_path])

        # Assert
        salary_stats = result[csv_path]["salary"]
        assert "min" in salary_stats
        assert "max" in salary_stats
        assert "mean" in salary_stats
        assert salary_stats["min"] == 50000.0
        assert salary_stats["max"] == 95000.0

    def test_compute_stats_with_nulls(self, tmp_path):
        """Test that null statistics are computed correctly."""
        # Arrange
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=5, include_nulls=True)

        # Act
        result = _compute_stats([csv_path])

        # Assert
        age_stats = result[csv_path]["age"]
        assert age_stats["null_count"] == 1
        assert age_stats["null_pct"] == 20.0

    def test_compute_stats_string_columns(self, tmp_path):
        """Test that string columns are handled correctly."""
        # Arrange
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=5)

        # Act
        result = _compute_stats([csv_path])

        # Assert
        name_stats = result[csv_path]["name"]
        assert name_stats["unique_count"] == 5
        assert "sample_values" in name_stats
        assert len(name_stats["sample_values"]) > 0


class TestProfiler:
    """Tests for the profiler agent's profile_dataset and profile_multiple_datasets functions."""

    @patch("agents.profiler.AuditLogger")
    @patch("agents.profiler.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_profile_dataset_creates_json(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that profile_dataset creates a JSON profile file."""
        # Arrange
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=3)
        run_id = "test-run-prof-001"

        # Mock the agent
        profile_response = {
            "semantic_meanings": {
                "customer_id": "unique identifier",
                "name": "customer name",
                "age": "age in years",
            },
            "join_keys": ["customer_id"],
            "quality_notes": {
                "customer_id": "no nulls, unique values",
                "name": "no nulls",
            },
            "overall_quality_score": 95,
        }
        
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(type="human"),
                Mock(
                    type="ai",
                    content=json.dumps(profile_response)
                ),
            ]
        }
        mock_create_agent.return_value = mock_agent

        # Mock trace
        mock_trace_instance = Mock()
        mock_trace_instance.set_input.return_value = mock_trace_instance
        mock_trace_instance.set_plan.return_value = mock_trace_instance
        mock_trace_instance.set_output.return_value = mock_trace_instance
        mock_trace.return_value = mock_trace_instance

        # Mock audit logger
        mock_audit_instance = Mock()
        mock_audit.return_value = mock_audit_instance

        # Act
        result_path = profile_dataset(csv_path, run_id)

        # Assert
        assert result_path is not None
        assert Path(result_path).exists(), "Profile file should be created"
        assert result_path.endswith(".json"), "Result should be JSON file"

        # Verify JSON content
        with open(result_path, "r") as f:
            profile_data = json.load(f)

        assert "run_id" in profile_data
        assert profile_data["run_id"] == run_id
        assert "files" in profile_data
        assert csv_path in profile_data["files"]
        assert "timestamp" in profile_data
        assert "profile" in profile_data

    @patch("agents.profiler.AuditLogger")
    @patch("agents.profiler.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_profile_multiple_datasets(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that profile_multiple_datasets handles multiple CSV files."""
        # Arrange
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        csv_path1 = _make_test_csv(tmp_path, "customers1.csv", rows=2)
        csv_path2 = _make_test_csv(tmp_path, "customers2.csv", rows=3)
        run_id = "test-run-prof-002"

        # Mock the agent
        profile_response = {
            "semantic_meanings": {"customer_id": "id", "name": "name"},
            "join_keys": ["customer_id"],
            "quality_notes": {"customer_id": "unique"},
            "overall_quality_score": 90,
        }
        
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(type="human"),
                Mock(type="ai", content=json.dumps(profile_response)),
            ]
        }
        mock_create_agent.return_value = mock_agent

        # Mock trace
        mock_trace_instance = Mock()
        mock_trace_instance.set_input.return_value = mock_trace_instance
        mock_trace_instance.set_plan.return_value = mock_trace_instance
        mock_trace_instance.set_output.return_value = mock_trace_instance
        mock_trace.return_value = mock_trace_instance

        # Mock audit logger
        mock_audit_instance = Mock()
        mock_audit.return_value = mock_audit_instance

        # Act
        result_path = profile_multiple_datasets([csv_path1, csv_path2], run_id)

        # Assert
        assert result_path is not None
        assert Path(result_path).exists()

        # Verify both files are in profile
        with open(result_path, "r") as f:
            profile_data = json.load(f)

        assert len(profile_data["files"]) == 2
        assert csv_path1 in profile_data["files"]
        assert csv_path2 in profile_data["files"]

    @patch("agents.profiler.AuditLogger")
    @patch("agents.profiler.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_profile_creates_trace(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that profiling creates an AgentTrace for observability."""
        # Arrange
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=2)
        run_id = "test-run-prof-003"

        # Mock the agent
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(type="human"),
                Mock(type="ai", content='{"quality_score": 90}'),
            ]
        }
        mock_create_agent.return_value = mock_agent

        # Mock trace
        mock_trace_instance = Mock()
        mock_trace_instance.set_input.return_value = mock_trace_instance
        mock_trace_instance.set_plan.return_value = mock_trace_instance
        mock_trace_instance.set_output.return_value = mock_trace_instance
        mock_trace.return_value = mock_trace_instance

        # Mock audit logger
        mock_audit_instance = Mock()
        mock_audit.return_value = mock_audit_instance

        # Act
        profile_dataset(csv_path, run_id)

        # Assert
        mock_trace.assert_called_with("profiler", run_id)
        mock_trace_instance.set_input.assert_called()
        mock_trace_instance.set_plan.assert_called()
        mock_trace_instance.set_output.assert_called()
        mock_trace_instance.complete.assert_called()

    @patch("agents.profiler.AuditLogger")
    @patch("agents.profiler.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_profile_logs_on_start(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that profiling completes successfully."""
        # Arrange
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=2)
        run_id = "test-run-prof-004"

        # Mock the agent
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(type="human"),
                Mock(type="ai", content="{}"),
            ]
        }
        mock_create_agent.return_value = mock_agent

        # Mock trace
        mock_trace_instance = Mock()
        mock_trace_instance.set_input.return_value = mock_trace_instance
        mock_trace_instance.set_plan.return_value = mock_trace_instance
        mock_trace_instance.set_output.return_value = mock_trace_instance
        mock_trace.return_value = mock_trace_instance

        # Mock audit logger
        mock_audit_instance = Mock()
        mock_audit.return_value = mock_audit_instance

        # Act
        result_path = profile_dataset(csv_path, run_id)

        # Assert
        # Trace should be called for observability
        mock_trace.assert_called_with("profiler", run_id)
        assert result_path is not None
        assert Path(result_path).exists()

    @patch("agents.profiler.AuditLogger")
    @patch("agents.profiler.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_profile_json_has_correct_shape(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that the generated profile JSON has the expected structure."""
        # Arrange
        monkeypatch.setattr("agents.profiler.PROFILES_DIR", tmp_path)
        csv_path = _make_test_csv(tmp_path, "customers.csv", rows=3)
        run_id = "test-run-prof-005"
        task_description = "Profile customer data"

        # Mock the agent
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(type="human"),
                Mock(type="ai", content='{"analysis": "complete"}'),
            ]
        }
        mock_create_agent.return_value = mock_agent

        # Mock trace
        mock_trace_instance = Mock()
        mock_trace_instance.set_input.return_value = mock_trace_instance
        mock_trace_instance.set_plan.return_value = mock_trace_instance
        mock_trace_instance.set_output.return_value = mock_trace_instance
        mock_trace.return_value = mock_trace_instance

        # Mock audit logger
        mock_audit_instance = Mock()
        mock_audit.return_value = mock_audit_instance

        # Act
        result_path = profile_dataset(csv_path, run_id, task_description)

        # Assert
        with open(result_path, "r") as f:
            profile_data = json.load(f)

        # Verify required fields
        required_fields = ["run_id", "timestamp", "files", "task_description", "profile"]
        for field in required_fields:
            assert field in profile_data, f"Profile should contain '{field}' field"

        assert profile_data["run_id"] == run_id
        assert profile_data["task_description"] == task_description
        assert isinstance(profile_data["files"], list)
