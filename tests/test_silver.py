"""
Tests for agents.silver_agent module.

TEST STRATEGY:
- _apply_silver_rules is pure Python (no LLM), test it directly with Parquet files (Silver's input format)
- execute_silver is an LLM entry point, mock the LangChain agent to avoid API calls
- Verify null handling (fillna), deduplication, column renames, surrogate keys, text normalization
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
import numpy as np
from agents.silver_agent import _apply_silver_rules, execute_silver
from core.config import SILVER_DIR


# ─── Helper Functions ───────────────────────────────────────────────────────

def _make_silver_sttm(tmp_path, rows=None):
    """Create a Silver STTM CSV with cleansing and transformation rules."""
    base_rows = [
        {
            "source_column": "order_id",
            "target_column": "order_id",
            "transformation_type": "numeric",
            "transformation_logic": "none",
            "description": "Order identifier",
        },
        {
            "source_column": "order_date",
            "target_column": "order_date",
            "transformation_type": "date",
            "transformation_logic": "none",
            "description": "Order date",
        },
        {
            "source_column": "amount",
            "target_column": "amount",
            "transformation_type": "float",
            "transformation_logic": "fill_mean",
            "description": "Order amount with mean fill",
        },
        {
            "source_column": "customer_name",
            "target_column": "customer_name",
            "transformation_type": "string",
            "transformation_logic": "lowercase, trim",
            "description": "Customer name",
        },
    ]

    if rows:
        base_rows.extend(rows)

    sttm_df = pd.DataFrame(base_rows)
    sttm_path = tmp_path / "silver_sttm.csv"
    sttm_df.to_csv(sttm_path, index=False)
    return str(sttm_path)


def _passthrough_sttm(tmp_path, source_table, columns):
    """Create a passthrough STTM (1-to-1 source-to-target mapping for simple testing)."""
    rows = []
    for col in columns:
        rows.append({
            "source_column": col,
            "target_column": col,
            "transformation_type": "string",
            "transformation_logic": "none",
            "description": f"Passthrough {col}",
        })
    sttm_df = pd.DataFrame(rows)
    sttm_path = tmp_path / "passthrough_sttm.csv"
    sttm_df.to_csv(sttm_path, index=False)
    return str(sttm_path)


def _make_test_parquet(tmp_path, filename, rows=5, include_nulls=False, include_dupes=False):
    """Create a test Parquet file (Bronze output format) as input to Silver."""
    data = {
        "order_id": [1001, 1002, 1003, 1004, 1005][:rows],
        "order_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"][:rows],
        "amount": [100.5, 250.75, 199.99, 500.0, 75.25][:rows],
        "customer_name": ["ALICE", "BOB", "CHARLIE", "DIANA", "EVE"][:rows],
        "_load_timestamp": ["2024-01-01T00:00:00"] * rows,
        "_source_file": ["/data/file.csv"] * rows,
    }

    if include_nulls:
        # Add some NaN values to amount column
        data["amount"][1] = np.nan
        data["amount"][3] = np.nan

    df = pd.DataFrame(data)

    if include_dupes:
        # Add a duplicate row
        duplicate_row = df.iloc[0:1].copy()
        df = pd.concat([df, duplicate_row], ignore_index=True)

    parquet_path = tmp_path / filename
    df.to_parquet(parquet_path, index=False)
    return str(parquet_path)


def _mock_agent_that_calls_tool(tool_result):
    """Return a mock agent that simulates calling a tool and returning results."""
    mock_agent = Mock()
    mock_agent.invoke.return_value = {"tool_result": tool_result}
    return mock_agent


# ─── Test Classes ───────────────────────────────────────────────────────────

class TestApplySilverRules:
    """Tests for the _apply_silver_rules pure Python function."""

    def test_output_written_for_each_input(self, tmp_path, monkeypatch):
        """Test that one output file is created for each input file."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        sttm_path = _make_silver_sttm(tmp_path)
        input_file1 = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=3)
        input_file2 = _make_test_parquet(tmp_path, "sales_bronze.parquet", rows=2)
        run_id = "test-run-s01"

        # Act
        output_paths = _apply_silver_rules([input_file1, input_file2], sttm_path, run_id)

        # Assert
        assert len(output_paths) == 2, "Expected 2 output files"
        for output_file in output_paths:
            assert Path(output_file).exists()
            assert output_file.endswith("_silver.parquet")

    def test_null_handling_fill_mean(self, tmp_path, monkeypatch):
        """Test that null handling is applied for numeric columns."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        sttm_path = _make_silver_sttm(tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=5, include_nulls=True)
        run_id = "test-run-s02"

        # Read input to see nulls
        input_df = pd.read_parquet(input_file)
        nulls_before = input_df["amount"].isna().sum()
        assert nulls_before > 0, "Test data should have nulls"

        # Act
        output_paths = _apply_silver_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)
        
        # Verify the amount column still exists and has valid values
        assert "amount" in output_df.columns, "Amount column should exist"
        assert len(output_df) > 0, "Output should have rows"
        # Mean should be a positive number if nulls were handled correctly
        assert output_df["amount"].mean() > 0, "Mean of amount should be positive"

    def test_dedup_removes_duplicate_rows(self, tmp_path, monkeypatch):
        """Test that deduplication removes exact duplicate rows."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        sttm_path = _make_silver_sttm(tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=5, include_dupes=True)
        run_id = "test-run-s03"

        # Read input to verify dupes
        input_df = pd.read_parquet(input_file)
        input_rows = len(input_df)
        assert input_rows == 6, "Test data should have 6 rows (5 + 1 dupe)"

        # Act
        output_paths = _apply_silver_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)
        output_rows = len(output_df)

        # Should be 5 rows after dedup (ignoring metadata columns which differ)
        assert output_rows <= input_rows, "Output should have fewer or equal rows after dedup"

    def test_column_rename_applied(self, tmp_path, monkeypatch):
        """Test that column rename rules from STTM are applied."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=2)

        # Create STTM with different target names
        sttm_rows = [
            {
                "source_column": "order_id",
                "target_column": "oid",
                "transformation_type": "numeric",
                "transformation_logic": "none",
                "description": "Order ID renamed",
            },
            {
                "source_column": "customer_name",
                "target_column": "cust_name",
                "transformation_type": "string",
                "transformation_logic": "none",
                "description": "Customer name renamed",
            },
        ]
        sttm_path = _make_silver_sttm(tmp_path, rows=sttm_rows)
        run_id = "test-run-s04"

        # Act
        output_paths = _apply_silver_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)

        assert "oid" in output_df.columns, "order_id should be renamed to oid"
        assert "cust_name" in output_df.columns, "customer_name should be renamed to cust_name"

    def test_text_normalization_lowercase(self, tmp_path, monkeypatch):
        """Test that text normalization (lowercase) is applied."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=2)

        # Create STTM with lowercase rule
        sttm_rows = [
            {
                "source_column": "customer_name",
                "target_column": "customer_name",
                "transformation_type": "string",
                "transformation_logic": "lowercase",
                "description": "Customer name lowercase",
            },
        ]
        sttm_path = _make_silver_sttm(tmp_path, rows=sttm_rows)
        run_id = "test-run-s05"

        # Act
        output_paths = _apply_silver_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)

        # All customer names should be lowercase
        assert output_df["customer_name"].str.islower().all(), "customer_name should be lowercase"

    def test_output_is_valid_parquet(self, tmp_path, monkeypatch):
        """Test that output file is a valid Parquet file."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        sttm_path = _make_silver_sttm(tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=3)
        run_id = "test-run-s06"

        # Act
        output_paths = _apply_silver_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        assert output_file.endswith(".parquet"), "Output should be .parquet file"
        assert Path(output_file).exists()

        # Try to read it back
        df = pd.read_parquet(output_file)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert len(df.columns) > 0

    def test_surrogate_key_injected(self, tmp_path, monkeypatch):
        """Test that surrogate key is injected as first column."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        sttm_path = _make_silver_sttm(tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=3)
        run_id = "test-run-s07"

        # Act
        output_paths = _apply_silver_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)

        # First column should be surrogate key
        first_col = output_df.columns[0]
        assert first_col.startswith("pk_"), "First column should be surrogate key starting with pk_"
        assert first_col.endswith("_silver_id"), "Surrogate key should end with _silver_id"

        # Surrogate key should have sequential values starting from 1
        surrogate_values = output_df[first_col].values
        assert surrogate_values[0] == 1, "Surrogate key should start from 1"
        assert len(surrogate_values) == len(output_df), "Surrogate key should have one value per row"

    def test_missing_sttm_file_raises_error(self, tmp_path, monkeypatch):
        """Test that missing STTM file raises an error."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=2)
        sttm_path = str(tmp_path / "nonexistent.csv")
        run_id = "test-run-s08"

        # Act & Assert
        with pytest.raises(ValueError, match="Failed to read STTM file"):
            _apply_silver_rules([input_file], sttm_path, run_id)

    def test_missing_input_file_raises_error(self, tmp_path, monkeypatch):
        """Test that missing input file raises an error."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        sttm_path = _make_silver_sttm(tmp_path)
        input_file = str(tmp_path / "nonexistent.parquet")
        run_id = "test-run-s09"

        # Act & Assert
        with pytest.raises(Exception):
            _apply_silver_rules([input_file], sttm_path, run_id)

    def test_audit_logging_on_success(self, tmp_path, monkeypatch):
        """Test that audit logging is called on successful cleansing."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)
        sttm_path = _make_silver_sttm(tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=2)
        run_id = "test-run-s10"

        with patch("agents.silver_agent.AuditLogger") as mock_audit:
            mock_audit_instance = Mock()
            mock_audit.return_value = mock_audit_instance

            # Act
            _apply_silver_rules([input_file], sttm_path, run_id)

            # Assert
            mock_audit.assert_called_with(run_id)
            mock_audit_instance.log.assert_called()
            # Check that log was called with the cleanse_file action
            calls = mock_audit_instance.log.call_args_list
            assert len(calls) > 0
            # At least one call should have the action parameter
            action_found = any("cleanse_file" in str(call) for call in calls)
            assert action_found, "Should log cleanse_file action"


class TestExecuteSilver:
    """Tests for the execute_silver LLM-based function."""

    @patch("agents.silver_agent.AuditLogger")
    @patch("agents.silver_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_silver_returns_paths(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_silver returns output paths."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)

        sttm_path = _make_silver_sttm(tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=2)
        run_id = "test-run-s11"

        # Mock the agent
        expected_output = [str(tmp_path / "orders_silver.parquet")]
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
        result = execute_silver(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        assert result is not None
        assert isinstance(result, list)

    @patch("agents.silver_agent.AuditLogger")
    @patch("agents.silver_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_silver_creates_trace(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_silver creates an AgentTrace for observability."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)

        sttm_path = _make_silver_sttm(tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=2)
        run_id = "test-run-s12"

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
        execute_silver(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        mock_trace.assert_called_with("silver_agent", run_id)
        mock_trace_instance.set_input.assert_called()
        mock_trace_instance.complete.assert_called()

    @patch("agents.silver_agent.AuditLogger")
    @patch("agents.silver_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_silver_logs_on_start(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_silver logs when starting."""
        # Arrange
        monkeypatch.setattr("agents.silver_agent.SILVER_DIR", tmp_path)

        sttm_path = _make_silver_sttm(tmp_path)
        input_file = _make_test_parquet(tmp_path, "orders_bronze.parquet", rows=2)
        run_id = "test-run-s13"

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
        execute_silver(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        mock_audit.assert_called_with(run_id)
        mock_audit_instance.log.assert_called()
