"""
Tests for agents.gold_agent module.

TEST STRATEGY:
- _apply_gold_rules is pure Python (no LLM), test it directly with Parquet files (Silver's output)
- execute_gold is an LLM entry point, mock the LangChain agent to avoid API calls
- Verify table creation, joins, column filtering, and surrogate key injection
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from agents.gold_agent import _apply_gold_rules, execute_gold
from core.config import GOLD_DIR


# ─── Helper Functions ───────────────────────────────────────────────────────

def _make_gold_sttm(tmp_path, rows=None):
    """Create a Gold STTM CSV with target_table grouping."""
    base_rows = [
        {
            "source_table": "orders",
            "source_column": "order_id",
            "target_table": "fact_orders",
            "target_column": "order_id",
            "transformation_type": "numeric",
            "transformation_logic": "none",
            "description": "Order identifier",
        },
        {
            "source_table": "orders",
            "source_column": "order_date",
            "target_table": "fact_orders",
            "target_column": "order_date",
            "transformation_type": "date",
            "transformation_logic": "none",
            "description": "Order date",
        },
        {
            "source_table": "orders",
            "source_column": "amount",
            "target_table": "fact_orders",
            "target_column": "amount",
            "transformation_type": "float",
            "transformation_logic": "none",
            "description": "Order amount",
        },
        {
            "source_table": "orders",
            "source_column": "customer_name",
            "target_table": "fact_orders",
            "target_column": "customer_name",
            "transformation_type": "string",
            "transformation_logic": "none",
            "description": "Customer name",
        },
    ]

    if rows:
        base_rows.extend(rows)

    sttm_df = pd.DataFrame(base_rows)
    sttm_path = tmp_path / "gold_sttm.csv"
    sttm_df.to_csv(sttm_path, index=False)
    return str(sttm_path)


def _passthrough_sttm(tmp_path, source_table, columns, target_table="analytics"):
    """Create a passthrough STTM (1-to-1 source-to-target mapping for simple testing)."""
    rows = []
    for col in columns:
        rows.append({
            "source_table": source_table,
            "source_column": col,
            "target_table": target_table,
            "target_column": col,
            "transformation_type": "string",
            "transformation_logic": "none",
            "description": f"Passthrough {col}",
        })
    sttm_df = pd.DataFrame(rows)
    sttm_path = tmp_path / "passthrough_sttm.csv"
    sttm_df.to_csv(sttm_path, index=False)
    return str(sttm_path)


def _make_test_silver_parquet(tmp_path, filename, rows=5):
    """Create a test Silver Parquet file (input to Gold)."""
    data = {
        "pk_orders_silver_id": range(1, rows + 1),
        "order_id": [1001 + i for i in range(rows)],
        "order_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"][:rows],
        "amount": [100.5, 250.75, 199.99, 500.0, 75.25][:rows],
        "customer_name": ["alice", "bob", "charlie", "diana", "eve"][:rows],
    }

    df = pd.DataFrame(data)
    parquet_path = tmp_path / filename
    df.to_parquet(parquet_path, index=False)
    return str(parquet_path)


def _mock_agent_that_calls_tool(tool_result):
    """Return a mock agent that simulates calling a tool and returning results."""
    mock_agent = Mock()
    mock_agent.invoke.return_value = {"tool_result": tool_result}
    return mock_agent


# ─── Test Classes ───────────────────────────────────────────────────────────

class TestApplyGoldRules:
    """Tests for the _apply_gold_rules pure Python function."""

    def test_output_written_for_each_target_table(self, tmp_path, monkeypatch):
        """Test that one output file is created for each target table in STTM."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)
        sttm_path = _make_gold_sttm(tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=3)
        run_id = "test-run-g01"

        # Act
        output_paths = _apply_gold_rules([input_file], sttm_path, run_id)

        # Assert
        assert len(output_paths) == 1, "Expected 1 output file (1 target table)"
        for output_file in output_paths:
            assert Path(output_file).exists()
            assert output_file.endswith(".parquet")

    def test_output_is_valid_parquet(self, tmp_path, monkeypatch):
        """Test that output file is a valid Parquet file."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)
        sttm_path = _make_gold_sttm(tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=3)
        run_id = "test-run-g02"

        # Act
        output_paths = _apply_gold_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        assert output_file.endswith(".parquet"), "Output should be .parquet file"
        assert Path(output_file).exists()

        # Try to read it back
        df = pd.read_parquet(output_file)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert len(df.columns) > 0

    def test_multiple_target_tables(self, tmp_path, monkeypatch):
        """Test that multiple target tables produce multiple output files."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)

        # Create STTM with two target tables
        extra_rows = [
            {
                "source_table": "orders",
                "source_column": "amount",
                "target_table": "fact_sales",
                "target_column": "total_sales",
                "transformation_type": "float",
                "transformation_logic": "none",
                "description": "Total sales",
            },
            {
                "source_table": "orders",
                "source_column": "customer_name",
                "target_table": "fact_sales",
                "target_column": "customer",
                "transformation_type": "string",
                "transformation_logic": "none",
                "description": "Customer",
            },
        ]
        sttm_path = _make_gold_sttm(tmp_path, rows=extra_rows)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=4)
        run_id = "test-run-g03"

        # Act
        output_paths = _apply_gold_rules([input_file], sttm_path, run_id)

        # Assert
        assert len(output_paths) == 2, "Expected 2 output files (2 target tables)"
        for output_file in output_paths:
            assert Path(output_file).exists()

    def test_column_subset_applied(self, tmp_path, monkeypatch):
        """Test that only STTM-specified columns appear in output."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)

        # Create STTM that specifies only a subset of columns
        sttm_rows = [
            {
                "source_table": "orders",
                "source_column": "order_id",
                "target_table": "fact_orders",
                "target_column": "order_id",
                "transformation_type": "numeric",
                "transformation_logic": "none",
                "description": "Order ID",
            },
            {
                "source_table": "orders",
                "source_column": "amount",
                "target_table": "fact_orders",
                "target_column": "amount",
                "transformation_type": "float",
                "transformation_logic": "none",
                "description": "Amount",
            },
            # Note: customer_name and order_date are NOT in STTM for this table
        ]
        sttm_df = pd.DataFrame(sttm_rows)
        sttm_path = tmp_path / "subset_sttm.csv"
        sttm_df.to_csv(sttm_path, index=False)

        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=3)
        run_id = "test-run-g04"

        # Act
        output_paths = _apply_gold_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)

        # Should have pk_gold_id, order_id, and amount (3 columns)
        assert "pk_gold_id" in output_df.columns, "Should have surrogate key"
        assert "order_id" in output_df.columns, "Should have order_id"
        assert "amount" in output_df.columns, "Should have amount"
        # These should NOT be in the output
        assert "customer_name" not in output_df.columns, "customer_name should not be in output"
        assert "order_date" not in output_df.columns, "order_date should not be in output"

    def test_surrogate_key_injected(self, tmp_path, monkeypatch):
        """Test that surrogate key pk_gold_id is injected as first column."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)
        sttm_path = _make_gold_sttm(tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=3)
        run_id = "test-run-g05"

        # Act
        output_paths = _apply_gold_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)

        # First column should be surrogate key
        first_col = output_df.columns[0]
        assert first_col == "pk_gold_id", "First column should be pk_gold_id"

        # Surrogate key should have sequential values starting from 1
        surrogate_values = output_df[first_col].values
        assert surrogate_values[0] == 1, "Surrogate key should start from 1"
        assert len(surrogate_values) == len(output_df), "Surrogate key should have one value per row"

    def test_column_rename_applied(self, tmp_path, monkeypatch):
        """Test that column rename rules from STTM are applied."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)

        # Create STTM with renames
        sttm_rows = [
            {
                "source_table": "orders",
                "source_column": "amount",
                "target_table": "fact_orders",
                "target_column": "total_amount",
                "transformation_type": "float",
                "transformation_logic": "none",
                "description": "Total amount renamed",
            },
            {
                "source_table": "orders",
                "source_column": "customer_name",
                "target_table": "fact_orders",
                "target_column": "customer",
                "transformation_type": "string",
                "transformation_logic": "none",
                "description": "Customer renamed",
            },
        ]
        sttm_df = pd.DataFrame(sttm_rows)
        sttm_path = tmp_path / "rename_sttm.csv"
        sttm_df.to_csv(sttm_path, index=False)

        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=2)
        run_id = "test-run-g06"

        # Act
        output_paths = _apply_gold_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        output_df = pd.read_parquet(output_file)

        assert "total_amount" in output_df.columns, "amount should be renamed to total_amount"
        assert "customer" in output_df.columns, "customer_name should be renamed to customer"

    def test_missing_sttm_file_raises_error(self, tmp_path, monkeypatch):
        """Test that missing STTM file raises an error."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=2)
        sttm_path = str(tmp_path / "nonexistent.csv")
        run_id = "test-run-g07"

        # Act & Assert
        with pytest.raises(ValueError, match="Failed to read STTM file"):
            _apply_gold_rules([input_file], sttm_path, run_id)

    def test_missing_input_file_raises_error(self, tmp_path, monkeypatch):
        """Test that missing input file raises an error."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)
        sttm_path = _make_gold_sttm(tmp_path)
        input_file = str(tmp_path / "nonexistent.parquet")
        run_id = "test-run-g08"

        # Act & Assert
        with pytest.raises(Exception):
            _apply_gold_rules([input_file], sttm_path, run_id)

    def test_audit_logging_on_success(self, tmp_path, monkeypatch):
        """Test that audit logging is called on successful gold table creation."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)
        sttm_path = _make_gold_sttm(tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=2)
        run_id = "test-run-g09"

        with patch("agents.gold_agent.AuditLogger") as mock_audit:
            mock_audit_instance = Mock()
            mock_audit.return_value = mock_audit_instance

            # Act
            _apply_gold_rules([input_file], sttm_path, run_id)

            # Assert
            mock_audit.assert_called_with(run_id)
            mock_audit_instance.log.assert_called()
            # Check that log was called with the create_gold_table action
            calls = mock_audit_instance.log.call_args_list
            assert len(calls) > 0
            action_found = any("create_gold_table" in str(call) for call in calls)
            assert action_found, "Should log create_gold_table action"

    def test_gold_table_name_from_sttm(self, tmp_path, monkeypatch):
        """Test that output file name matches target_table from STTM."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)
        sttm_path = _make_gold_sttm(tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=2)
        run_id = "test-run-g10"

        # Act
        output_paths = _apply_gold_rules([input_file], sttm_path, run_id)

        # Assert
        output_file = output_paths[0]
        # Should be named "fact_orders.parquet" based on STTM target_table
        assert "fact_orders.parquet" in output_file, "Output file should be named fact_orders.parquet"


class TestExecuteGold:
    """Tests for the execute_gold LLM-based function."""

    @patch("agents.gold_agent.AuditLogger")
    @patch("agents.gold_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_gold_returns_paths(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_gold returns output paths."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)

        sttm_path = _make_gold_sttm(tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=2)
        run_id = "test-run-g11"

        # Mock the agent
        expected_output = [str(tmp_path / "fact_orders.parquet")]
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
        result = execute_gold(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        assert result is not None
        assert isinstance(result, list)

    @patch("agents.gold_agent.AuditLogger")
    @patch("agents.gold_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_gold_creates_trace(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_gold creates an AgentTrace for observability."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)

        sttm_path = _make_gold_sttm(tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=2)
        run_id = "test-run-g12"

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
        execute_gold(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        mock_trace.assert_called_with("gold_agent", run_id)
        mock_trace_instance.set_input.assert_called()
        mock_trace_instance.complete.assert_called()

    @patch("agents.gold_agent.AuditLogger")
    @patch("agents.gold_agent.AgentTrace")
    @patch("langgraph.prebuilt.create_react_agent")
    def test_execute_gold_logs_on_start(
        self, mock_create_agent, mock_trace, mock_audit, tmp_path, monkeypatch
    ):
        """Test that execute_gold logs when starting."""
        # Arrange
        monkeypatch.setattr("agents.gold_agent.GOLD_DIR", tmp_path)

        sttm_path = _make_gold_sttm(tmp_path)
        input_file = _make_test_silver_parquet(tmp_path, "orders_silver.parquet", rows=2)
        run_id = "test-run-g13"

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
        execute_gold(
            input_files=[input_file],
            sttm_path=sttm_path,
            run_id=run_id,
        )

        # Assert
        mock_audit.assert_called_with(run_id)
        mock_audit_instance.log.assert_called()
