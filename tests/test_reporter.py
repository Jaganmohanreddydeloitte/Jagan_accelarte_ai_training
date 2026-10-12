"""
Tests for agents.reporter module.

TEST STRATEGY:
- Test chart generation from specifications
- Test reporter tools including DuckDB integration
- Verify SQL query execution and error handling
- Test analysis JSON structure and data flow
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
import duckdb
from agents.reporter import generate_chart_from_spec, _make_reporter_tools, _inspect_gold_tables
from core.config import REPORTS_DIR


# ─── Sample Analysis JSON ────────────────────────────────────────────────────

ANALYSIS_JSON = {
    "direct_answer": "Sales increased 25% year-over-year in Q4 2024",
    "charts": [
        {
            "id": "chart_1",
            "type": "bar",
            "title": "Monthly Sales Trend",
            "x_column": "month",
            "y_column": "sales",
        },
        {
            "id": "chart_2",
            "type": "pie",
            "title": "Sales by Region",
            "x_column": "region",
            "y_column": "amount",
        },
    ],
    "detailed_analysis": "Analysis shows strong growth in North and South regions",
    "sql_queries": [
        "SELECT month, SUM(sales) as sales FROM fact_orders GROUP BY month",
        "SELECT region, SUM(amount) as amount FROM fact_orders GROUP BY region",
    ],
}


# ─── Helper Functions ───────────────────────────────────────────────────────

def _make_test_gold_parquet(tmp_path, filename, rows=10):
    """Create a test Gold Parquet file."""
    data = {
        "pk_gold_id": range(1, rows + 1),
        "order_id": [1001 + i for i in range(rows)],
        "order_date": ["2024-01-01", "2024-01-02"] * (rows // 2) + (["2024-01-03"] if rows % 2 else []),
        "amount": [100.0, 250.0, 199.99, 500.0, 75.25, 300.0, 450.0, 200.0, 600.0, 350.0][:rows],
        "region": ["North", "South", "East", "West"] * (rows // 4) + (["North"] * (rows % 4)),
    }

    df = pd.DataFrame(data)
    parquet_path = tmp_path / filename
    df.to_parquet(parquet_path, index=False)
    return str(parquet_path)


def _mock_reporter_agent(analysis_json=None):
    """Create a mock reporter agent that simulates the workflow."""
    mock_agent = Mock()
    
    analysis = analysis_json or ANALYSIS_JSON
    mock_agent.invoke.return_value = {
        "messages": [
            Mock(type="human"),
            Mock(type="ai", content=json.dumps(analysis)),
        ]
    }
    return mock_agent


# ─── Test Classes ───────────────────────────────────────────────────────────

class TestGenerateChartFromSpec:
    """Tests for the generate_chart_from_spec function."""

    def test_bar_chart_returns_html(self):
        """Test that bar chart generation returns valid HTML."""
        # Arrange
        df = pd.DataFrame({
            "month": ["Jan", "Feb", "Mar", "Apr"],
            "sales": [100, 150, 200, 175],
        })
        chart_spec = {
            "type": "bar",
            "title": "Monthly Sales",
            "x_column": "month",
            "y_column": "sales",
        }

        # Act
        html = generate_chart_from_spec(df, chart_spec, "test_chart_1")

        # Assert
        assert html is not None
        assert isinstance(html, str)
        assert len(html) > 0
        assert "Monthly Sales" in html or "plotly" in html.lower()

    def test_pie_chart_returns_html(self):
        """Test that pie chart generation returns valid HTML."""
        # Arrange
        df = pd.DataFrame({
            "region": ["North", "South", "East", "West"],
            "amount": [1000, 1500, 1200, 800],
        })
        chart_spec = {
            "type": "pie",
            "title": "Sales by Region",
            "x_column": "region",
            "y_column": "amount",
        }

        # Act
        html = generate_chart_from_spec(df, chart_spec, "test_chart_2")

        # Assert
        assert html is not None
        assert isinstance(html, str)
        assert len(html) > 0
        assert "Sales by Region" in html or "plotly" in html.lower()

    def test_line_chart_returns_html(self):
        """Test that line chart generation returns valid HTML."""
        # Arrange
        df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "value": [100, 150, 120],
        })
        chart_spec = {
            "type": "line",
            "title": "Trend Over Time",
            "x_column": "date",
            "y_column": "value",
        }

        # Act
        html = generate_chart_from_spec(df, chart_spec, "test_chart_3")

        # Assert
        assert html is not None
        assert isinstance(html, str)

    def test_unknown_chart_type_defaults_to_bar(self):
        """Test that unknown chart type defaults to bar chart."""
        # Arrange
        df = pd.DataFrame({
            "category": ["A", "B", "C"],
            "value": [10, 20, 30],
        })
        chart_spec = {
            "type": "unknown_type",
            "title": "Default Chart",
            "x_column": "category",
            "y_column": "value",
        }

        # Act
        html = generate_chart_from_spec(df, chart_spec, "test_chart_4")

        # Assert
        assert html is not None
        assert isinstance(html, str)

    def test_bad_column_returns_error_html(self):
        """Test that missing column gracefully returns error HTML."""
        # Arrange
        df = pd.DataFrame({
            "category": ["A", "B", "C"],
            "value": [10, 20, 30],
        })
        chart_spec = {
            "type": "bar",
            "title": "Test Chart",
            "x_column": "nonexistent_col",
            "y_column": "value",
        }

        # Act
        html = generate_chart_from_spec(df, chart_spec, "test_chart_5")

        # Assert
        assert html is not None
        assert isinstance(html, str)
        # Should contain either error message or be empty/minimal
        assert len(html) > 0


class TestInspectGoldTables:
    """Tests for the _inspect_gold_tables function."""

    def test_inspect_gold_table(self, tmp_path):
        """Test that _inspect_gold_tables correctly inspects a Parquet file."""
        # Arrange
        parquet_path = _make_test_gold_parquet(tmp_path, "fact_orders.parquet", rows=5)

        # Act
        result = _inspect_gold_tables([parquet_path])

        # Assert
        assert "fact_orders" in result
        assert result["fact_orders"]["shape"] == (5, 5)  # 5 rows, 5 columns
        assert "pk_gold_id" in result["fact_orders"]["columns"]
        assert result["fact_orders"]["sample_rows"] is not None
        assert len(result["fact_orders"]["sample_rows"]) > 0

    def test_inspect_multiple_gold_tables(self, tmp_path):
        """Test that _inspect_gold_tables handles multiple files."""
        # Arrange
        parquet_path1 = _make_test_gold_parquet(tmp_path, "fact_orders.parquet", rows=3)
        parquet_path2 = _make_test_gold_parquet(tmp_path, "fact_sales.parquet", rows=4)

        # Act
        result = _inspect_gold_tables([parquet_path1, parquet_path2])

        # Assert
        assert len(result) == 2
        assert "fact_orders" in result
        assert "fact_sales" in result
        assert result["fact_orders"]["shape"][0] == 3
        assert result["fact_sales"]["shape"][0] == 4


class TestMakeReporterTools:
    """Tests for the reporter tool factory and DuckDB integration."""

    def test_load_tool_returns_catalog(self, tmp_path):
        """Test that load_gold_data_tool returns table catalog."""
        # Arrange
        parquet_path = _make_test_gold_parquet(tmp_path, "fact_orders.parquet", rows=5)
        run_id = "test-run-reporter-001"
        
        with patch("agents.reporter.AuditLogger"):
            tools, scratchpad, db_connection = _make_reporter_tools([parquet_path], run_id)

            # Act
            load_tool = tools[1]
            result_str = load_tool.func()
            result = json.loads(result_str)

            # Assert
            assert "fact_orders" in result
            # Shape can be a list or tuple depending on JSON serialization
            assert result["fact_orders"]["shape"][0] == 5
            assert result["fact_orders"]["shape"][1] == 5
            assert result["fact_orders"]["columns"] is not None

            # Cleanup
            if db_connection["conn"]:
                db_connection["conn"].close()

    def test_execute_query_tool_returns_results(self, tmp_path):
        """Test that execute_query_tool executes SQL and returns results."""
        # Arrange
        parquet_path = _make_test_gold_parquet(tmp_path, "fact_orders.parquet", rows=5)
        run_id = "test-run-reporter-002"
        
        with patch("agents.reporter.AuditLogger"):
            tools, scratchpad, db_connection = _make_reporter_tools([parquet_path], run_id)

            try:
                # Load data first
                load_tool = tools[1]
                load_tool.func()

                # Execute query
                execute_tool = tools[2]
                result_str = execute_tool.func("SELECT COUNT(*) as count FROM fact_orders")
                result = json.loads(result_str)

                # Assert
                assert "rows" in result
                assert result["rows"] > 0
                assert "data" in result

            finally:
                # Cleanup
                if db_connection["conn"]:
                    db_connection["conn"].close()

    def test_execute_query_tool_error_on_bad_sql(self, tmp_path):
        """Test that execute_query_tool handles bad SQL gracefully."""
        # Arrange
        parquet_path = _make_test_gold_parquet(tmp_path, "fact_orders.parquet", rows=5)
        run_id = "test-run-reporter-003"
        
        with patch("agents.reporter.AuditLogger"):
            tools, scratchpad, db_connection = _make_reporter_tools([parquet_path], run_id)

            try:
                # Load data first
                load_tool = tools[1]
                load_tool.func()

                # Execute bad query
                execute_tool = tools[2]
                
                # This should raise an exception
                with pytest.raises(Exception):
                    execute_tool.func("SELECT * FROM nonexistent_table")

            finally:
                # Cleanup
                if db_connection["conn"]:
                    db_connection["conn"].close()

    def test_execute_tool_requires_loaded_data(self, tmp_path):
        """Test that execute_query_tool requires load_gold_data_tool to be called first."""
        # Arrange
        parquet_path = _make_test_gold_parquet(tmp_path, "fact_orders.parquet", rows=5)
        run_id = "test-run-reporter-004"
        
        with patch("agents.reporter.AuditLogger"):
            tools, scratchpad, db_connection = _make_reporter_tools([parquet_path], run_id)

            try:
                # Try to execute without loading
                execute_tool = tools[2]
                
                with pytest.raises(ValueError, match="Database not loaded"):
                    execute_tool.func("SELECT COUNT(*) FROM fact_orders")

            finally:
                # Cleanup
                if db_connection["conn"]:
                    db_connection["conn"].close()

    def test_submit_analysis_tool_stores_result(self, tmp_path):
        """Test that submit_analysis_tool stores analysis in scratchpad."""
        # Arrange
        parquet_path = _make_test_gold_parquet(tmp_path, "fact_orders.parquet", rows=5)
        run_id = "test-run-reporter-005"
        
        with patch("agents.reporter.AuditLogger"):
            tools, scratchpad, db_connection = _make_reporter_tools([parquet_path], run_id)

            try:
                submit_tool = tools[3]
                analysis = {"direct_answer": "Test answer", "quality_score": 95}
                
                # Act
                result_str = submit_tool.func(json.dumps(analysis))
                result = json.loads(result_str)

                # Assert
                assert result["status"] == "ok"
                assert "direct_answer" in scratchpad
                assert scratchpad["direct_answer"] == "Test answer"

            finally:
                # Cleanup
                if db_connection["conn"]:
                    db_connection["conn"].close()


class TestAnalysisStructure:
    """Tests for analysis JSON structure and content."""

    def test_analysis_json_has_required_fields(self):
        """Test that analysis JSON has required fields."""
        # Arrange & Act
        analysis = ANALYSIS_JSON

        # Assert
        assert "direct_answer" in analysis
        assert "charts" in analysis
        assert "detailed_analysis" in analysis
        assert "sql_queries" in analysis

    def test_chart_spec_has_required_fields(self):
        """Test that chart specifications have required fields."""
        # Arrange
        analysis = ANALYSIS_JSON
        
        # Act & Assert
        for chart in analysis["charts"]:
            assert "id" in chart
            assert "type" in chart
            assert "title" in chart
            assert "x_column" in chart
            assert "y_column" in chart
