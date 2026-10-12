"""Data quality checks and validation framework for pipeline layers."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
import numpy as np

from core.audit import AuditLogger


class QualitySeverity(Enum):
    """Severity levels for quality issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class QualityIssue:
    """Represents a single data quality issue."""
    severity: str
    category: str
    message: str
    affected_rows: int = 0
    affected_columns: List[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    
    def __post_init__(self):
        if self.affected_columns is None:
            self.affected_columns = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["affected_columns"] = self.affected_columns or []
        return data


@dataclass
class QualityScore:
    """Data quality assessment result."""
    layer: str
    total_rows: int
    total_columns: int
    issues: List[QualityIssue]
    overall_score: float  # 0-100
    passed: bool
    timestamp: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "layer": self.layer,
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "issues": [issue.to_dict() for issue in self.issues],
            "overall_score": self.overall_score,
            "passed": self.passed,
            "timestamp": self.timestamp,
        }


class DataQualityChecker:
    """Automated data quality validation for pipeline layers."""
    
    def __init__(self, run_id: str, layer_name: str):
        """Initialize quality checker.
        
        Args:
            run_id: Pipeline run ID
            layer_name: Layer name (bronze, silver, gold)
        """
        self.run_id = run_id
        self.layer_name = layer_name
        self.logger = AuditLogger(run_id)
        self.issues = []
        self.baseline_stats = {}
    
    def check_null_values(
        self,
        df: pd.DataFrame,
        max_null_pct: float = 5.0,
        critical_columns: Optional[List[str]] = None,
    ) -> List[QualityIssue]:
        """
        Check for unexpected null values.
        
        Args:
            df: DataFrame to check
            max_null_pct: Maximum acceptable null percentage (default 5%)
            critical_columns: Columns that must not have nulls
        
        Returns:
            List of QualityIssue objects
        """
        issues = []
        
        if critical_columns is None:
            critical_columns = []
        
        null_counts = df.isnull().sum()
        null_pcts = (null_counts / len(df) * 100).round(2)
        
        for col in df.columns:
            null_pct = null_pcts[col]
            
            # Check critical columns (must be 0% nulls)
            if col in critical_columns and null_counts[col] > 0:
                issues.append(QualityIssue(
                    severity=QualitySeverity.CRITICAL.value,
                    category="null_values",
                    message=f"Column '{col}' is critical but has {null_counts[col]} nulls ({null_pct}%)",
                    affected_rows=int(null_counts[col]),
                    affected_columns=[col],
                    value=null_pct,
                    threshold=0.0,
                ))
            
            # Check standard columns (warning if exceeds threshold)
            elif null_pct > max_null_pct and null_counts[col] > 0:
                issues.append(QualityIssue(
                    severity=QualitySeverity.WARNING.value,
                    category="null_values",
                    message=f"Column '{col}' has {null_pct}% nulls (threshold: {max_null_pct}%)",
                    affected_rows=int(null_counts[col]),
                    affected_columns=[col],
                    value=null_pct,
                    threshold=max_null_pct,
                ))
        
        self.issues.extend(issues)
        return issues
    
    def check_row_count(
        self,
        df: pd.DataFrame,
        min_rows: int = 1,
        max_rows: Optional[int] = None,
        expected_rows: Optional[int] = None,
    ) -> List[QualityIssue]:
        """
        Check row count is within expected range.
        
        Args:
            df: DataFrame to check
            min_rows: Minimum acceptable rows (default 1)
            max_rows: Maximum acceptable rows (optional)
            expected_rows: Expected row count (for validation)
        
        Returns:
            List of QualityIssue objects
        """
        issues = []
        row_count = len(df)
        
        # Check minimum rows
        if row_count < min_rows:
            issues.append(QualityIssue(
                severity=QualitySeverity.CRITICAL.value,
                category="row_count",
                message=f"Only {row_count} rows (minimum: {min_rows})",
                affected_rows=row_count,
                value=float(row_count),
                threshold=float(min_rows),
            ))
        
        # Check maximum rows
        if max_rows is not None and row_count > max_rows:
            issues.append(QualityIssue(
                severity=QualitySeverity.WARNING.value,
                category="row_count",
                message=f"{row_count} rows exceeds maximum ({max_rows})",
                affected_rows=row_count,
                value=float(row_count),
                threshold=float(max_rows),
            ))
        
        # Check expected rows (within 10%)
        if expected_rows is not None:
            tolerance = expected_rows * 0.1
            if abs(row_count - expected_rows) > tolerance:
                issues.append(QualityIssue(
                    severity=QualitySeverity.WARNING.value,
                    category="row_count",
                    message=f"{row_count} rows differs from expected {expected_rows} (tolerance: {tolerance:.0f})",
                    affected_rows=row_count,
                    value=float(row_count),
                    threshold=float(expected_rows),
                ))
        
        self.issues.extend(issues)
        return issues
    
    def check_duplicates(
        self,
        df: pd.DataFrame,
        key_columns: Optional[List[str]] = None,
        max_duplicate_pct: float = 1.0,
    ) -> List[QualityIssue]:
        """
        Check for duplicate rows.
        
        Args:
            df: DataFrame to check
            key_columns: Columns to check for duplicates (default all)
            max_duplicate_pct: Maximum acceptable duplicate percentage
        
        Returns:
            List of QualityIssue objects
        """
        issues = []
        
        if key_columns is None:
            key_columns = list(df.columns)
        
        duplicates = df.duplicated(subset=key_columns, keep=False).sum()
        dup_pct = (duplicates / len(df) * 100).round(2)
        
        if dup_pct > max_duplicate_pct:
            issues.append(QualityIssue(
                severity=QualitySeverity.WARNING.value,
                category="duplicates",
                message=f"{duplicates} duplicate rows ({dup_pct}%, threshold: {max_duplicate_pct}%)",
                affected_rows=duplicates,
                affected_columns=key_columns,
                value=dup_pct,
                threshold=max_duplicate_pct,
            ))
        
        self.issues.extend(issues)
        return issues
    
    def check_numeric_anomalies(
        self,
        df: pd.DataFrame,
        std_dev_threshold: float = 3.0,
    ) -> List[QualityIssue]:
        """
        Detect anomalies in numeric columns (outliers beyond 3 std devs).
        
        Args:
            df: DataFrame to check
            std_dev_threshold: Number of std devs for outlier detection (default 3.0)
        
        Returns:
            List of QualityIssue objects
        """
        issues = []
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            if df[col].isnull().all():
                continue
            
            mean = df[col].mean()
            std = df[col].std()
            
            if std == 0:
                continue
            
            z_scores = np.abs((df[col] - mean) / std)
            outliers = (z_scores > std_dev_threshold).sum()
            outlier_pct = (outliers / len(df) * 100).round(2)
            
            if outliers > 0:
                issues.append(QualityIssue(
                    severity=QualitySeverity.INFO.value,
                    category="numeric_anomalies",
                    message=f"Column '{col}' has {outliers} outliers ({outlier_pct}%) beyond {std_dev_threshold} std devs",
                    affected_rows=outliers,
                    affected_columns=[col],
                    value=outlier_pct,
                    threshold=0.0,
                ))
        
        self.issues.extend(issues)
        return issues
    
    def check_data_types(
        self,
        df: pd.DataFrame,
        expected_types: Optional[Dict[str, str]] = None,
    ) -> List[QualityIssue]:
        """
        Check that columns have expected data types.
        
        Args:
            df: DataFrame to check
            expected_types: Dict of column_name -> expected_dtype
        
        Returns:
            List of QualityIssue objects
        """
        issues = []
        
        if expected_types is None:
            return issues
        
        for col, expected_type in expected_types.items():
            if col not in df.columns:
                issues.append(QualityIssue(
                    severity=QualitySeverity.ERROR.value,
                    category="data_types",
                    message=f"Column '{col}' not found (expected {expected_type})",
                    affected_columns=[col],
                ))
            else:
                actual_type = str(df[col].dtype)
                if expected_type not in actual_type:
                    issues.append(QualityIssue(
                        severity=QualitySeverity.WARNING.value,
                        category="data_types",
                        message=f"Column '{col}' has type {actual_type} (expected {expected_type})",
                        affected_columns=[col],
                    ))
        
        self.issues.extend(issues)
        return issues
    
    def check_value_ranges(
        self,
        df: pd.DataFrame,
        ranges: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> List[QualityIssue]:
        """
        Check that numeric values fall within expected ranges.
        
        Args:
            df: DataFrame to check
            ranges: Dict of column_name -> (min_value, max_value)
        
        Returns:
            List of QualityIssue objects
        """
        issues = []
        
        if ranges is None:
            return issues
        
        for col, (min_val, max_val) in ranges.items():
            if col not in df.columns:
                continue
            
            col_data = pd.to_numeric(df[col], errors="coerce")
            below_min = (col_data < min_val).sum()
            above_max = (col_data > max_val).sum()
            
            if below_min > 0:
                issues.append(QualityIssue(
                    severity=QualitySeverity.WARNING.value,
                    category="value_ranges",
                    message=f"Column '{col}' has {below_min} values below minimum {min_val}",
                    affected_rows=below_min,
                    affected_columns=[col],
                    value=float(col_data.min()),
                    threshold=float(min_val),
                ))
            
            if above_max > 0:
                issues.append(QualityIssue(
                    severity=QualitySeverity.WARNING.value,
                    category="value_ranges",
                    message=f"Column '{col}' has {above_max} values above maximum {max_val}",
                    affected_rows=above_max,
                    affected_columns=[col],
                    value=float(col_data.max()),
                    threshold=float(max_val),
                ))
        
        self.issues.extend(issues)
        return issues
    
    def check_required_columns(
        self,
        df: pd.DataFrame,
        required_columns: Optional[List[str]] = None,
    ) -> List[QualityIssue]:
        """
        Check that required columns exist.
        
        Args:
            df: DataFrame to check
            required_columns: List of required column names
        
        Returns:
            List of QualityIssue objects
        """
        issues = []
        
        if required_columns is None:
            return issues
        
        missing = set(required_columns) - set(df.columns)
        
        for col in missing:
            issues.append(QualityIssue(
                severity=QualitySeverity.CRITICAL.value,
                category="required_columns",
                message=f"Required column '{col}' is missing",
                affected_columns=[col],
            ))
        
        self.issues.extend(issues)
        return issues
    
    def calculate_score(
        self,
        critical_weight: float = 10.0,
        error_weight: float = 5.0,
        warning_weight: float = 1.0,
        info_weight: float = 0.1,
    ) -> float:
        """
        Calculate overall quality score (0-100).
        
        Scoring: Start at 100, subtract weights based on issue severity.
        
        Args:
            critical_weight: Points deducted per CRITICAL issue
            error_weight: Points deducted per ERROR issue
            warning_weight: Points deducted per WARNING issue
            info_weight: Points deducted per INFO issue
        
        Returns:
            Score between 0 and 100
        """
        score = 100.0
        
        for issue in self.issues:
            if issue.severity == QualitySeverity.CRITICAL.value:
                score -= critical_weight
            elif issue.severity == QualitySeverity.ERROR.value:
                score -= error_weight
            elif issue.severity == QualitySeverity.WARNING.value:
                score -= warning_weight
            elif issue.severity == QualitySeverity.INFO.value:
                score -= info_weight
        
        return max(0.0, min(100.0, score))
    
    def validate(
        self,
        df: pd.DataFrame,
        min_score: float = 80.0,
        **check_kwargs,
    ) -> QualityScore:
        """
        Run all quality checks and return score.
        
        Args:
            df: DataFrame to validate
            min_score: Minimum acceptable quality score (default 80)
            **check_kwargs: Arguments passed to individual check methods
        
        Returns:
            QualityScore object
        """
        from datetime import datetime, timezone
        
        # Run default checks
        self.check_null_values(df, **{k: v for k, v in check_kwargs.items() if k.startswith("null_")})
        self.check_row_count(df, **{k: v for k, v in check_kwargs.items() if k.startswith("row_")})
        self.check_duplicates(df, **{k: v for k, v in check_kwargs.items() if k.startswith("dup_")})
        self.check_numeric_anomalies(df, **{k: v for k, v in check_kwargs.items() if k.startswith("numeric_")})
        
        # Run optional checks if parameters provided
        if "expected_types" in check_kwargs:
            self.check_data_types(df, check_kwargs["expected_types"])
        if "ranges" in check_kwargs:
            self.check_value_ranges(df, check_kwargs["ranges"])
        if "required_columns" in check_kwargs:
            self.check_required_columns(df, check_kwargs["required_columns"])
        
        score = self.calculate_score()
        passed = score >= min_score
        
        quality_result = QualityScore(
            layer=self.layer_name,
            total_rows=len(df),
            total_columns=len(df.columns),
            issues=self.issues,
            overall_score=score,
            passed=passed,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        # Log to audit trail
        self.logger.log(
            "data_quality",
            f"{self.layer_name}_validation",
            score=score,
            passed=passed,
            issue_count=len(self.issues),
            critical_issues=sum(1 for i in self.issues if i.severity == QualitySeverity.CRITICAL.value),
            error_issues=sum(1 for i in self.issues if i.severity == QualitySeverity.ERROR.value),
            warning_issues=sum(1 for i in self.issues if i.severity == QualitySeverity.WARNING.value),
        )
        
        return quality_result
    
    def get_summary(self) -> str:
        """
        Get human-readable summary of quality issues.
        
        Returns:
            Formatted string summary
        """
        if not self.issues:
            return "[OK] No quality issues found"
        
        critical = [i for i in self.issues if i.severity == QualitySeverity.CRITICAL.value]
        errors = [i for i in self.issues if i.severity == QualitySeverity.ERROR.value]
        warnings = [i for i in self.issues if i.severity == QualitySeverity.WARNING.value]
        infos = [i for i in self.issues if i.severity == QualitySeverity.INFO.value]
        
        summary = []
        summary.append(f"\n{'='*70}")
        summary.append(f"Data Quality Report - {self.layer_name.upper()}")
        summary.append(f"{'='*70}")
        
        if critical:
            summary.append(f"\n[CRITICAL] {len(critical)} issues:")
            for issue in critical:
                summary.append(f"  - {issue.message}")
        
        if errors:
            summary.append(f"\n[ERROR] {len(errors)} issues:")
            for issue in errors:
                summary.append(f"  - {issue.message}")
        
        if warnings:
            summary.append(f"\n[WARNING] {len(warnings)} issues:")
            for issue in warnings[:5]:
                summary.append(f"  - {issue.message}")
            if len(warnings) > 5:
                summary.append(f"  ... and {len(warnings) - 5} more")
        
        if infos:
            summary.append(f"\n[INFO] {len(infos)} informational items")
        
        summary.append(f"\n{'='*70}\n")
        
        return "\n".join(summary)
