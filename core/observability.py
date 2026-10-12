"""
Agent observability — captures detailed reasoning traces for each AI agent run.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from core.config import BASE_DIR

TRACES_DIR: Path = BASE_DIR / "data" / "traces"
TRACES_DIR.mkdir(parents=True, exist_ok=True)


class AgentTrace:
    """Records the full reasoning trace of a single agent execution."""

    def __init__(self, agent_name: str, run_id: str):
        self.agent_name = agent_name
        self.run_id = run_id
        self._start_time = time.time()
        self.trace: dict = {
            "agent": agent_name,
            "run_id": run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "input": {},
            "plan": None,
            "tool_calls": [],
            "reasoning_steps": [],
            "output": {},
            "duration_seconds": None,
            "status": None,
        }

    # ── Chainable setters ────────────────────────────────────────────────────

    def set_input(self, **kwargs) -> "AgentTrace":
        self.trace["input"] = kwargs
        return self

    def set_plan(self, plan_str: str) -> "AgentTrace":
        self.trace["plan"] = plan_str
        return self

    def set_output(self, **kwargs) -> "AgentTrace":
        self.trace["output"] = kwargs
        return self

    # ── Message extraction ───────────────────────────────────────────────────

    def extract_from_messages(self, messages: list) -> "AgentTrace":
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        plan_captured = False

        for msg in messages:
            if isinstance(msg, HumanMessage):
                self.trace["reasoning_steps"].append({
                    "type": "task_input",
                    "content": msg.content,
                })
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    self.trace["tool_calls"].extend(msg.tool_calls)
                if msg.content:
                    self.trace["reasoning_steps"].append({
                        "type": "ai_reasoning",
                        "content": msg.content,
                    })
                    if not plan_captured and msg.content.strip():
                        self.trace["plan"] = msg.content
                        plan_captured = True
            elif isinstance(msg, ToolMessage):
                self.trace["reasoning_steps"].append({
                    "type": "tool_result",
                    "tool": getattr(msg, "name", "unknown"),
                    "content": msg.content,
                })

        return self

    # ── Completion ───────────────────────────────────────────────────────────

    def complete(self, status: str = "success") -> dict:
        self.trace["status"] = status
        self.trace["duration_seconds"] = round(time.time() - self._start_time, 3)

        file_name = f"trace_{self.agent_name}_{self.run_id[:8]}.json"
        trace_path = TRACES_DIR / file_name
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(self.trace, f, indent=2, default=str)

        print(
            f"[TRACE] {self.agent_name} | {status} | "
            f"{self.trace['duration_seconds']}s | {trace_path.name}"
        )
        return self.trace

    def fail(self, error: str) -> dict:
        self.trace["error"] = error
        return self.complete(status="failed")
