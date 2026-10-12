"""
Silver agent — cleanses Bronze data: handles nulls, deduplicates, standardizes types and text.
"""

import json
from datetime import datetime, timezone
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
    SILVER_DIR,
)
from core.observability import AgentTrace


# ─── System Prompt ──────────────────────────────────────────────────────────
SILVER_AGENT_PROMPT = """You are a Data Engineer responsible for Silver layer cleansing.

Your task: transform Bronze data into clean, standardized Silver data.

CRITICAL: You MUST call both tools in sequence:
1. Call inspect_task_tool first to preview the Bronze Parquet files and STTM rules
2. Then call silver_ingestion_tool to execute the cleansing and transformation

Planning without executing is FAILURE. Always execute by calling the tools.
"""


# ─── Helper Functions (Pure Python) ─────────────────────────────────────────

def _inspect_task(input_files: list[str], sttm_path: str) -> dict:
    """Preview Bronze Parquet schemas and STTM rules."""
    result = {"input_files": {}, "sttm_rules": {}}

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
        result["sttm_rules"] = {
            "rows": len(sttm_df),
            "columns": list(sttm_df.columns),
            "sample_mappings": sttm_df.head(3).to_dict(orient="records"),
        }
    except Exception as e:
        result["sttm_rules"]["error"] = str(e)

    return result


def _normalize_column_name(col: str) -> str:
    """Normalize column name for flexible matching."""
    return col.lower().strip().replace(" ", "_")


def _apply_silver_rules(
    input_files: list[str],
    sttm_path: str,
    run_id: str,
) -> list[str]:
    """Apply Silver layer rules: nulls, deduplication, type casting, text normalization."""
    output_paths = []

    try:
        sttm_df = pd.read_csv(sttm_path)
        sttm_df.columns = [_normalize_column_name(col) for col in sttm_df.columns]
    except Exception as e:
        raise ValueError(f"Failed to read STTM file: {e}")

    for input_file in input_files:
        try:
            df = pd.read_parquet(input_file)
            original_rows = len(df)

            # Build rename mapping from STTM
            rename_map = {}
            for _, row in sttm_df.iterrows():
                source_col = str(row.get("source_column", "")).strip()
                target_col = str(row.get("target_column", "")).strip()
                if source_col and target_col and source_col in df.columns:
                    rename_map[source_col] = target_col

            # Apply renames
            df.rename(columns=rename_map, inplace=True)

            # Apply transformations based on STTM rules
            for _, row in sttm_df.iterrows():
                target_col = str(row.get("target_column", "")).strip()
                transform_type = str(row.get("transformation_type", "")).lower()
                transform_logic = str(row.get("transformation_logic", "")).lower()

                if target_col not in df.columns:
                    continue

                # Handle nulls
                if "drop" in transform_logic or "remove_null" in transform_logic:
                    df[target_col] = df[target_col].dropna()
                elif "fill_mean" in transform_logic or "mean" in transform_logic:
                    if pd.api.types.is_numeric_dtype(df[target_col]):
                        df[target_col].fillna(df[target_col].mean(), inplace=True)
                elif "fill_median" in transform_logic or "median" in transform_logic:
                    if pd.api.types.is_numeric_dtype(df[target_col]):
                        df[target_col].fillna(df[target_col].median(), inplace=True)
                elif "fill_mode" in transform_logic or "mode" in transform_logic:
                    mode_val = df[target_col].mode()
                    if len(mode_val) > 0:
                        df[target_col].fillna(mode_val[0], inplace=True)
                elif "fill_" in transform_logic:
                    fill_val = transform_logic.split("fill_")[-1].strip()
                    df[target_col].fillna(fill_val, inplace=True)

                # Type casting
                if transform_type in ("numeric", "number", "float", "int"):
                    try:
                        df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
                    except Exception:
                        pass

                elif transform_type in ("date", "datetime", "timestamp"):
                    try:
                        df[target_col] = pd.to_datetime(df[target_col], errors="coerce")
                        df[target_col] = df[target_col].dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                # Text normalization
                if "lowercase" in transform_logic:
                    df[target_col] = df[target_col].astype(str).str.lower()
                elif "uppercase" in transform_logic:
                    df[target_col] = df[target_col].astype(str).str.upper()
                elif "titlecase" in transform_logic or "title_case" in transform_logic:
                    df[target_col] = df[target_col].astype(str).str.title()

                if "trim" in transform_logic or "strip" in transform_logic:
                    df[target_col] = df[target_col].astype(str).str.strip()

            # Deduplication
            df_dedup = df.drop_duplicates()
            dedup_removed = len(df) - len(df_dedup)
            df = df_dedup

            # Extract table name for surrogate key
            file_stem = Path(input_file).stem.replace("_bronze", "")
            surrogate_key_col = f"pk_{file_stem}_silver_id"

            # Inject surrogate key as first column
            df.insert(0, surrogate_key_col, range(1, len(df) + 1))

            # Filter to approved columns (those mapped in STTM)
            approved_cols = [surrogate_key_col] + [
                col for col in df.columns
                if col in sttm_df["target_column"].values or col.startswith("_")
            ]
            df = df[[col for col in approved_cols if col in df.columns]]

            # Write to Silver as Parquet
            output_file = SILVER_DIR / f"{file_stem}_silver.parquet"
            df.to_parquet(output_file, index=False)
            output_paths.append(str(output_file))

            # Log action
            logger = AuditLogger(run_id)
            logger.log(
                "silver_agent",
                "cleanse_file",
                input_file=input_file,
                output_file=str(output_file),
                original_rows=original_rows,
                final_rows=len(df),
                rows_deduped=dedup_removed,
                columns=len(df.columns),
            )

        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log(
                "silver_agent",
                "cleanse_file_error",
                input_file=input_file,
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

def _make_silver_tools(input_files: list[str], sttm_path: str, run_id: str):
    """Create tools for the Silver agent."""

    @tool
    def inspect_task_tool() -> str:
        """Preview Bronze Parquet files and STTM rules."""
        result = _inspect_task(input_files, sttm_path)
        logger = AuditLogger(run_id)
        logger.log("silver_agent", "inspect_task", result=result)
        return json.dumps(result, indent=2, default=str)

    @tool
    def silver_ingestion_tool() -> str:
        """Execute Silver layer cleansing: apply STTM rules and standardize data."""
        output_paths = _apply_silver_rules(input_files, sttm_path, run_id)
        result = {
            "status": "success",
            "output_files": output_paths,
            "count": len(output_paths),
        }
        logger = AuditLogger(run_id)
        logger.log("silver_agent", "silver_ingestion", result=result)
        return json.dumps(result, indent=2, default=str)

    return [inspect_task_tool, silver_ingestion_tool]


# ─── Public Entry Point ─────────────────────────────────────────────────────

def execute_silver(
    input_files: list[str],
    sttm_path: str,
    run_id: str,
    task_description: str = "",
) -> list[str]:
    """
    Execute Silver layer cleansing via AI agent.
    Returns list of output Parquet file paths.
    """
    from langgraph.prebuilt import create_react_agent

    trace = AgentTrace("silver_agent", run_id)
    trace.set_input(input_files=input_files, sttm_path=sttm_path)
    trace.set_plan("Inspect task → Apply Silver rules → Cleanse and standardize → Load to Parquet")

    try:
        llm = _make_llm()
        tools = _make_silver_tools(input_files, sttm_path, run_id)

        agent = create_react_agent(llm, tools, state_modifier=SILVER_AGENT_PROMPT)

        input_msg = (
            f"Execute Silver layer cleansing for files: {input_files}. "
            f"Use STTM rules from: {sttm_path}. {task_description}"
        )
        result = agent.invoke({"messages": [("user", input_msg)]})

        output_files = _apply_silver_rules(input_files, sttm_path, run_id)
        trace.set_output(output_files=output_files)
        trace.complete(status="success")

        return output_files

    except Exception as e:
        trace.fail(str(e))
        raise
