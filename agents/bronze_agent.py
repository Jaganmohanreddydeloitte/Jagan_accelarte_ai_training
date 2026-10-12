"""
Bronze agent — loads raw CSV files into the Bronze layer with minimal transformation plus metadata.
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
    BRONZE_DIR,
)
from core.observability import AgentTrace


# ─── System Prompt ──────────────────────────────────────────────────────────
BRONZE_AGENT_PROMPT = """You are a Data Engineer responsible for Bronze layer ingestion.

Your task: load raw CSV files into the Bronze layer with minimal changes and metadata.

CRITICAL: You MUST call both tools in sequence:
1. Call inspect_task_tool first to preview the files and STTM rules
2. Then call bronze_ingestion_tool to execute the ingestion

Planning without executing is FAILURE. Always execute by calling the tools.
"""


# ─── Helper Functions (Pure Python) ─────────────────────────────────────────

def _inspect_task(input_files: list[str], sttm_path: str) -> dict:
    """Preview input CSV shapes and STTM rules."""
    result = {"input_files": {}, "sttm_rules": {}}

    for fpath in input_files:
        try:
            df = pd.read_csv(fpath)
            result["input_files"][fpath] = {
                "shape": df.shape,
                "columns": list(df.columns),
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


def _apply_bronze_rules(
    input_files: list[str],
    sttm_path: str,
    run_id: str,
) -> list[str]:
    """Apply Bronze layer rules: column renames, type casts, metadata."""
    output_paths = []
    load_timestamp = datetime.now(timezone.utc).isoformat()

    try:
        sttm_df = pd.read_csv(sttm_path)
    except Exception as e:
        raise ValueError(f"Failed to read STTM file: {e}")

    for input_file in input_files:
        try:
            df = pd.read_csv(input_file)

            # Build rename mapping from STTM (source_column -> target_column)
            rename_map = {}
            for _, row in sttm_df.iterrows():
                source_col = row.get("source_column", "")
                target_col = row.get("target_column", "")
                if source_col and target_col and source_col in df.columns:
                    rename_map[source_col] = target_col

            # Apply renames
            df.rename(columns=rename_map, inplace=True)

            # Apply type casts based on transformation_type
            for _, row in sttm_df.iterrows():
                target_col = row.get("target_column", "")
                transform_type = row.get("transformation_type", "").lower()

                if target_col not in df.columns:
                    continue

                if transform_type in ("numeric", "number", "float", "int"):
                    try:
                        df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
                    except Exception:
                        pass

                elif transform_type in ("date", "datetime", "timestamp"):
                    try:
                        df[target_col] = pd.to_datetime(df[target_col], errors="coerce")
                    except Exception:
                        pass

                elif transform_type in ("string", "text", "categorical"):
                    df[target_col] = df[target_col].astype(str)

            # Add metadata columns
            df["_load_timestamp"] = load_timestamp
            df["_source_file"] = str(input_file)

            # Write to Bronze as Parquet
            file_stem = Path(input_file).stem
            output_file = BRONZE_DIR / f"{file_stem}_bronze.parquet"
            df.to_parquet(output_file, index=False)
            output_paths.append(str(output_file))

            # Log action
            logger = AuditLogger(run_id)
            logger.log(
                "bronze_agent",
                "ingest_file",
                input_file=input_file,
                output_file=str(output_file),
                rows=len(df),
                columns=len(df.columns),
            )

        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log(
                "bronze_agent",
                "ingest_file_error",
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

def _make_bronze_tools(input_files: list[str], sttm_path: str, run_id: str):
    """Create tools for the Bronze agent."""

    @tool
    def inspect_task_tool() -> str:
        """Preview input CSV files and STTM rules."""
        result = _inspect_task(input_files, sttm_path)
        logger = AuditLogger(run_id)
        logger.log("bronze_agent", "inspect_task", result=result)
        return json.dumps(result, indent=2, default=str)

    @tool
    def bronze_ingestion_tool() -> str:
        """Execute Bronze layer ingestion: apply STTM rules and load data."""
        output_paths = _apply_bronze_rules(input_files, sttm_path, run_id)
        result = {
            "status": "success",
            "output_files": output_paths,
            "count": len(output_paths),
        }
        logger = AuditLogger(run_id)
        logger.log("bronze_agent", "bronze_ingestion", result=result)
        return json.dumps(result, indent=2, default=str)

    return [inspect_task_tool, bronze_ingestion_tool]


# ─── Public Entry Point ─────────────────────────────────────────────────────

def execute_bronze(
    input_files: list[str],
    sttm_path: str,
    run_id: str,
    task_description: str = "",
) -> list[str]:
    """
    Execute Bronze layer ingestion via AI agent.
    Returns list of output Parquet file paths.
    """
    from langgraph.prebuilt import create_react_agent

    trace = AgentTrace("bronze_agent", run_id)
    trace.set_input(input_files=input_files, sttm_path=sttm_path)
    trace.set_plan("Inspect task → Apply Bronze rules → Load to Parquet")

    try:
        llm = _make_llm()
        tools = _make_bronze_tools(input_files, sttm_path, run_id)

        agent = create_react_agent(llm, tools, state_modifier=BRONZE_AGENT_PROMPT)

        input_msg = (
            f"Execute Bronze layer ingestion for files: {input_files}. "
            f"Use STTM rules from: {sttm_path}. {task_description}"
        )
        result = agent.invoke({"messages": [("user", input_msg)]})

        output_files = _apply_bronze_rules(input_files, sttm_path, run_id)
        trace.set_output(output_files=output_files)
        trace.complete(status="success")

        return output_files

    except Exception as e:
        trace.fail(str(e))
        raise
