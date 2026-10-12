"""
STTM generator agent — AI-driven creation of Source-to-Target Mapping transformation rules.
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
    BRONZE_DIR,
    SILVER_DIR,
    GOLD_DIR,
)
from core.observability import AgentTrace


# ─── System Prompt ──────────────────────────────────────────────────────────
STTM_AGENT_PROMPT = """You are an expert data engineer specializing in STTM (Source-to-Target Mapping) rule generation.

Your task: generate transformation rules for the specified data layer.

Follow this sequence:
1. Call inspect_context_tool to understand the current state
2. Call the appropriate generation tool ONCE (bronze, silver, or gold)
3. Ensure all rules follow the STTM format

Bronze layer: map every column, add metadata (_load_timestamp, _source_file)
Silver layer: add surrogate key first, then apply cleansing rules
Gold layer: add surrogate key first, then apply joins/aggregations

Return the STTM rule path.
"""


# ─── Shared JSON Extraction Helper ──────────────────────────────────────────

def _parse_json_array(raw: str) -> list[dict]:
    """Extract a JSON array of STTM rows from raw LLM text output."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]
    raw = raw.strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        rows = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return []
    return rows if isinstance(rows, list) else []


def _invoke_llm_for_sttm_rows(prompt: str, layer: str) -> list[dict]:
    """
    Invoke LLM for STTM rows, retrying once, failing loudly if empty.
    Guarantees non-empty result or raises ValueError.
    """
    llm = _make_llm()
    last_raw = ""
    for attempt in range(2):
        p = (
            prompt
            if attempt == 0
            else prompt
            + "\n\nReturn ONLY the JSON array. No other text, no explanation."
        )
        response = llm.invoke(p)
        last_raw = response.content if hasattr(response, "content") else str(response)
        rows = _parse_json_array(last_raw)
        if rows:
            return rows
    raise ValueError(
        f"{layer} STTM generation failed: LLM did not return a valid, non-empty JSON array "
        f"after 2 attempts. Raw response (truncated): {last_raw[:500]!r}"
    )


# ─── Helper Functions (Pure Python) ─────────────────────────────────────────

def _prepare_bronze_context(profile_path: str) -> dict:
    """Read the data profile and prepare context for Bronze layer rules."""
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        return {
            "files": profile.get("files", []),
            "profile": profile.get("profile", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def _prepare_silver_context(bronze_output_paths: list[str], bronze_sttm_path: str) -> dict:
    """Read Bronze layer Parquet metadata and STTM rules for Silver context."""
    try:
        bronze_sttm = pd.read_csv(bronze_sttm_path)
        approved_cols = bronze_sttm["target_column"].tolist()
        return {
            "bronze_output_paths": bronze_output_paths,
            "approved_columns": approved_cols,
            "bronze_sttm_columns": list(bronze_sttm.columns),
        }
    except Exception as e:
        return {"error": str(e)}


def _prepare_gold_context(silver_output_paths: list[str], silver_sttm_path: str) -> dict:
    """Read Silver layer Parquet metadata and STTM rules for Gold context."""
    try:
        silver_sttm = pd.read_csv(silver_sttm_path)
        return {
            "silver_output_paths": silver_output_paths,
            "silver_sttm_columns": list(silver_sttm.columns),
        }
    except Exception as e:
        return {"error": str(e)}


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

def _make_sttm_tools(
    layer: str,
    profile_path: str = "",
    bronze_output_paths: list[str] = None,
    bronze_sttm_path: str = "",
    silver_output_paths: list[str] = None,
    silver_sttm_path: str = "",
    business_intent: str = "",
    run_id: str = "",
):
    """Create tools for the STTM generator agent."""
    bronze_output_paths = bronze_output_paths or []
    silver_output_paths = silver_output_paths or []

    @tool
    def inspect_context_tool() -> str:
        """Inspect the context for the current layer."""
        logger = AuditLogger(run_id)
        if layer == "bronze":
            context = _prepare_bronze_context(profile_path)
        elif layer == "silver":
            context = _prepare_silver_context(bronze_output_paths, bronze_sttm_path)
        elif layer == "gold":
            context = _prepare_gold_context(silver_output_paths, silver_sttm_path)
        else:
            context = {"error": f"Unknown layer: {layer}"}
        logger.log("sttm_generator", f"inspect_context_{layer}", context=context)
        return json.dumps(context, indent=2, default=str)

    @tool
    def generate_bronze_sttm_tool() -> str:
        """Generate Bronze layer STTM rules."""
        context = _prepare_bronze_context(profile_path)
        prompt = f"""Generate Bronze layer STTM rules from this profile:
{json.dumps(context, indent=2)}

Requirements:
1. Map every column from source to bronze_layer schema
2. Add metadata columns: _load_timestamp (load time), _source_file (source file path)
3. Include transformation_type and transformation_logic for each rule

Return a JSON array with objects containing:
- source_schema, source_table, source_column
- target_schema, target_table, target_column
- transformation_type, transformation_logic
"""
        rows = _invoke_llm_for_sttm_rows(prompt, "Bronze")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sttm_path = BRONZE_DIR / f"sttm_bronze_{timestamp}.csv"
        df = pd.DataFrame(rows)
        df.to_csv(sttm_path, index=False)
        logger = AuditLogger(run_id)
        logger.log("sttm_generator", "generate_bronze_sttm", rows_count=len(rows), sttm_path=str(sttm_path))
        return str(sttm_path)

    @tool
    def generate_silver_sttm_tool() -> str:
        """Generate Silver layer STTM rules."""
        context = _prepare_silver_context(bronze_output_paths, bronze_sttm_path)
        prompt = f"""Generate Silver layer STTM rules from this Bronze context:
{json.dumps(context, indent=2)}

Requirements:
1. Add a surrogate key first (e.g., sk_<table>)
2. Apply cleansing rules: normalize text, standardize dates, handle nulls
3. Filter to only approved columns from Bronze
4. Include transformation_type and transformation_logic for each rule

Return a JSON array with STTM objects.
"""
        rows = _invoke_llm_for_sttm_rows(prompt, "Silver")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sttm_path = SILVER_DIR / f"sttm_silver_{timestamp}.csv"
        df = pd.DataFrame(rows)
        df.to_csv(sttm_path, index=False)
        logger = AuditLogger(run_id)
        logger.log("sttm_generator", "generate_silver_sttm", rows_count=len(rows), sttm_path=str(sttm_path))
        return str(sttm_path)

    @tool
    def generate_gold_sttm_tool() -> str:
        """Generate Gold layer STTM rules."""
        context = _prepare_gold_context(silver_output_paths, silver_sttm_path)
        prompt = f"""Generate Gold layer STTM rules from this Silver context:
{json.dumps(context, indent=2)}

Business intent: {business_intent}

Requirements:
1. Add a surrogate key first (e.g., pk_<table>)
2. Apply joins and aggregations based on business intent
3. Create facts and dimensions for analytics
4. Include transformation_type and transformation_logic for each rule

Return a JSON array with STTM objects.
"""
        rows = _invoke_llm_for_sttm_rows(prompt, "Gold")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sttm_path = GOLD_DIR / f"sttm_gold_{timestamp}.csv"
        df = pd.DataFrame(rows)
        df.to_csv(sttm_path, index=False)
        logger = AuditLogger(run_id)
        logger.log("sttm_generator", "generate_gold_sttm", rows_count=len(rows), sttm_path=str(sttm_path))
        return str(sttm_path)

    if layer == "bronze":
        return [inspect_context_tool, generate_bronze_sttm_tool]
    elif layer == "silver":
        return [inspect_context_tool, generate_silver_sttm_tool]
    elif layer == "gold":
        return [inspect_context_tool, generate_gold_sttm_tool]
    else:
        return [inspect_context_tool]


# ─── Agent Runner ───────────────────────────────────────────────────────────

def _run_sttm_agent(
    layer: str,
    profile_path: str = "",
    bronze_output_paths: list[str] = None,
    bronze_sttm_path: str = "",
    silver_output_paths: list[str] = None,
    silver_sttm_path: str = "",
    business_intent: str = "",
    run_id: str = "",
) -> str:
    """Run STTM agent and extract the generated STTM path."""
    from langgraph.prebuilt import create_react_agent

    trace = AgentTrace(f"sttm_generator_{layer}", run_id)
    trace.set_input(
        layer=layer,
        profile_path=profile_path,
        business_intent=business_intent,
    )
    trace.set_plan(f"Generate {layer.upper()} layer STTM rules")

    try:
        llm = _make_llm()
        tools = _make_sttm_tools(
            layer=layer,
            profile_path=profile_path,
            bronze_output_paths=bronze_output_paths or [],
            bronze_sttm_path=bronze_sttm_path,
            silver_output_paths=silver_output_paths or [],
            silver_sttm_path=silver_sttm_path,
            business_intent=business_intent,
            run_id=run_id,
        )

        agent = create_react_agent(llm, tools, state_modifier=STTM_AGENT_PROMPT)
        input_msg = f"Generate {layer.upper()} layer STTM rules. Business intent: {business_intent}"
        result = agent.invoke({"messages": [("user", input_msg)]})

        final_msg = result.get("messages", [])[-1].content if result.get("messages") else ""
        sttm_path = final_msg.strip().split()[-1] if final_msg else ""

        trace.set_output(sttm_path=sttm_path)
        trace.complete(status="success")
        return sttm_path

    except Exception as e:
        trace.fail(str(e))
        raise


# ─── Public Entry Points ────────────────────────────────────────────────────

def generate_bronze_sttm(profile_path: str, run_id: str, task_description: str = "") -> str:
    """
    Generate Bronze layer STTM rules from a data profile.
    Returns path to the STTM CSV file.
    """
    return _run_sttm_agent(
        layer="bronze",
        profile_path=profile_path,
        run_id=run_id,
    )


def generate_silver_sttm(
    bronze_output_paths: list[str],
    bronze_sttm_path: str,
    run_id: str,
    task_description: str = "",
) -> str:
    """
    Generate Silver layer STTM rules from Bronze output and STTM rules.
    Returns path to the STTM CSV file.
    """
    return _run_sttm_agent(
        layer="silver",
        bronze_output_paths=bronze_output_paths,
        bronze_sttm_path=bronze_sttm_path,
        run_id=run_id,
    )


def generate_gold_sttm(
    silver_output_paths: list[str],
    silver_sttm_path: str,
    business_intent: str,
    run_id: str,
    task_description: str = "",
) -> str:
    """
    Generate Gold layer STTM rules from Silver output, STTM rules, and business intent.
    Returns path to the STTM CSV file.
    """
    return _run_sttm_agent(
        layer="gold",
        silver_output_paths=silver_output_paths,
        silver_sttm_path=silver_sttm_path,
        business_intent=business_intent,
        run_id=run_id,
    )
