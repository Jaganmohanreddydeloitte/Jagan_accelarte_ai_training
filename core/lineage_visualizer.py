"""
Data lineage visualization - creates Mermaid diagrams for pipeline flow.

Generates interactive diagrams showing data flow, transformations, and column lineage.
"""

from typing import Dict, List, Any, Optional
from core.lineage import PipelineLineage, LineageTracker


class LineageVisualizer:
    """Generate Mermaid diagrams for data lineage visualization."""
    
    def __init__(self, lineage: PipelineLineage):
        """
        Initialize visualizer with lineage data.
        
        Args:
            lineage: PipelineLineage object to visualize
        """
        self.lineage = lineage
    
    def generate_flow_diagram(self) -> str:
        """
        Generate Mermaid flow diagram showing data path through pipeline.
        
        Shows: Source Files → Bronze → Silver → Gold → Report
        
        Returns:
            Mermaid diagram as string
        """
        lines = ["graph LR"]
        lines.append("    classDef sourceStyle fill:#e1f5e1,stroke:#27ae60,stroke-width:2px")
        lines.append("    classDef bronzeStyle fill:#ffe1e1,stroke:#e74c3c,stroke-width:2px")
        lines.append("    classDef silverStyle fill:#e1e5ff,stroke:#3498db,stroke-width:2px")
        lines.append("    classDef goldStyle fill:#fff9e1,stroke:#f39c12,stroke-width:2px")
        lines.append("    classDef reportStyle fill:#f1e1ff,stroke:#9b59b6,stroke-width:2px")
        lines.append("")
        
        # Add source files
        source_count = len(self.lineage.source_files)
        if source_count == 1:
            lines.append(f"    SRC['{self.lineage.source_files[0].split('/')[-1]}']")
        else:
            for i, f in enumerate(self.lineage.source_files):
                filename = f.split('/')[-1]
                lines.append(f"    SRC{i}['{filename}']")
        
        # Add stages
        for stage in self.lineage.stages:
            if stage.stage_name == "source":
                continue
            
            stage_upper = stage.stage_name.upper()
            row_count = f"<br/>{stage.row_count:,} rows" if stage.row_count else ""
            col_count = f"<br/>{len(stage.columns)} cols" if stage.columns else ""
            
            label = f"{stage_upper} Layer{row_count}{col_count}"
            lines.append(f"    {stage_upper}['{label}']")
        
        # Add report stage
        lines.append("    REPORT['Executive<br/>Report']")
        
        # Add connections
        if source_count == 1:
            lines.append("    SRC --> BRONZE")
        else:
            src_list = " & ".join([f"SRC{i}" for i in range(source_count)])
            lines.append(f"    {src_list} --> BRONZE")
        
        # Chain stages
        lines.append("    BRONZE --> SILVER")
        lines.append("    SILVER --> GOLD")
        lines.append("    GOLD --> REPORT")
        
        # Apply styles
        lines.append("")
        lines.append("    class SRC sourceStyle")
        lines.append("    class BRONZE bronzeStyle")
        lines.append("    class SILVER silverStyle")
        lines.append("    class GOLD goldStyle")
        lines.append("    class REPORT reportStyle")
        
        return "\n".join(lines)
    
    def generate_transformation_diagram(self) -> str:
        """
        Generate Mermaid diagram showing transformations at each stage.
        
        Shows: Stage name, transformations applied, row counts
        
        Returns:
            Mermaid diagram as string
        """
        lines = ["graph TD"]
        lines.append("    classDef stageBox fill:#e8f4f8,stroke:#2c3e50,stroke-width:2px")
        lines.append("    classDef transformBox fill:#fff5e6,stroke:#d35400,stroke-width:1px")
        lines.append("")
        
        node_id = 0
        prev_stage_id = None
        
        for stage in self.lineage.stages:
            if stage.stage_name == "source":
                continue
            
            # Stage node
            stage_label = f"{stage.stage_name.upper()}<br/>({stage.row_count} rows)"
            stage_id = f"STAGE{node_id}"
            lines.append(f"    {stage_id}[\"{stage_label}\"]")
            node_id += 1
            
            # Connect from previous stage
            if prev_stage_id:
                lines.append(f"    {prev_stage_id} --> {stage_id}")
            
            # Add transformations
            for i, transform in enumerate(stage.transformations[:3]):  # Show top 3
                transform_label = transform[:50] + "..." if len(transform) > 50 else transform
                transform_id = f"TRANS{node_id}"
                lines.append(f"    {transform_id}['{transform_label}']")
                lines.append(f"    {stage_id} --> {transform_id}")
                node_id += 1
            
            if len(stage.transformations) > 3:
                more_id = f"MORE{node_id}"
                lines.append(f"    {more_id}['+{len(stage.transformations) - 3} more...']")
                lines.append(f"    {stage_id} --> {more_id}")
                node_id += 1
            
            prev_stage_id = stage_id
        
        # Apply styles
        lines.append("")
        for i in range(node_id):
            if f"STAGE{i}" in "\n".join(lines):
                lines.append(f"    class STAGE{i} stageBox")
        
        return "\n".join(lines)
    
    def generate_column_lineage_diagram(self, target_column: str) -> str:
        """
        Generate Mermaid diagram showing lineage for a specific column.
        
        Traces column back to source and shows all transformations.
        
        Args:
            target_column: Column name to trace
            
        Returns:
            Mermaid diagram as string
        """
        lines = ["graph LR"]
        lines.append("    classDef sourceCol fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px")
        lines.append("    classDef transformCol fill:#fff9c4,stroke:#f57f17,stroke-width:2px")
        lines.append("    classDef targetCol fill:#c5cae9,stroke:#283593,stroke-width:2px")
        lines.append("")
        
        node_id = 0
        
        # Find column through stages
        column_path = []
        for stage in self.lineage.stages:
            for col in stage.columns:
                if col.name == target_column:
                    column_path.append({
                        "stage": stage.stage_name,
                        "column": col,
                        "row_count": stage.row_count
                    })
        
        if not column_path:
            return "graph LR\n    NOTFOUND['Column not found in lineage']"
        
        # Add source node
        first = column_path[0]
        source_label = f"Source<br/>{first['column'].source_column}<br/>({first['column'].source_file.split('/')[-1]})"
        lines.append(f"    NODE0[\"{source_label}\"]")
        prev_id = "NODE0"
        node_id = 1
        
        # Add transformation nodes
        for item in column_path:
            for transform in item['column'].transformations:
                transform_label = transform[:40] + "..." if len(transform) > 40 else transform
                node_name = f"NODE{node_id}"
                lines.append(f"    {node_name}['{transform_label}']")
                lines.append(f"    {prev_id} --> {node_name}")
                prev_id = node_name
                node_id += 1
        
        # Add final column node
        final_stage = column_path[-1]['stage'].upper()
        final_label = f"{final_stage}<br/>{target_column}"
        final_id = f"NODE{node_id}"
        lines.append(f"    {final_id}[\"{final_label}\"]")
        lines.append(f"    {prev_id} --> {final_id}")
        
        # Apply styles
        lines.append("")
        lines.append("    class NODE0 sourceCol")
        lines.append(f"    class {final_id} targetCol")
        
        return "\n".join(lines)
    
    def generate_table_diagram(self) -> str:
        """
        Generate table showing data at each stage.
        
        Returns:
            Markdown table as string
        """
        lines = ["| Stage | Input Files | Output File | Rows | Columns | Transformations |"]
        lines.append("|-------|-------------|-------------|------|---------|-----------------|")
        
        for stage in self.lineage.stages:
            if stage.stage_name == "source":
                continue
            
            input_files = ", ".join([f.split('/')[-1] for f in stage.input_files])
            output_file = stage.output_file.split('/')[-1] if stage.output_file else "N/A"
            row_count = f"{stage.row_count:,}" if stage.row_count else "0"
            col_count = len(stage.columns)
            transform_count = len(stage.transformations)
            
            lines.append(
                f"| {stage.stage_name} | {input_files} | {output_file} | {row_count} | {col_count} | {transform_count} |"
            )
        
        return "\n".join(lines)
    
    def generate_summary_text(self) -> str:
        """
        Generate text summary of lineage.
        
        Returns:
            Text summary
        """
        summary = []
        summary.append("# Data Lineage Summary\n")
        summary.append(f"**Run ID:** {self.lineage.run_id}\n")
        summary.append(f"**Business Intent:** {self.lineage.business_intent}\n")
        summary.append(f"**Created:** {self.lineage.created_at}\n\n")
        
        summary.append("## Source Files\n")
        for file in self.lineage.source_files:
            filename = file.split('/')[-1]
            summary.append(f"- {filename}")
        summary.append("\n")
        
        summary.append("## Pipeline Stages\n")
        for stage in self.lineage.stages:
            if stage.stage_name == "source":
                continue
            
            summary.append(f"### {stage.stage_name.upper()} Layer\n")
            summary.append(f"- **Input:** {', '.join([f.split('/')[-1] for f in stage.input_files])}\n")
            summary.append(f"- **Output:** {stage.output_file.split('/')[-1] if stage.output_file else 'N/A'}\n")
            summary.append(f"- **Rows:** {stage.row_count:,}\n")
            summary.append(f"- **Columns:** {len(stage.columns)}\n")
            
            if stage.transformations:
                summary.append(f"- **Transformations:**\n")
                for transform in stage.transformations:
                    summary.append(f"  - {transform}\n")
            summary.append("\n")
        
        return "".join(summary)


def create_lineage_diagram(lineage: PipelineLineage, diagram_type: str = "flow") -> str:
    """
    Create Mermaid diagram from lineage.
    
    Args:
        lineage: PipelineLineage object
        diagram_type: Type of diagram ("flow", "transformation", "table", "summary")
        
    Returns:
        Mermaid diagram or summary text
    """
    visualizer = LineageVisualizer(lineage)
    
    if diagram_type == "flow":
        return visualizer.generate_flow_diagram()
    elif diagram_type == "transformation":
        return visualizer.generate_transformation_diagram()
    elif diagram_type == "table":
        return visualizer.generate_table_diagram()
    elif diagram_type == "summary":
        return visualizer.generate_summary_text()
    else:
        return visualizer.generate_flow_diagram()
