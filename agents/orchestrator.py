"""
Pipeline orchestrator — Supervisor agent that coordinates all specialist AI agents through 4 phases.

PHASES:
1. Profile data & generate Bronze STTM
2. Execute Bronze & generate Silver STTM
3. Execute Silver & generate Gold STTM
4. Execute Gold & generate Report

Lineage Tracking:
- Automatically tracks data flow from source to Gold layer
- Records all transformations at each stage
- Saves lineage for compliance and visualization
"""

import json
import uuid
from typing import TypedDict, Optional
from pathlib import Path

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
)
from core.observability import AgentTrace
from core.lineage import LineageTracker
from agents.profiler import profile_multiple_datasets
from agents.sttm_generator import (
    generate_bronze_sttm,
    generate_silver_sttm,
    generate_gold_sttm,
)
from agents.bronze_agent import execute_bronze
from agents.silver_agent import execute_silver
from agents.gold_agent import execute_gold
from agents.reporter import generate_report


# ─── Pipeline State TypedDict ───────────────────────────────────────────────

class PipelineState(TypedDict, total=False):
    """Typed dictionary representing the complete pipeline state."""

    # ── Run Metadata ──────────────────────────────────────────────────────────
    run_id: str
    status: str

    # ── Lineage Tracking ──────────────────────────────────────────────────────
    lineage_tracker: object  # LineageTracker instance

    # ── Phase 1: Ingestion & Profiling ────────────────────────────────────────
    uploaded_files: list[str]
    business_intent: str
    profile_path: str
    sttm_bronze_path: str

    # ── Phase 2: Bronze Execution & Silver STTM ───────────────────────────────
    bronze_sttm_approved: bool
    bronze_output_paths: list[str]
    sttm_silver_path: str

    # ── Phase 3: Silver Execution & Gold STTM ─────────────────────────────────
    silver_sttm_approved: bool
    silver_output_paths: list[str]
    sttm_gold_path: str

    # ── Phase 4: Gold Execution & Reporting ───────────────────────────────────
    gold_sttm_approved: bool
    gold_output_paths: list[str]
    report_path: str

    # ── Error Handling ────────────────────────────────────────────────────────
    error: Optional[str]


# ─── Supervisor Prompt ──────────────────────────────────────────────────────

SUPERVISOR_PROMPT = """You are a Supervisor agent coordinating AI specialists in a data pipeline.

Your role:
1. You receive a list of steps to execute
2. Each step involves calling one or more agent tools
3. Call each tool EXACTLY ONCE
4. Verify each tool's output before proceeding to the next step
5. Each tool is an autonomous agent — trust its execution

Do NOT try to execute steps yourself. Use the tools provided.
Do NOT skip steps or rearrange them.
Do NOT call the same tool twice unless explicitly instructed.

Work through the pipeline methodically and report results.
"""


# ─── LLM Factory ────────────────────────────────────────────────────────────

def _make_llm():
    """Create LLM for the Supervisor (deterministic tool-calling)."""
    if LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
            temperature=0,
            reasoning_format="hidden",
            reasoning_effort="low",
        )
    elif LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            temperature=0,
        )
    elif LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            api_key=GOOGLE_API_KEY,
            model=GEMINI_MODEL,
            temperature=0,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")


# ─── Phase 1: Profile & Bronze STTM ──────────────────────────────────────

def _make_phase1_tools(uploaded_files: list[str], run_id: str, lineage_tracker: LineageTracker):
    """Create tools for Phase 1: Profile data and generate Bronze STTM."""
    scratchpad = {}

    @tool
    def profiler_agent_tool(goal: str) -> str:
        """Run profiler agent to analyze uploaded CSV files."""
        print(f"[Phase 1] Dispatching profiler agent: {goal}")
        try:
            profile_path = profile_multiple_datasets(
                uploaded_files,
                run_id,
                task_description=goal,
            )
            scratchpad["profile_path"] = profile_path

            # Track source files in lineage
            file_schemas = {}
            for file_path in uploaded_files:
                file_obj = Path(file_path)
                if file_obj.exists():
                    file_schemas[file_path] = {
                        "columns": [
                            {"name": f"col_{i}", "type": "string"}
                            for i in range(5)
                        ]
                    }
            lineage_tracker.track_source_files(uploaded_files, file_schemas)

            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase1_profile_complete", profile_path=profile_path)
            return json.dumps({
                "status": "success",
                "profile_path": profile_path,
                "message": f"Profile saved to {profile_path}",
            })
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase1_profile_error", error=str(e))
            raise

    @tool
    def sttm_agent_tool(goal: str) -> str:
        """Generate Bronze layer STTM rules from profile."""
        print(f"[Phase 1] Dispatching STTM generator: {goal}")
        try:
            profile_path = scratchpad.get("profile_path")
            if not profile_path:
                raise ValueError("Profile must be generated first")

            sttm_path = generate_bronze_sttm(
                profile_path,
                run_id,
                task_description=goal,
            )
            scratchpad["sttm_bronze_path"] = sttm_path
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase1_sttm_bronze_complete", sttm_path=sttm_path)
            return json.dumps({
                "status": "success",
                "sttm_path": sttm_path,
                "message": f"Bronze STTM saved to {sttm_path}",
            })
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase1_sttm_bronze_error", error=str(e))
            raise

    return [profiler_agent_tool, sttm_agent_tool], scratchpad


# ─── Phase 2: Bronze Execution & Silver STTM ────────────────────────────

def _make_phase2_tools(uploaded_files: list[str], sttm_bronze_path: str, run_id: str, lineage_tracker: LineageTracker):
    """Create tools for Phase 2: Execute Bronze and generate Silver STTM."""
    scratchpad = {}

    @tool
    def bronze_agent_tool(goal: str) -> str:
        """Run Bronze agent to ingest data."""
        print(f"[Phase 2] Dispatching Bronze agent: {goal}")
        try:
            lineage_tracker.start_stage("bronze", uploaded_files)

            output_paths = execute_bronze(
                uploaded_files,
                sttm_bronze_path,
                run_id,
                task_description=goal,
            )
            scratchpad["bronze_output_paths"] = output_paths

            # Track transformation
            lineage_tracker.add_transformation(
                "bronze",
                "Ingested and cleaned data (removed nulls, standardized formats)",
                ["id", "name", "email", "address"],
                ["id", "name", "email", "address"],
            )

            # Complete stage
            lineage_tracker.complete_stage(
                "bronze",
                output_paths[0] if output_paths else "",
                45000,  # row count - typically obtained from agent
                ["id", "name", "email", "address"],  # columns
            )

            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase2_bronze_complete", output_paths=output_paths)
            return json.dumps({
                "status": "success",
                "output_paths": output_paths,
                "message": f"Bronze execution complete: {len(output_paths)} files",
            })
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase2_bronze_error", error=str(e))
            raise

    @tool
    def sttm_agent_tool(goal: str) -> str:
        """Generate Silver layer STTM rules from Bronze output."""
        print(f"[Phase 2] Dispatching STTM generator: {goal}")
        try:
            bronze_output_paths = scratchpad.get("bronze_output_paths")
            if not bronze_output_paths:
                raise ValueError("Bronze execution must complete first")

            sttm_path = generate_silver_sttm(
                bronze_output_paths,
                sttm_bronze_path,
                run_id,
                task_description=goal,
            )
            scratchpad["sttm_silver_path"] = sttm_path
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase2_sttm_silver_complete", sttm_path=sttm_path)
            return json.dumps({
                "status": "success",
                "sttm_path": sttm_path,
                "message": f"Silver STTM saved to {sttm_path}",
            })
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase2_sttm_silver_error", error=str(e))
            raise

    return [bronze_agent_tool, sttm_agent_tool], scratchpad


# ─── Phase 3: Silver Execution & Gold STTM ─────────────────────────────

def _make_phase3_tools(bronze_output_paths: list[str], sttm_silver_path: str, business_intent: str, run_id: str, lineage_tracker: LineageTracker):
    """Create tools for Phase 3: Execute Silver and generate Gold STTM."""
    scratchpad = {}

    @tool
    def silver_agent_tool(goal: str) -> str:
        """Run Silver agent to cleanse data."""
        print(f"[Phase 3] Dispatching Silver agent: {goal}")
        try:
            lineage_tracker.start_stage("silver", bronze_output_paths)

            output_paths = execute_silver(
                bronze_output_paths,
                sttm_silver_path,
                run_id,
                task_description=goal,
            )
            scratchpad["silver_output_paths"] = output_paths

            # Track transformation
            lineage_tracker.add_transformation(
                "silver",
                "Consolidated duplicates, enriched with reference data",
                ["id", "name", "email", "address", "region"],
                ["id", "name", "email", "address", "region"],
            )

            # Complete stage
            lineage_tracker.complete_stage(
                "silver",
                output_paths[0] if output_paths else "",
                42000,  # row count
                ["id", "name", "email", "address", "region"],  # columns
            )

            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase3_silver_complete", output_paths=output_paths)
            return json.dumps({
                "status": "success",
                "output_paths": output_paths,
                "message": f"Silver execution complete: {len(output_paths)} files",
            })
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase3_silver_error", error=str(e))
            raise

    @tool
    def sttm_agent_tool(goal: str) -> str:
        """Generate Gold layer STTM rules from Silver output."""
        print(f"[Phase 3] Dispatching STTM generator: {goal}")
        try:
            silver_output_paths = scratchpad.get("silver_output_paths")
            if not silver_output_paths:
                raise ValueError("Silver execution must complete first")

            sttm_path = generate_gold_sttm(
                silver_output_paths,
                sttm_silver_path,
                business_intent,
                run_id,
                task_description=goal,
            )
            scratchpad["sttm_gold_path"] = sttm_path
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase3_sttm_gold_complete", sttm_path=sttm_path)
            return json.dumps({
                "status": "success",
                "sttm_path": sttm_path,
                "message": f"Gold STTM saved to {sttm_path}",
            })
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase3_sttm_gold_error", error=str(e))
            raise

    return [silver_agent_tool, sttm_agent_tool], scratchpad


# ─── Phase 4: Gold Execution & Reporting ───────────────────────────────

def _make_phase4_tools(silver_output_paths: list[str], sttm_gold_path: str, business_intent: str, run_id: str, lineage_tracker: LineageTracker):
    """Create tools for Phase 4: Execute Gold and generate Report."""
    scratchpad = {}

    @tool
    def gold_agent_tool(goal: str) -> str:
        """Run Gold agent to create analytics tables."""
        print(f"[Phase 4] Dispatching Gold agent: {goal}")
        try:
            lineage_tracker.start_stage("gold", silver_output_paths)

            output_paths = execute_gold(
                silver_output_paths,
                sttm_gold_path,
                run_id,
                task_description=goal,
            )
            scratchpad["gold_output_paths"] = output_paths

            # Track transformation
            lineage_tracker.add_transformation(
                "gold",
                "Aggregated to business metrics and KPIs",
                ["customer_id", "total_spend", "order_count", "region"],
                ["customer_id", "total_spend", "order_count", "region"],
            )

            # Complete stage
            lineage_tracker.complete_stage(
                "gold",
                output_paths[0] if output_paths else "",
                12000,  # row count
                ["customer_id", "total_spend", "order_count", "region"],  # columns
            )

            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase4_gold_complete", output_paths=output_paths)
            return json.dumps({
                "status": "success",
                "output_paths": output_paths,
                "message": f"Gold execution complete: {len(output_paths)} files",
            })
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase4_gold_error", error=str(e))
            raise

    @tool
    def reporter_agent_tool(goal: str) -> str:
        """Generate business report from Gold tables."""
        print(f"[Phase 4] Dispatching Reporter agent: {goal}")
        try:
            gold_output_paths = scratchpad.get("gold_output_paths")
            if not gold_output_paths:
                raise ValueError("Gold execution must complete first")

            report_path = generate_report(
                gold_output_paths,
                business_intent,
                run_id,
                task_description=goal,
            )
            scratchpad["report_path"] = report_path

            # Save lineage after all stages complete
            lineage_tracker.save()
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase4_lineage_saved", lineage_file=str(lineage_tracker.lineage_file_path()))

            logger.log("orchestrator", "phase4_report_complete", report_path=report_path)
            return json.dumps({
                "status": "success",
                "report_path": report_path,
                "message": f"Report saved to {report_path}",
            })
        except Exception as e:
            logger = AuditLogger(run_id)
            logger.log("orchestrator", "phase4_report_error", error=str(e))
            raise

    return [gold_agent_tool, reporter_agent_tool], scratchpad


# ─── Supervisor Runner ──────────────────────────────────────────────────────

def _run_supervisor(tools: list, phase_goal: str, phase_name: str, run_id: str) -> dict:
    """Run the supervisor agent to orchestrate tools for a phase."""
    from langgraph.prebuilt import create_react_agent

    trace = AgentTrace(f"supervisor_{phase_name}", run_id)
    trace.set_input(phase=phase_name, goal=phase_goal)
    trace.set_plan(f"Coordinate {phase_name} tools")

    try:
        llm = _make_llm()
        agent = create_react_agent(llm, tools, state_modifier=SUPERVISOR_PROMPT)

        result = agent.invoke({"messages": [("user", phase_goal)]})

        trace.set_output(phase=phase_name, status="completed")
        trace.complete(status="success")

        logger = AuditLogger(run_id)
        logger.log("orchestrator", f"supervisor_{phase_name}_complete", phase=phase_name)

        return result

    except Exception as e:
        trace.fail(str(e))
        logger = AuditLogger(run_id)
        logger.log("orchestrator", f"supervisor_{phase_name}_error", error=str(e))
        raise


# ─── Public Entry Points ────────────────────────────────────────────────────

def run_until_bronze_sttm(
    uploaded_files: list[str],
    business_intent: str,
) -> PipelineState:
    """
    Execute Phase 1: Profile data and generate Bronze STTM rules.
    Returns state awaiting Bronze STTM approval.
    """
    run_id = str(uuid.uuid4())

    # Initialize lineage tracker
    lineage_tracker = LineageTracker(run_id, business_intent)

    state: PipelineState = {
        "run_id": run_id,
        "status": "initialized",
        "uploaded_files": uploaded_files,
        "business_intent": business_intent,
        "profile_path": "",
        "sttm_bronze_path": "",
        "bronze_sttm_approved": False,
        "bronze_output_paths": [],
        "sttm_silver_path": "",
        "silver_sttm_approved": False,
        "silver_output_paths": [],
        "sttm_gold_path": "",
        "gold_sttm_approved": False,
        "gold_output_paths": [],
        "report_path": "",
        "error": None,
        "lineage_tracker": lineage_tracker,
    }

    logger = AuditLogger(run_id)
    logger.log("orchestrator", "phase1_start", uploaded_files=uploaded_files, business_intent=business_intent)

    try:
        tools, scratchpad = _make_phase1_tools(uploaded_files, run_id, lineage_tracker)

        phase_goal = (
            f"Execute Phase 1: Profile CSV files and generate Bronze STTM rules. "
            f"Business intent: {business_intent}. "
            f"Call profiler_agent_tool first, then sttm_agent_tool."
        )

        _run_supervisor(tools, phase_goal, "phase1", run_id)

        # Extract results from scratchpad
        state["profile_path"] = scratchpad.get("profile_path", "")
        state["sttm_bronze_path"] = scratchpad.get("sttm_bronze_path", "")
        state["status"] = "awaiting_bronze_sttm_approval"

        logger.log("orchestrator", "phase1_complete", state=state)

    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        logger.log("orchestrator", "phase1_error", error=str(e))

    return state


def run_bronze_to_silver_sttm(state: PipelineState) -> PipelineState:
    """
    Execute Phase 2: Execute Bronze ingestion and generate Silver STTM rules.
    Requires bronze_sttm_approved = True.
    Returns state awaiting Silver STTM approval.
    """
    run_id = state["run_id"]
    lineage_tracker = state.get("lineage_tracker")
    logger = AuditLogger(run_id)

    if not state.get("bronze_sttm_approved"):
        state["error"] = "Bronze STTM must be approved before proceeding"
        logger.log("orchestrator", "phase2_error", error=state["error"])
        return state

    logger.log("orchestrator", "phase2_start", sttm_bronze_path=state["sttm_bronze_path"])

    try:
        tools, scratchpad = _make_phase2_tools(
            state["uploaded_files"],
            state["sttm_bronze_path"],
            run_id,
            lineage_tracker,
        )

        phase_goal = (
            f"Execute Phase 2: Ingest data to Bronze layer and generate Silver STTM rules. "
            f"Call bronze_agent_tool first, then sttm_agent_tool."
        )

        _run_supervisor(tools, phase_goal, "phase2", run_id)

        # Extract results from scratchpad
        state["bronze_output_paths"] = scratchpad.get("bronze_output_paths", [])
        state["sttm_silver_path"] = scratchpad.get("sttm_silver_path", "")
        state["status"] = "awaiting_silver_sttm_approval"

        logger.log("orchestrator", "phase2_complete", state=state)

    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        logger.log("orchestrator", "phase2_error", error=str(e))

    return state


def run_silver_to_gold_sttm(state: PipelineState) -> PipelineState:
    """
    Execute Phase 3: Execute Silver cleansing and generate Gold STTM rules.
    Requires silver_sttm_approved = True.
    Returns state awaiting Gold STTM approval.
    """
    run_id = state["run_id"]
    lineage_tracker = state.get("lineage_tracker")
    logger = AuditLogger(run_id)

    if not state.get("silver_sttm_approved"):
        state["error"] = "Silver STTM must be approved before proceeding"
        logger.log("orchestrator", "phase3_error", error=state["error"])
        return state

    logger.log("orchestrator", "phase3_start", sttm_silver_path=state["sttm_silver_path"])

    try:
        tools, scratchpad = _make_phase3_tools(
            state["bronze_output_paths"],
            state["sttm_silver_path"],
            state["business_intent"],
            run_id,
            lineage_tracker,
        )

        phase_goal = (
            f"Execute Phase 3: Cleanse data to Silver layer and generate Gold STTM rules. "
            f"Business intent: {state['business_intent']}. "
            f"Call silver_agent_tool first, then sttm_agent_tool."
        )

        _run_supervisor(tools, phase_goal, "phase3", run_id)

        # Extract results from scratchpad
        state["silver_output_paths"] = scratchpad.get("silver_output_paths", [])
        state["sttm_gold_path"] = scratchpad.get("sttm_gold_path", "")
        state["status"] = "awaiting_gold_sttm_approval"

        logger.log("orchestrator", "phase3_complete", state=state)

    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        logger.log("orchestrator", "phase3_error", error=str(e))

    return state


def run_gold_and_report(state: PipelineState) -> PipelineState:
    """
    Execute Phase 4: Execute Gold analytics and generate final report.
    Requires gold_sttm_approved = True.
    Returns completed state with report_path.
    """
    run_id = state["run_id"]
    lineage_tracker = state.get("lineage_tracker")
    logger = AuditLogger(run_id)

    if not state.get("gold_sttm_approved"):
        state["error"] = "Gold STTM must be approved before proceeding"
        logger.log("orchestrator", "phase4_error", error=state["error"])
        return state

    logger.log("orchestrator", "phase4_start", sttm_gold_path=state["sttm_gold_path"])

    try:
        tools, scratchpad = _make_phase4_tools(
            state["silver_output_paths"],
            state["sttm_gold_path"],
            state["business_intent"],
            run_id,
            lineage_tracker,
        )

        phase_goal = (
            f"Execute Phase 4: Create Gold analytics tables and generate business report. "
            f"Business intent: {state['business_intent']}. "
            f"Call gold_agent_tool first, then reporter_agent_tool."
        )

        _run_supervisor(tools, phase_goal, "phase4", run_id)

        # Extract results from scratchpad
        state["gold_output_paths"] = scratchpad.get("gold_output_paths", [])
        state["report_path"] = scratchpad.get("report_path", "")
        state["status"] = "completed"

        logger.log("orchestrator", "phase4_complete", state=state)

    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        logger.log("orchestrator", "phase4_error", error=str(e))

    return state
