"""
Pipeline state schema — Pydantic model tracking progress through all pipeline phases.
"""

from typing import Optional

from pydantic import BaseModel, Field


class PipelineState(BaseModel):
    """Structured state for the multi-phase data transformation pipeline."""

    # ── Run Metadata ──────────────────────────────────────────────────────────
    run_id: str = Field(default="", description="Unique identifier for this pipeline run")
    status: str = Field(
        default="initialized",
        description="Current phase: initialized, profiling, mapping, executing, reporting, completed, failed",
    )

    # ── Phase 1: Ingestion ────────────────────────────────────────────────────
    uploaded_files: list[str] = Field(
        default_factory=list,
        description="Paths to uploaded CSV files",
    )
    business_intent: str = Field(
        default="",
        description="User's question or objective in plain English",
    )

    # ── Phase 2: Profiling ────────────────────────────────────────────────────
    profile_path: str = Field(
        default="",
        description="Path to the generated data profile JSON",
    )

    # ── Phase 3: STTM (Source-to-Target Mapping) ─────────────────────────────
    sttm_bronze_path: str = Field(
        default="",
        description="Path to Bronze layer transformation rules",
    )
    sttm_silver_path: str = Field(
        default="",
        description="Path to Silver layer transformation rules",
    )
    sttm_gold_path: str = Field(
        default="",
        description="Path to Gold layer transformation rules",
    )
    hitl_approved: bool = Field(
        default=False,
        description="Whether human reviewed and approved the transformation rules",
    )

    # ── Phase 4: Execution ────────────────────────────────────────────────────
    bronze_output_paths: list[str] = Field(
        default_factory=list,
        description="Paths to Bronze layer Parquet files",
    )
    silver_output_paths: list[str] = Field(
        default_factory=list,
        description="Paths to Silver layer Parquet files",
    )
    gold_output_paths: list[str] = Field(
        default_factory=list,
        description="Paths to Gold layer Parquet files",
    )

    # ── Phase 5: Reporting ────────────────────────────────────────────────────
    report_path: str = Field(
        default="",
        description="Path to the final HTML report",
    )

    # ── Error Handling ────────────────────────────────────────────────────────
    error: Optional[str] = Field(
        default=None,
        description="Error message if pipeline failed",
    )

    class Config:
        """Pydantic config."""
        str_strip_whitespace = True
