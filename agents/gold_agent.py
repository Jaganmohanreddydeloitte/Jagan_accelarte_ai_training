"""
Gold agent — creates analytics-ready Gold tables: joins, aggregations, and business shapes.
"""

import json
from pathlib import Path

import pandas as pd
from langchain_core.tools import tool

from core.audit import AuditLogger
from core.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GOOGLE_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    GOLD_DIR,
)
from core.observability import AgentTrace


# ─── System Prompt ──────────────────────────────────────────────────────────
GOLD_AGENT_PROMPT = """You are a Business Intelligence Engineer responsible for Gold layer analytics.

Your task: transform Silver data into analytics-ready Gold tables with joins and aggregations.

CRITICAL: You MUST call both tools in sequence:
1. Call inspect_task_tool first to preview the Silver Parquet files and Gold STTM rules
2. Then call gold_ingestion_tool to execute the joins, aggregations, and table creation

Planning without executing is FAILURE. Always execute by calling the tools.
"""


# ─── Helper Functions (Pure Python) ─────────────────────────────────────────

def _inspect_task(input_files: list[str], sttm_path: str) -> dict:
    """Preview Silver Parquet schemas and Gold STTM rules grouped by target table."""
    result = {"input_files": {}, "sttm_rules_by_table": {}}

    for fpath in input_files:
        try:
            df = pd.read_parquet(fpath)
            result["input_files"][fpath] = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            }
        except Exception as e:
            result["input_files"][fpath] = {"error": str(e)}

    try:
        sttm_df = pd.read_csv(sttm_path)
        for target_table, group in sttm_df.groupby("target_table"):
            result["sttm_rules_by_table"][target_table] = {
                "rows": len(group),
                "columns": list(group.columns),
                "sample_mappings": group.head(3).to_dict(orient="records"),
            }
    except Exception as e:
        result["sttm_rules"]["error"] = str(e)

    return result


def _normalize_column_name(col: str) -> str:
    """Normalize column name for flexible matching."""
    return col.lower().strip().replace(" ", "_")


def _apply_gold_rules(
    input_files: list[str],
    sttm_path: str,
    run_id: str,
) -> list[str]:
    """Apply Gold layer rules: joins, aggregations, business shapes."""
    output_paths = []

    # Load all Silver Parquet files
    silver_dfs = {}
    for input_file in input_files:
        try:
            df = pd.read_parquet(input_file)
            file_stem = Path(input_file).stem.replace("_silver", "")
            silver_dfs[file_stem] = df
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log(
                "gold_agent",
                "load_silver_error",
                input_file=input_file,
                error=str(e),
            )
            raise

    # Read and normalize STTM
    try:
        sttm_df = pd.read_csv(sttm_path)
        sttm_df.columns = [_normalize_column_name(col) for col in sttm_df.columns]
    except Exception as e:
        raise ValueError(f"Failed to read STTM file: {e}")

    # Group STTM rules by target_table
    for target_table, group in sttm_df.groupby("target_table"):
        try:
            # Get unique source tables for this target
            source_tables = group["source_table"].unique()
            source_tables = [st for st in source_tables if pd.notna(st) and st in silver_dfs]

            if not source_tables:
                continue

            # Start with first source DataFrame
            result_df = silver_dfs[source_tables[0]].copy()

            # Join additional sources on _id columns (outer join)
            for source_table in source_tables[1:]:
                join_df = silver_dfs[source_table]

                # Find common ID columns
                join_cols = [
                    col for col in result_df.columns
                    if col.endswith("_id") and col in join_df.columns
                ]
                if join_cols:
                    result_df = pd.merge(
                        result_df,
                        join_df,
                        on=join_cols,
                        how="outer",
                        suffixes=("", f"_{source_table}"),
                    )

            # Apply column renames from STTM
            rename_map = {}
            for _, row in group.iterrows():
                source_col = str(row.get("source_column", "")).strip()
                target_col = str(row.get("target_column", "")).strip()
                if source_col and target_col and source_col in result_df.columns:
                    rename_map[source_col] = target_col

            result_df.rename(columns=rename_map, inplace=True)

            # Apply aggregations if specified
            for _, row in group.iterrows():
                agg_type = str(row.get("transformation_type", "")).lower()
                agg_logic = str(row.get("transformation_logic", "")).lower()
                target_col = str(row.get("target_column", "")).strip()

                if target_col not in result_df.columns:
                    continue

                if "groupby" in agg_logic:
                    groupby_col = agg_logic.split("groupby")[-1].strip()
                    if groupby_col in result_df.columns:
                        if "sum" in agg_logic:
                            result_df = result_df.groupby(groupby_col)[target_col].sum().reset_index()
                        elif "avg" in agg_logic or "mean" in agg_logic:
                            result_df = result_df.groupby(groupby_col)[target_col].mean().reset_index()
                        elif "count" in agg_logic:
                            result_df = result_df.groupby(groupby_col)[target_col].count().reset_index()
                        elif "max" in agg_logic:
                            result_df = result_df.groupby(groupby_col)[target_col].max().reset_index()
                        elif "min" in agg_logic:
                            result_df = result_df.groupby(groupby_col)[target_col].min().reset_index()

            # Filter to approved columns (those in this STTM group)
            approved_cols = [
                col for col in group["target_column"].values
                if col in result_df.columns
            ]
            result_df = result_df[[col for col in approved_cols if col in result_df.columns]]

            # Inject surrogate key as first column
            result_df.insert(0, "pk_gold_id", range(1, len(result_df) + 1))

            # Write to Gold as Parquet
            output_file = GOLD_DIR / f"{target_table}.parquet"
            result_df.to_parquet(output_file, index=False)
            output_paths.append(str(output_file))

            # Log action
            logger = AuditLogger(run_id)
            logger.log(
                "gold_agent",
                "create_gold_table",
                target_table=target_table,
                output_file=str(output_file),
                source_tables=list(source_tables),
                rows=len(result_df),
                columns=len(result_df.columns),
            )

        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log(
                "gold_agent",
                "create_gold_table_error",
                target_table=target_table,
                error=str(e),
            )
            raise

    return output_paths


# ─── LLM Factory ────────────────────────────────────────────────────────────

def _make_llm():
    """Create LLM based on LLM_PROVIDER setting."""
    if LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
            reasoning_format="hidden",
            reasoning_effort="low",
        )
    elif LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
        )
    elif LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            api_key=GOOGLE_API_KEY,
            model=GEMINI_MODEL,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")


# ─── Tool Factory ───────────────────────────────────────────────────────────

def _make_gold_tools(input_files: list[str], sttm_path: str, run_id: str):
    """Create tools for the Gold agent."""

    @tool
    def inspect_task_tool() -> str:
        """Preview Silver Parquet files and Gold STTM rules grouped by target table."""
        result = _inspect_task(input_files, sttm_path)
        logger = AuditLogger(run_id)
        logger.log("gold_agent", "inspect_task", result=result)
        return json.dumps(result, indent=2, default=str)

    @tool
    def gold_ingestion_tool() -> str:
        """Execute Gold layer analytics: joins, aggregations, and table creation."""
        output_paths = _apply_gold_rules(input_files, sttm_path, run_id)
        result = {
            "status": "success",
            "output_files": output_paths,
            "count": len(output_paths),
        }
        logger = AuditLogger(run_id)
        logger.log("gold_agent", "gold_ingestion", result=result)
        return json.dumps(result, indent=2, default=str)

    return [inspect_task_tool, gold_ingestion_tool]


# ─── Public Entry Point ─────────────────────────────────────────────────────

def execute_gold(
    input_files: list[str],
    sttm_path: str,
    run_id: str,
    task_description: str = "",
) -> list[str]:
    """
    Execute Gold layer analytics via AI agent.
    Returns list of output Parquet file paths.
    Optionally exports to PostgreSQL if configured.
    """
    from langgraph.prebuilt import create_react_agent

    trace = AgentTrace("gold_agent", run_id)
    trace.set_input(input_files=input_files, sttm_path=sttm_path)
    trace.set_plan("Inspect task → Apply Gold rules → Join and aggregate → Load to Parquet → Export to PostgreSQL")

    logger = AuditLogger(run_id)

    try:
        llm = _make_llm()
        tools = _make_gold_tools(input_files, sttm_path, run_id)

        agent = create_react_agent(llm, tools, state_modifier=GOLD_AGENT_PROMPT)

        input_msg = (
            f"Execute Gold layer analytics for files: {input_files}. "
            f"Use STTM rules from: {sttm_path}. {task_description}"
        )
        result = agent.invoke({"messages": [("user", input_msg)]})

        output_files = _apply_gold_rules(input_files, sttm_path, run_id)
        
        # ────────────────────────────────────────────────────────────────
        # NEW: Export to PostgreSQL if enabled
        # ────────────────────────────────────────────────────────────────
        logger.log("gold_agent", "postgres_export_start", table_count=len(output_files))
        
        try:
            from core.postgres_exporter import export_gold_to_postgres
            
            export_results = export_gold_to_postgres(run_id, output_files)
            
            # Log results
            successful = sum(1 for v in export_results.values() if v)
            logger.log(
                "gold_agent",
                "postgres_export_complete",
                successful=successful,
                total=len(export_results),
            )
        
        except Exception as postgres_error:
            # Log but don't fail - PostgreSQL is optional
            logger.log(
                "gold_agent",
                "postgres_export_error",
                error=str(postgres_error),
            )
            print(f"[WARN] PostgreSQL export failed (non-fatal): {postgres_error}")
        
        trace.set_output(output_files=output_files)
        trace.complete(status="success")

        return output_files

    except Exception as e:
        trace.fail(str(e))
        raise
