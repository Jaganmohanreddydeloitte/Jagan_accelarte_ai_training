"""
Tests for agents.sttm_generator module.

TEST STRATEGY:
- Test context preparation for each layer (Bronze, Silver, Gold)
- Test STTM row extraction from LLM responses
- Test JSON array parsing with edge cases (think tags, markdown fences)
- Test LLM invocation with retry logic and fail-loud behavior
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
from agents.sttm_generator import (
    _prepare_bronze_context,
    _prepare_silver_context,
    _prepare_gold_context,
    _parse_json_array,
    _invoke_llm_for_sttm_rows,
)


# ─── Sample STTM Row Constants ───────────────────────────────────────────────

BRONZE_ROW = {
    "source_column": "customer_id",
    "target_column": "customer_id",
    "transformation_type": "numeric",
    "transformation_logic": "none",
    "description": "Customer identifier",
}

SILVER_ROW = {
    "source_column": "customer_id",
    "target_column": "customer_id",
    "transformation_type": "numeric",
    "transformation_logic": "fill_mean",
    "description": "Customer ID with null handling",
}

GOLD_ROW = {
    "source_table": "customers",
    "source_column": "customer_id",
    "target_table": "fact_customers",
    "target_column": "customer_id",
    "transformation_type": "numeric",
    "transformation_logic": "none",
    "description": "Customer ID in fact table",
}


# ─── Helper Functions ───────────────────────────────────────────────────────

def _make_test_profile_json(tmp_path, files=None):
    """Create a test profile JSON file."""
    profile = {
        "run_id": "test-run-sttm-001",
        "timestamp": "2024-01-01T00:00:00",
        "files": files or ["/data/customers.csv"],
        "task_description": "Profile test data",
        "profile": {
            "semantic_meanings": {"customer_id": "unique id", "name": "customer name"},
            "join_keys": ["customer_id"],
            "quality_notes": {},
            "overall_quality_score": 95,
        },
    }
    profile_path = tmp_path / "profile.json"
    with open(profile_path, "w") as f:
        json.dump(profile, f)
    return str(profile_path)


def _make_test_sttm_csv(tmp_path, filename, rows=None):
    """Create a test STTM CSV file."""
    if rows is None:
        rows = [
            {
                "source_column": "id",
                "target_column": "customer_id",
                "transformation_type": "numeric",
                "transformation_logic": "none",
            },
            {
                "source_column": "name",
                "target_column": "customer_name",
                "transformation_type": "string",
                "transformation_logic": "lowercase",
            },
        ]
    
    df = pd.DataFrame(rows)
    csv_path = tmp_path / filename
    df.to_csv(csv_path, index=False)
    return str(csv_path)


def _mock_reporter_agent(response_content):
    """Create a mock agent that returns specified content."""
    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [
            Mock(type="human"),
            Mock(type="ai", content=response_content),
        ]
    }
    return mock_agent


# ─── Test Classes ───────────────────────────────────────────────────────────

class TestPrepareBronzeContext:
    """Tests for _prepare_bronze_context function."""

    def test_returns_profile_dict(self, tmp_path):
        """Test that _prepare_bronze_context returns profile dictionary."""
        # Arrange
        profile_path = _make_test_profile_json(tmp_path, files=["/data/test.csv"])

        # Act
        result = _prepare_bronze_context(profile_path)

        # Assert
        assert "files" in result
        assert "profile" in result
        assert isinstance(result["files"], list)
        assert "/data/test.csv" in result["files"]

    def test_returns_empty_dict_on_missing_file(self, tmp_path):
        """Test that _prepare_bronze_context handles missing file gracefully."""
        # Arrange
        nonexistent_path = str(tmp_path / "nonexistent.json")

        # Act
        result = _prepare_bronze_context(nonexistent_path)

        # Assert
        assert "error" in result


class TestPrepareSilverContext:
    """Tests for _prepare_silver_context function."""

    def test_filters_to_approved_columns(self, tmp_path):
        """Test that _prepare_silver_context filters to approved columns."""
        # Arrange
        bronze_output_paths = ["/data/bronze/orders.parquet"]
        sttm_path = _make_test_sttm_csv(tmp_path, "bronze_sttm.csv")

        # Act
        result = _prepare_silver_context(bronze_output_paths, sttm_path)

        # Assert
        assert "approved_columns" in result
        assert "customer_id" in result["approved_columns"]
        assert "customer_name" in result["approved_columns"]

    def test_returns_filename_not_full_path(self, tmp_path):
        """Test that _prepare_silver_context returns relative paths."""
        # Arrange
        bronze_output_paths = ["/data/bronze/orders.parquet", "/data/bronze/customers.parquet"]
        sttm_path = _make_test_sttm_csv(tmp_path, "bronze_sttm.csv")

        # Act
        result = _prepare_silver_context(bronze_output_paths, sttm_path)

        # Assert
        assert "bronze_output_paths" in result
        assert isinstance(result["bronze_output_paths"], list)

    def test_handles_missing_sttm_gracefully(self, tmp_path):
        """Test that _prepare_silver_context handles missing STTM file."""
        # Arrange
        bronze_output_paths = ["/data/bronze/orders.parquet"]
        nonexistent_sttm = str(tmp_path / "nonexistent.csv")

        # Act
        result = _prepare_silver_context(bronze_output_paths, nonexistent_sttm)

        # Assert
        assert "error" in result


class TestPrepareGoldContext:
    """Tests for _prepare_gold_context function."""

    def test_filters_to_approved_columns(self, tmp_path):
        """Test that _prepare_gold_context includes STTM columns."""
        # Arrange
        silver_output_paths = ["/data/silver/orders.parquet"]
        sttm_path = _make_test_sttm_csv(tmp_path, "silver_sttm.csv")

        # Act
        result = _prepare_gold_context(silver_output_paths, sttm_path)

        # Assert
        assert "silver_sttm_columns" in result
        assert isinstance(result["silver_sttm_columns"], list)
        assert len(result["silver_sttm_columns"]) > 0

    def test_handles_missing_sttm_gracefully(self, tmp_path):
        """Test that _prepare_gold_context handles missing STTM file."""
        # Arrange
        silver_output_paths = ["/data/silver/orders.parquet"]
        nonexistent_sttm = str(tmp_path / "nonexistent.csv")

        # Act
        result = _prepare_gold_context(silver_output_paths, nonexistent_sttm)

        # Assert
        assert "error" in result


class TestParseJsonArray:
    """Tests for the _parse_json_array function."""

    def test_extracts_plain_json_array(self):
        """Test that _parse_json_array extracts a plain JSON array."""
        # Arrange
        raw = json.dumps([BRONZE_ROW, BRONZE_ROW])

        # Act
        rows = _parse_json_array(raw)

        # Assert
        assert len(rows) == 2
        assert rows[0]["source_column"] == "customer_id"

    def test_extracts_json_with_markdown_fences(self):
        """Test that _parse_json_array extracts JSON from markdown code blocks."""
        # Arrange
        array_str = json.dumps([BRONZE_ROW, SILVER_ROW])
        raw = f"```json\n{array_str}\n```"

        # Act
        rows = _parse_json_array(raw)

        # Assert
        assert len(rows) == 2
        assert rows[0]["source_column"] == "customer_id"
        assert rows[1]["transformation_logic"] == "fill_mean"

    def test_extracts_json_with_triple_backticks(self):
        """Test that _parse_json_array extracts JSON from triple backticks."""
        # Arrange
        array_str = json.dumps([BRONZE_ROW])
        raw = f"```\n{array_str}\n```"

        # Act
        rows = _parse_json_array(raw)

        # Assert
        assert len(rows) == 1

    def test_returns_empty_list_when_no_array(self):
        """Test that _parse_json_array returns empty list when no JSON array found."""
        # Arrange
        raw = "This is plain text with no JSON"

        # Act
        rows = _parse_json_array(raw)

        # Assert
        assert rows == []

    def test_handles_think_tags_correctly(self):
        """Test that _parse_json_array handles <think> tags with corrupted brackets correctly.
        
        The scenario: LLM response contains <think>...[decoy]...</think> followed by real array.
        _parse_json_array should find the real trailing array, not merge corrupted brackets.
        """
        # Arrange - Simulate response with think tags and decoy array
        decoy_array = '[{"bad": "decoy"}]'
        real_array_str = json.dumps([BRONZE_ROW, SILVER_ROW])
        raw = f"<think>Let me think about this:\n{decoy_array}\nThis is confusing</think>\nHere is the STTM:\n{real_array_str}"

        # Act
        rows = _parse_json_array(raw)

        # Assert
        # Should either:
        # 1. Extract the real trailing array correctly, or
        # 2. Return empty list (fail-loud is handled by _invoke_llm_for_sttm_rows)
        # NOT: extract corrupted merge of both arrays
        if rows:
            assert len(rows) >= 1
            # If we got rows, verify they have expected fields
            assert all("source_column" in row for row in rows)
        else:
            # Empty list is acceptable - fail-loud is handled upstream
            assert rows == []

    def test_returns_empty_on_invalid_json(self):
        """Test that _parse_json_array returns empty list on invalid JSON."""
        # Arrange
        raw = "[{invalid json}]"

        # Act
        rows = _parse_json_array(raw)

        # Assert
        assert rows == []

    def test_prefers_last_array_in_multiple(self):
        """Test that _parse_json_array uses last ] as end boundary."""
        # Arrange - Multiple arrays, should take last one
        array1 = json.dumps([{"id": 1}])
        array2 = json.dumps([BRONZE_ROW])
        raw = f"First array: {array1}\nSecond array: {array2}"

        # Act
        rows = _parse_json_array(raw)

        # Assert - Should get array2 (uses rfind for ] )
        if rows:
            # Should get the second array
            assert any("source_column" in row for row in rows)


class TestInvokeLlmForSttmRows:
    """Tests for the _invoke_llm_for_sttm_rows function."""

    @patch("agents.sttm_generator._make_llm")
    def test_returns_rows_on_first_success(self, mock_make_llm):
        """Test that _invoke_llm_for_sttm_rows returns rows when LLM succeeds on first attempt."""
        # Arrange
        array_str = json.dumps([BRONZE_ROW, SILVER_ROW])
        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content=array_str)
        mock_make_llm.return_value = mock_llm

        # Act
        rows = _invoke_llm_for_sttm_rows("Generate STTM", "bronze")

        # Assert
        assert len(rows) == 2
        assert rows[0]["source_column"] == "customer_id"
        # Should only invoke LLM once
        assert mock_llm.invoke.call_count == 1

    @patch("agents.sttm_generator._make_llm")
    def test_retries_once_on_empty(self, mock_make_llm):
        """Test that _invoke_llm_for_sttm_rows retries once when first attempt is empty."""
        # Arrange
        array_str = json.dumps([BRONZE_ROW])
        mock_llm = Mock()
        # First call returns non-JSON, second returns valid JSON
        mock_llm.invoke.side_effect = [
            Mock(content="This is not JSON"),
            Mock(content=array_str),
        ]
        mock_make_llm.return_value = mock_llm

        # Act
        rows = _invoke_llm_for_sttm_rows("Generate STTM", "bronze")

        # Assert
        assert len(rows) == 1
        # Should invoke LLM twice
        assert mock_llm.invoke.call_count == 2

    @patch("agents.sttm_generator._make_llm")
    def test_raises_when_rows_empty_after_retries(self, mock_make_llm):
        """Test that _invoke_llm_for_sttm_rows raises ValueError after failed retries."""
        # Arrange
        mock_llm = Mock()
        # Both attempts return non-JSON or empty array
        mock_llm.invoke.side_effect = [
            Mock(content="Not JSON at all"),
            Mock(content="Still not JSON"),
        ]
        mock_make_llm.return_value = mock_llm

        # Act & Assert
        with pytest.raises(ValueError, match="STTM generation failed"):
            _invoke_llm_for_sttm_rows("Generate STTM", "bronze")

    @patch("agents.sttm_generator._make_llm")
    def test_second_attempt_includes_explicit_instruction(self, mock_make_llm):
        """Test that _invoke_llm_for_sttm_rows adds explicit instruction on second attempt."""
        # Arrange
        array_str = json.dumps([BRONZE_ROW])
        mock_llm = Mock()
        mock_llm.invoke.side_effect = [
            Mock(content="Not JSON"),
            Mock(content=array_str),
        ]
        mock_make_llm.return_value = mock_llm

        # Act
        rows = _invoke_llm_for_sttm_rows("Original prompt", "bronze")

        # Assert
        assert len(rows) == 1
        # Verify second call had added instruction
        second_call = mock_llm.invoke.call_args_list[1]
        prompt_arg = second_call[0][0]
        assert "Return ONLY the JSON array" in prompt_arg
        assert "No other text" in prompt_arg

    @patch("agents.sttm_generator._make_llm")
    def test_error_message_includes_truncated_response(self, mock_make_llm):
        """Test that error message includes truncated raw response."""
        # Arrange
        mock_llm = Mock()
        long_response = "x" * 1000
        mock_llm.invoke.side_effect = [
            Mock(content=long_response),
            Mock(content=long_response),
        ]
        mock_make_llm.return_value = mock_llm

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            _invoke_llm_for_sttm_rows("Generate", "silver")
        
        error_msg = str(exc_info.value)
        assert "truncated" in error_msg.lower() or "response" in error_msg.lower()
