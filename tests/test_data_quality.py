"""Tests for data quality checking module."""

import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_quality import (
    DataQualityChecker,
    QualityIssue,
    QualityScore,
    QualitySeverity,
)


class TestQualityIssue:
    """Test QualityIssue dataclass."""
    
    def test_create_issue_minimal(self):
        """Test creating issue with minimal fields."""
        issue = QualityIssue(
            severity=QualitySeverity.WARNING.value,
            category="null_values",
            message="Test issue",
        )
        
        assert issue.severity == "warning"
        assert issue.category == "null_values"
        assert issue.message == "Test issue"
        assert issue.affected_rows == 0
        assert issue.affected_columns == []
    
    def test_create_issue_full(self):
        """Test creating issue with all fields."""
        issue = QualityIssue(
            severity=QualitySeverity.CRITICAL.value,
            category="null_values",
            message="Column A has 50% nulls",
            affected_rows=500,
            affected_columns=["A"],
            value=50.0,
            threshold=5.0,
        )
        
        assert issue.severity == "critical"
        assert issue.affected_rows == 500
        assert issue.affected_columns == ["A"]
        assert issue.value == 50.0
        assert issue.threshold == 5.0
    
    def test_issue_to_dict(self):
        """Test converting issue to dictionary."""
        issue = QualityIssue(
            severity=QualitySeverity.WARNING.value,
            category="row_count",
            message="Low row count",
            affected_rows=1,
        )
        
        issue_dict = issue.to_dict()
        
        assert isinstance(issue_dict, dict)
        assert issue_dict["severity"] == "warning"
        assert issue_dict["category"] == "row_count"
        assert issue_dict["affected_columns"] == []


class TestQualityScore:
    """Test QualityScore dataclass."""
    
    def test_create_score(self):
        """Test creating quality score."""
        issues = [
            QualityIssue(
                severity=QualitySeverity.WARNING.value,
                category="test",
                message="Test",
            )
        ]
        
        score = QualityScore(
            layer="bronze",
            total_rows=1000,
            total_columns=10,
            issues=issues,
            overall_score=95.0,
            passed=True,
            timestamp="2024-01-01T00:00:00Z",
        )
        
        assert score.layer == "bronze"
        assert score.total_rows == 1000
        assert score.overall_score == 95.0
        assert score.passed is True
    
    def test_score_to_dict(self):
        """Test converting score to dictionary."""
        score = QualityScore(
            layer="silver",
            total_rows=500,
            total_columns=5,
            issues=[],
            overall_score=100.0,
            passed=True,
            timestamp="2024-01-01T00:00:00Z",
        )
        
        score_dict = score.to_dict()
        
        assert isinstance(score_dict, dict)
        assert score_dict["layer"] == "silver"
        assert score_dict["total_rows"] == 500
        assert score_dict["issues"] == []


class TestNullValuesCheck:
    """Test null value checking."""
    
    def test_no_nulls(self):
        """Test data with no null values."""
        df = pd.DataFrame({
            "A": [1, 2, 3],
            "B": ["a", "b", "c"],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_null_values(df)
        
        assert len(issues) == 0
    
    def test_warning_nulls(self):
        """Test data with acceptable nulls."""
        df = pd.DataFrame({
            "A": [1, 2, 3, np.nan],
            "B": ["a", "b", "c", "d"],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_null_values(df, max_null_pct=5.0)
        
        # 1 null out of 4 = 25% > 5% threshold
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "A" in issues[0].affected_columns
    
    def test_critical_nulls_in_key_column(self):
        """Test critical columns cannot have nulls."""
        df = pd.DataFrame({
            "id": [1, 2, np.nan],
            "name": ["a", "b", "c"],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_null_values(df, critical_columns=["id"])
        
        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert issues[0].affected_rows == 1


class TestRowCountCheck:
    """Test row count validation."""
    
    def test_row_count_ok(self):
        """Test acceptable row count."""
        df = pd.DataFrame({"A": [1, 2, 3, 4, 5]})
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_row_count(df, min_rows=1, max_rows=100)
        
        assert len(issues) == 0
    
    def test_row_count_too_low(self):
        """Test row count below minimum."""
        df = pd.DataFrame({"A": []})
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_row_count(df, min_rows=1)
        
        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert "minimum" in issues[0].message.lower()
    
    def test_row_count_too_high(self):
        """Test row count exceeds maximum."""
        df = pd.DataFrame({"A": range(1000)})
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_row_count(df, max_rows=100)
        
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "exceeds" in issues[0].message.lower()
    
    def test_row_count_expected_with_tolerance(self):
        """Test row count matches expected (within tolerance)."""
        df = pd.DataFrame({"A": range(100)})
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_row_count(df, expected_rows=100)
        
        # 100 rows with 100 expected = 0 difference (within 10% tolerance)
        assert len(issues) == 0
    
    def test_row_count_expected_exceeds_tolerance(self):
        """Test row count differs too much from expected."""
        df = pd.DataFrame({"A": range(50)})
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_row_count(df, expected_rows=100)
        
        # 50 rows vs 100 expected = 50 difference > 10 tolerance
        assert len(issues) == 1
        assert issues[0].severity == "warning"


class TestDuplicatesCheck:
    """Test duplicate detection."""
    
    def test_no_duplicates(self):
        """Test data with no duplicates."""
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "value": ["a", "b", "c"],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_duplicates(df, key_columns=["id"])
        
        assert len(issues) == 0
    
    def test_duplicates_detected(self):
        """Test detection of duplicate rows."""
        df = pd.DataFrame({
            "id": [1, 1, 2],
            "value": ["a", "a", "b"],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_duplicates(df, key_columns=["id"])
        
        # 2 rows (the duplicate pair) marked as duplicates
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].affected_rows > 0


class TestNumericAnomalies:
    """Test anomaly detection in numeric columns."""
    
    def test_no_anomalies(self):
        """Test normal numeric data."""
        df = pd.DataFrame({
            "value": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_numeric_anomalies(df, std_dev_threshold=3.0)
        
        # No outliers beyond 3 std devs
        assert len(issues) == 0
    
    def test_anomalies_detected(self):
        """Test detection of numeric outliers."""
        df = pd.DataFrame({
            "value": [1, 2, 3, 4, 5, 6, 7, 8, 9, 1000],  # 1000 is outlier
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_numeric_anomalies(df, std_dev_threshold=2.0)
        
        assert len(issues) >= 1
        assert issues[0].severity == "info"
        assert "outlier" in issues[0].message.lower()


class TestDataTypeCheck:
    """Test data type validation."""
    
    def test_correct_types(self):
        """Test data with correct types."""
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["a", "b", "c"],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_data_types(
            df,
            expected_types={"id": "int", "name": "str"},
        )
        
        assert len(issues) == 0
    
    def test_missing_column(self):
        """Test detection of missing column."""
        df = pd.DataFrame({"A": [1, 2, 3]})
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_data_types(
            df,
            expected_types={"B": "int"},
        )
        
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "not found" in issues[0].message.lower()


class TestValueRangesCheck:
    """Test value range validation."""
    
    def test_values_in_range(self):
        """Test values within acceptable range."""
        df = pd.DataFrame({
            "age": [18, 25, 30, 40, 65],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_value_ranges(
            df,
            ranges={"age": (0, 150)},
        )
        
        assert len(issues) == 0
    
    def test_values_below_range(self):
        """Test values below minimum range."""
        df = pd.DataFrame({
            "age": [-5, 25, 30],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_value_ranges(
            df,
            ranges={"age": (0, 150)},
        )
        
        assert len(issues) == 1
        assert "below minimum" in issues[0].message.lower()
    
    def test_values_above_range(self):
        """Test values above maximum range."""
        df = pd.DataFrame({
            "age": [25, 30, 200],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_value_ranges(
            df,
            ranges={"age": (0, 150)},
        )
        
        assert len(issues) == 1
        assert "above maximum" in issues[0].message.lower()


class TestRequiredColumns:
    """Test required column checking."""
    
    def test_all_columns_present(self):
        """Test when all required columns exist."""
        df = pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["a", "b", "c"],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_required_columns(df, required_columns=["id", "name"])
        
        assert len(issues) == 0
    
    def test_missing_columns(self):
        """Test when required columns are missing."""
        df = pd.DataFrame({"id": [1, 2, 3]})
        
        checker = DataQualityChecker("test-run", "bronze")
        issues = checker.check_required_columns(
            df,
            required_columns=["id", "name", "email"],
        )
        
        assert len(issues) == 2
        assert all(i.severity == "critical" for i in issues)


class TestScoreCalculation:
    """Test quality score calculation."""
    
    def test_perfect_score(self):
        """Test perfect quality score."""
        checker = DataQualityChecker("test-run", "bronze")
        checker.issues = []
        
        score = checker.calculate_score()
        
        assert score == 100.0
    
    def test_score_with_warnings(self):
        """Test score calculation with warnings."""
        checker = DataQualityChecker("test-run", "bronze")
        checker.issues = [
            QualityIssue(
                severity=QualitySeverity.WARNING.value,
                category="test",
                message="Test warning",
            ),
            QualityIssue(
                severity=QualitySeverity.WARNING.value,
                category="test",
                message="Test warning 2",
            ),
        ]
        
        score = checker.calculate_score(warning_weight=1.0)
        
        # Start 100, subtract 1 point per warning = 98
        assert score == 98.0
    
    def test_score_with_critical_issues(self):
        """Test score drops significantly with critical issues."""
        checker = DataQualityChecker("test-run", "bronze")
        checker.issues = [
            QualityIssue(
                severity=QualitySeverity.CRITICAL.value,
                category="test",
                message="Test critical",
            ),
        ]
        
        score = checker.calculate_score(critical_weight=10.0)
        
        # Start 100, subtract 10 for critical = 90
        assert score == 90.0
    
    def test_score_cannot_go_negative(self):
        """Test that score is clamped to 0-100."""
        checker = DataQualityChecker("test-run", "bronze")
        checker.issues = [
            QualityIssue(
                severity=QualitySeverity.CRITICAL.value,
                category="test",
                message="Test",
            )
            for _ in range(50)
        ]
        
        score = checker.calculate_score(critical_weight=10.0)
        
        assert 0.0 <= score <= 100.0


class TestValidationFlow:
    """Test complete validation workflow."""
    
    def test_validate_clean_data(self):
        """Test validation of clean data."""
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["a", "b", "c", "d", "e"],
            "value": [10.0, 20.0, 30.0, 40.0, 50.0],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        result = checker.validate(df, min_score=80.0)
        
        assert result.passed is True
        assert result.overall_score == 100.0
        assert len(result.issues) == 0
    
    def test_validate_dirty_data_passes(self):
        """Test validation of data with minor issues."""
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["a", "b", "c", "d", np.nan],  # 1 null (20%)
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        result = checker.validate(df, min_score=80.0, max_null_pct=30.0)
        
        # Should pass with min_score=80
        assert result.passed is True
        assert result.overall_score >= 80.0
    
    def test_validate_dirty_data_fails(self):
        """Test validation of data with critical issues."""
        df = pd.DataFrame({
            "id": [np.nan, np.nan, np.nan],  # All nulls
            "name": ["a", "b", "c"],
        })
        
        checker = DataQualityChecker("test-run", "bronze")
        result = checker.validate(
            df,
            min_score=99.5,  # Extremely strict threshold
            critical_columns=["id"],
        )
        
        # Should fail due to critical null in required column + strict threshold
        assert result.passed is False
        assert result.overall_score < 99.5
    
    def test_validate_empty_dataframe(self):
        """Test validation of empty dataframe."""
        df = pd.DataFrame()
        
        checker = DataQualityChecker("test-run", "bronze")
        result = checker.validate(df, min_score=95.0)  # Strict threshold
        
        # Empty dataframe should fail row count check with strict threshold
        assert result.passed is False


class TestSummaryGeneration:
    """Test summary report generation."""
    
    def test_summary_no_issues(self):
        """Test summary when no issues found."""
        checker = DataQualityChecker("test-run", "bronze")
        checker.issues = []
        
        summary = checker.get_summary()
        
        assert "No quality issues" in summary
    
    def test_summary_with_issues(self):
        """Test summary with multiple issue types."""
        checker = DataQualityChecker("test-run", "bronze")
        checker.issues = [
            QualityIssue(
                severity=QualitySeverity.CRITICAL.value,
                category="test",
                message="Critical issue",
            ),
            QualityIssue(
                severity=QualitySeverity.ERROR.value,
                category="test",
                message="Error issue",
            ),
            QualityIssue(
                severity=QualitySeverity.WARNING.value,
                category="test",
                message="Warning issue",
            ),
        ]
        
        summary = checker.get_summary()
        
        assert "CRITICAL" in summary
        assert "ERROR" in summary
        assert "WARNING" in summary


class TestCheckerInitialization:
    """Test checker initialization."""
    
    def test_init_with_run_and_layer(self):
        """Test checker initialization."""
        checker = DataQualityChecker("run-123", "bronze")
        
        assert checker.run_id == "run-123"
        assert checker.layer_name == "bronze"
        assert checker.issues == []
        assert checker.logger is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
