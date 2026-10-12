"""
Tests for agents.bronze_agent module.

TEST STRATEGY:
- _apply_bronze_rules is pure Python (no LLM), test it directly with real CSV/Parquet files
- execute_bronze is an LLM entry point, mock the LangChain agent to avoid API calls
- Use temporary directories and monkeypatch to isolate tests from real filesystem
- Verify metadata columns, row preservation, column renames, and output format
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from agents.bronze_agent import _apply_bronze_rules, execute_bronze
from core.config import BRONZE_DIR


# ─── Helper Functions ───────────────────────────────────────────────────────

def _make_sttm_csv(tmp_path, extra_rows=None):
    """Create a Bronze STTM CSV with basic column rename and type cast rules."""
    base_rows = [
        {
            "source_column": "OrderID",
            "target_column": "order_id",
            "transformation_type": "numeric",
            "description": "Unique order identifier",
        },
        {
            "source_column": "OrderDate",
            "target_column": "order_date",
            "transformation_type": "date",
            "description": "Date of order",
        },
        {
            "source_column": "Amount",
            "target_column": "amount",
            "transformation_type": "float",
            "description": "Order amount",
        },
        {
            "source_column": "CustomerName",
            "target_column": "customer_name",
            "transformation_type": "string",
            "description": "Name of customer",
        },
    ]

    if extra_rows:
        base_rows.extend(extra_rows)

    sttm_df = pd.DataFrame(base_rows)
    sttm_path = tmp_path / "bronze_sttm.csv"
    sttm_df.to_csv(sttm_path, index=False)
    return str(sttm_path)


def _make_test_csv(tmp_path, filename, rows=5):
    """Create a test CSV file with sample data."""
    data = {
        "OrderID": ["1001", "1002", "1003", "1004", "1005"][:rows],
        "OrderDate": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"][:rows],
        "Amount": ["100.50", "250.75", "199.99", "500.00", "75.25"][:rows],
        "CustomerName": ["Alice", "Bob", "Charlie", "Diana", "Eve"][:rows],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / filename
    df.to_csv(csv_path, index=False)
    return str(csv_path)


def _mock_agent_that_calls_tool(tool_result):
    """Return a mock agent that simulates calling a tool and returning results."""
    mock_agent = Mock()
    mock_agent.invoke.return_value = {"tool_result": tool_result}
    return mock_agent


# ─── Test Classes ───────────────────────────────────────────────────────────

class TestApplyBronzeRules:
    """Tests for the _apply_bronze_rules pure Python function."""

    def test_metadata_columns_added(self, tmp_path, monkeypatch):
        """Test that _load_timestamp and _source_file metadata columns are added."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=3)
        run_id = "test-run-001"

        # Act
        output_paths = _apply_bronze_rules([input_file], sttm_path, run_id)

        # Assert
        assert len(output_paths) == 1
        output_file = output_paths[0]
        assert output_file.endswith(".parquet")

        df = pd.read_parquet(output_file)
        assert "_load_timestamp" in df.columns, "Missing _load_timestamp column"
        assert "_source_file" in df.columns, "Missing _source_file column"
        assert df["_load_timestamp"].iloc[0] is not None
        assert str(input_file) in df["_source_file"].iloc[0]

    def test_row_count_preserved(self, tmp_path, monkeypatch):
        """Test that the number of rows is preserved during ingestion."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=5)
        run_id = "test-run-002"

        # Read input row count
        input_df = pd.read_csv(input_file)
        input_rows = len(input_df)

        # Act
        output_paths = _apply_bronze_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)
        output_rows = len(output_df)

        assert output_rows == input_rows, f"Expected {input_rows} rows, got {output_rows}"

    def test_column_rename_applied(self, tmp_path, monkeypatch):
        """Test that column rename rules from STTM are applied correctly."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=2)
        run_id = "test-run-003"

        # Act
        output_paths = _apply_bronze_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        df = pd.read_parquet(output_file)

        # Check renamed columns exist
        assert "order_id" in df.columns, "Column OrderID not renamed to order_id"
        assert "order_date" in df.columns, "Column OrderDate not renamed to order_date"
        assert "amount" in df.columns, "Column Amount not renamed to amount"
        assert "customer_name" in df.columns, "Column CustomerName not renamed to customer_name"

        # Check original columns don't exist
        assert "OrderID" not in df.columns
        assert "OrderDate" not in df.columns

    def test_type_casting_applied(self, tmp_path, monkeypatch):
        """Test that transformation_type rules are applied (numeric, date, string)."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=2)
        run_id = "test-run-004"

        # Act
        output_paths = _apply_bronze_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        df = pd.read_parquet(output_file)

        # Check types
        assert pd.api.types.is_numeric_dtype(df["order_id"]), "order_id should be numeric"
        assert pd.api.types.is_datetime64_any_dtype(df["order_date"]), "order_date should be datetime"
        assert pd.api.types.is_numeric_dtype(df["amount"]), "amount should be numeric"
        # String columns might be object or string dtype in different pandas versions
        assert pd.api.types.is_object_dtype(df["customer_name"]) or pd.api.types.is_string_dtype(df["customer_name"]), "customer_name should be string"

    def test_multiple_files_produce_multiple_outputs(self, tmp_path, monkeypatch):
        """Test that multiple input files produce multiple output files."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        sttm_path = _make_sttm_csv(tmp_path)
        file1 = _make_test_csv(tmp_path, "orders_jan.csv", rows=2)
        file2 = _make_test_csv(tmp_path, "orders_feb.csv", rows=3)
        run_id = "test-run-005"

        # Act
        output_paths = _apply_bronze_rules([file1, file2], sttm_path, run_id)

        # Assert
        assert len(output_paths) == 2, "Expected 2 output files"
        for output_file in output_paths:
            assert Path(output_file).exists()
            df = pd.read_parquet(output_file)
            assert len(df) > 0

    def test_output_file_is_valid_parquet(self, tmp_path, monkeypatch):
        """Test that output file is a valid Parquet file."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=3)
        run_id = "test-run-006"

        # Act
        output_paths = _apply_bronze_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        assert output_file.endswith(".parquet"), "Output should be .parquet file"
        assert Path(output_file).exists()

        # Try to read it back
        df = pd.read_parquet(output_file)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert len(df.columns) > 0

    def test_missing_sttm_file_raises_error(self, tmp_path, monkeypatch):
        """Test that missing STTM file raises an error."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=2)
        sttm_path = str(tmp_path / "nonexistent.csv")
        run_id = "test-run-007"

        # Act & Assert
        with pytest.raises(ValueError, match="Failed to read STTM file"):
            _apply_bronze_rules([input_file], sttm_path, run_id)

    def test_missing_input_file_raises_error(self, tmp_path, monkeypatch):
        """Test that missing input file raises an error."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        sttm_path = _make_sttm_csv(tmp_path)
        input_file = str(tmp_path / "nonexistent.csv")
        run_id = "test-run-008"

        # Act & Assert
        with pytest.raises(Exception):
            _apply_bronze_rules([input_file], sttm_path, run_id)

    def test_output_filenames_match_input_stems(self, tmp_path, monkeypatch):
        """Test that output filenames are based on input file stems."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)
        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "my_orders.csv", rows=2)
        run_id = "test-run-009"

        # Act
        output_paths = _apply_bronze_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        assert "my_orders_bronze.parquet" in output_file


class TestExecuteBronze:
    """Tests for the execute_bronze LLM-based function."""

    @patch("agents.bronze_agent.AuditLogger")
    @patch("agents.bronze_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_bronze_returns_output_paths(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_bronze returns output paths from the agent."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)

        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=2)
        run_id = "test-run-010"

        # Mock the agent
        expected_output = [str(tmp_path / "orders_bronze.parquet")]
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(type="human"),
                Mock(
                    type="ai",
                    tool_calls=[],
                    content='{"output_paths": ["' + expected_output[0] + '"]}'
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
        result = execute_bronze(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        assert result is not None
        assert isinstance(result, list)

    @patch("agents.bronze_agent.AuditLogger")
    @patch("agents.bronze_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_bronze_creates_trace(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_bronze creates an AgentTrace for observability."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)

        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=2)
        run_id = "test-run-011"

        # Mock the agent
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(type="human"),
                Mock(type="ai", tool_calls=[], content="{}"),
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
        execute_bronze(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        mock_trace.assert_called_with("bronze_agent", run_id)
        mock_trace_instance.set_input.assert_called()
        mock_trace_instance.complete.assert_called()

    @patch("agents.bronze_agent.AuditLogger")
    @patch("agents.bronze_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_bronze_logs_on_start(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_bronze logs when starting."""
        # Arrange
        monkeypatch.setattr("agents.bronze_agent.BRONZE_DIR", tmp_path)

        sttm_path = _make_sttm_csv(tmp_path)
        input_file = _make_test_csv(tmp_path, "orders.csv", rows=2)
        run_id = "test-run-012"

        # Mock the agent
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(type="human"),
                Mock(type="ai", tool_calls=[], content="{}"),
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
        execute_bronze(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        mock_audit.assert_called_with(run_id)
        mock_audit_instance.log.assert_called()
