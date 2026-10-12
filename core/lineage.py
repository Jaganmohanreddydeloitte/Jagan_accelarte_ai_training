"""
Data lineage tracking system for IDAMP pipeline.

Tracks data flow from source files through Bronze, Silver, Gold layers
with column-level lineage and transformation details.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, asdict, field
from uuid import uuid4

from core.config import GOLD_DIR


@dataclass
class ColumnLineage:
    """Track lineage of a single column."""
    name: str
    source_file: Optional[str] = None
    source_column: Optional[str] = None
    transformations: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class StageLineage:
    """Track lineage for a processing stage."""
    stage_name: str  # "bronze", "silver", "gold"
    input_files: List[str] = field(default_factory=list)
    output_file: str = ""
    columns: List[ColumnLineage] = field(default_factory=list)
    transformations: List[str] = field(default_factory=list)
    row_count: int = 0
    timestamp: str = ""
    sttm_applied: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineLineage:
    """Complete lineage for a pipeline run."""
    run_id: str
    business_intent: str
    source_files: List[str] = field(default_factory=list)
    stages: List[StageLineage] = field(default_factory=list)
    created_at: str = ""
    completed_at: Optional[str] = None


class LineageTracker:
    """Track and manage data lineage through pipeline stages."""
    
    def __init__(self, run_id: str, business_intent: str = ""):
        """
        Initialize lineage tracker.
        
        Args:
            run_id: Unique run identifier
            business_intent: User's business question/intent
        """
        self.run_id = run_id
        self.lineage = PipelineLineage(
            run_id=run_id,
            business_intent=business_intent,
            created_at=datetime.now().isoformat()
        )
        self.lineage_dir = Path("data/lineage")
        self.lineage_dir.mkdir(parents=True, exist_ok=True)
    
    def track_source_files(self, file_paths: List[str], file_profiles: Dict[str, Any]):
        """
        Record source files and their schemas.
        
        Args:
            file_paths: List of source file paths
            file_profiles: Profile data for each file (from profiler)
        """
        self.lineage.source_files = file_paths
        
        for file_path in file_paths:
            profile = file_profiles.get(file_path, {})
            columns = profile.get("columns", [])
            
            # Create initial column lineage from source
            for col_info in columns:
                col_name = col_info.get("name", "")
                col_lineage = ColumnLineage(
                    name=col_name,
                    source_file=file_path,
                    source_column=col_name,
                    description=col_info.get("type", "")
                )
                # Store in first stage temporarily
                if not self.lineage.stages:
                    self.lineage.stages.append(StageLineage("source"))
                self.lineage.stages[0].columns.append(col_lineage)
    
    def start_stage(self, stage_name: str, input_files: List[str]) -> 'StageLineage':
        """
        Record start of a processing stage.
        
        Args:
            stage_name: "bronze", "silver", or "gold"
            input_files: Input file paths for this stage
            
        Returns:
            StageLineage object for tracking
        """
        stage = StageLineage(
            stage_name=stage_name,
            input_files=input_files,
            timestamp=datetime.now().isoformat()
        )
        self.lineage.stages.append(stage)
        return stage
    
    def add_transformation(
        self,
        stage_name: str,
        transformation: str,
        input_columns: List[str] = None,
        output_columns: List[str] = None
    ):
        """
        Record a transformation applied during a stage.
        
        Args:
            stage_name: Stage where transformation occurred
            transformation: Description of transformation (e.g., "Filter rows where amount > 1000")
            input_columns: Columns used in transformation
            output_columns: Columns produced by transformation
        """
        stage = self._get_stage(stage_name)
        if stage:
            stage.transformations.append(transformation)
            
            # Update column lineage
            if input_columns and output_columns:
                for output_col in output_columns:
                    # Find or create column
                    col = self._find_or_create_column(stage, output_col)
                    col.transformations.append(transformation)
    
    def add_sttm_rules(self, stage_name: str, sttm_rules: Dict[str, Any]):
        """
        Record STTM rules applied in a stage.
        
        Args:
            stage_name: Stage where STTM was applied
            sttm_rules: STTM rules dictionary
        """
        stage = self._get_stage(stage_name)
        if stage:
            stage.sttm_applied = sttm_rules
    
    def complete_stage(
        self,
        stage_name: str,
        output_file: str,
        row_count: int,
        output_columns: List[str] = None
    ):
        """
        Record completion of a stage.
        
        Args:
            stage_name: Completed stage name
            output_file: Output file path
            row_count: Number of rows in output
            output_columns: List of output column names
        """
        stage = self._get_stage(stage_name)
        if stage:
            stage.output_file = output_file
            stage.row_count = row_count
            
            # Ensure all output columns are tracked
            if output_columns:
                for col_name in output_columns:
                    self._find_or_create_column(stage, col_name)
    
    def save(self) -> Path:
        """
        Save lineage to JSON file.
        
        Returns:
            Path to saved lineage file
        """
        self.lineage.completed_at = datetime.now().isoformat()
        
        file_path = self.lineage_dir / f"lineage_{self.run_id}.json"
        
        with open(file_path, "w") as f:
            json.dump(asdict(self.lineage), f, indent=2)
        
        return file_path
    
    def get_column_source(self, column_name: str) -> Optional[Dict[str, Any]]:
        """
        Trace back column to its source.
        
        Args:
            column_name: Column to trace
            
        Returns:
            Dictionary with source file and original column name
        """
        for stage in self.lineage.stages:
            for col in stage.columns:
                if col.name == column_name:
                    return {
                        "stage": stage.stage_name,
                        "column_name": col.name,
                        "source_file": col.source_file,
                        "source_column": col.source_column,
                        "transformations": col.transformations
                    }
        return None
    
    def get_stage_transformations(self, stage_name: str) -> List[str]:
        """Get all transformations applied in a stage."""
        stage = self._get_stage(stage_name)
        return stage.transformations if stage else []
    
    def get_data_flow_summary(self) -> Dict[str, Any]:
        """Get summary of data flow through pipeline."""
        return {
            "run_id": self.run_id,
            "business_intent": self.lineage.business_intent,
            "source_files": self.lineage.source_files,
            "stages": [
                {
                    "name": stage.stage_name,
                    "input_files": stage.input_files,
                    "output_file": stage.output_file,
                    "row_count": stage.row_count,
                    "column_count": len(stage.columns),
                    "transformation_count": len(stage.transformations),
                }
                for stage in self.lineage.stages
            ],
            "total_transformations": sum(len(s.transformations) for s in self.lineage.stages),
        }
    
    def _get_stage(self, stage_name: str) -> Optional[StageLineage]:
        """Find stage by name."""
        for stage in self.lineage.stages:
            if stage.stage_name == stage_name:
                return stage
        return None
    
    def _find_or_create_column(self, stage: StageLineage, col_name: str) -> ColumnLineage:
        """Find existing column or create new one."""
        for col in stage.columns:
            if col.name == col_name:
                return col
        
        # Create new column lineage
        new_col = ColumnLineage(name=col_name)
        stage.columns.append(new_col)
        return new_col


def load_lineage(run_id: str) -> Optional[PipelineLineage]:
    """
    Load lineage from saved file.
    
    Args:
        run_id: Run ID to load
        
    Returns:
        Loaded PipelineLineage or None if not found
    """
    lineage_file = Path("data/lineage") / f"lineage_{run_id}.json"
    
    if not lineage_file.exists():
        return None
    
    with open(lineage_file, "r") as f:
        data = json.load(f)
    
    # Reconstruct dataclass from dict
    lineage = PipelineLineage(**data)
    return lineage
