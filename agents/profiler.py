"""
Data profiler agent — AI-driven analysis of CSV file structure and quality.
"""

import json
from datetime import datetime
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
    PROFILES_DIR,
)
from core.observability import AgentTrace


# ─── System Prompt ──────────────────────────────────────────────────────────
PROFILER_AGENT_PROMPT = """You are a Data Analyst specializing in data profiling.

Your task: analyze CSV files and generate a comprehensive data profile.

Follow this sequence:
1. THINK: understand the task and file paths
2. INSPECT: call inspect_files_tool to preview files
3. PLAN: decide what statistics are needed
4. ACT: call profiler_tool to compute full statistics
5. VERIFY: validate results and compile final profile

Return a JSON object with:
- semantic_meanings: dict mapping column_name -> what the column represents
- join_keys: list of potential foreign keys or join columns
- quality_notes: dict mapping column_name -> data quality observations (nulls, inconsistencies, outliers, duplicates)
- overall_quality_score: 0-100 rating
"""


# ─── Helper Functions (Pure Python) ─────────────────────────────────────────

def _inspect_files(file_paths: list[str]) -> dict:
    """Preview files: shape, columns, dtypes, 3 sample rows."""
    result = {}
    for fpath in file_paths:
        try:
            df = pd.read_csv(fpath)
            result[fpath] = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "sample_values": {
                    col: df[col].dropna().head(3).tolist() for col in df.columns
                },
            }
        except Exception as e:
            result[fpath] = {"error": str(e)}
    return result


def _compute_stats(file_paths: list[str]) -> dict:
    """Compute full statistics for each file."""
    result = {}
    for fpath in file_paths:
        try:
            df = pd.read_csv(fpath)
            stats = {}
            for col in df.columns:
                col_stats = {
                    "dtype": str(df[col].dtype),
                    "null_count": int(df[col].isna().sum()),
                    "null_pct": round(df[col].isna().sum() / len(df) * 100, 2),
                    "unique_count": int(df[col].nunique()),
                }
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_stats.update({
                        "min": float(df[col].min()) if not df[col].isna().all() else None,
                        "max": float(df[col].max()) if not df[col].isna().all() else None,
                        "mean": float(df[col].mean()) if not df[col].isna().all() else None,
                    })
                col_stats["sample_values"] = df[col].dropna().head(5).tolist()
                stats[col] = col_stats
            result[fpath] = stats
        except Exception as e:
            result[fpath] = {"error": str(e)}
    return result


# ─── Tool Factory ───────────────────────────────────────────────────────────

def _make_profiler_tools(file_paths: list[str], run_id: str):
    """Create tools for the profiler agent."""

    @tool
    def inspect_files_tool() -> str:
        """Preview CSV files: shape, columns, dtypes, sample values."""
        result = _inspect_files(file_paths)
        logger = AuditLogger(run_id)
        logger.log("profiler", "inspect_files", result=result)
        return json.dumps(result, indent=2, default=str)

    @tool
    def profiler_tool() -> str:
        """Compute full statistics for CSV files."""
        result = _compute_stats(file_paths)
        logger = AuditLogger(run_id)
        logger.log("profiler", "compute_stats", result=result)
        return json.dumps(result, indent=2, default=str)

    return [inspect_files_tool, profiler_tool]


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


# ─── Public Entry Points ────────────────────────────────────────────────────

def profile_dataset(file_path: str, run_id: str, task_description: str = "") -> str:
    """Profile a single CSV file and return path to profile JSON."""
    return profile_multiple_datasets([file_path], run_id, task_description)


def profile_multiple_datasets(
    file_paths: list[str],
    run_id: str,
    task_description: str = "",
) -> str:
    """
    Profile multiple CSV files using an AI agent.
    Returns path to the combined profile JSON.
    """
    from langgraph.prebuilt import create_react_agent

    trace = AgentTrace("profiler", run_id)
    trace.set_input(file_paths=file_paths, task_description=task_description)
    trace.set_plan("Inspect files → compute statistics → generate profile")

    try:
        llm = _make_llm()
        tools = _make_profiler_tools(file_paths, run_id)

        agent = create_react_agent(llm, tools, state_modifier=PROFILER_AGENT_PROMPT)

        input_msg = f"Profile these files: {file_paths}. Task: {task_description}"
        result = agent.invoke({"messages": [("user", input_msg)]})

        profile_content = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "files": file_paths,
            "task_description": task_description,
            "profile": result.get("messages", [])[-1].content if result.get("messages") else "",
        }

        trace.set_output(profile=profile_content)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_path = PROFILES_DIR / f"profile_combined_{timestamp}.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile_content, f, indent=2, default=str)

        trace.complete(status="success")
        return str(profile_path)

    except Exception as e:
        trace.fail(str(e))
        raise
