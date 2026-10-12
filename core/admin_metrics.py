"""
System Metrics and Performance Monitoring

Collects system health metrics and pipeline performance statistics.
"""

import psutil
import json
import threading
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from collections import defaultdict

from core.config import AUDIT_DIR


@dataclass
class SystemMetrics:
    """System health snapshot"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    memory_available_mb: int
    disk_free_gb: float
    process_count: int


@dataclass
class AgentMetric:
    """Agent performance metric"""
    timestamp: str
    agent_name: str
    run_id: str
    duration_seconds: float
    status: str  # "success", "failed", "timeout"
    tokens_used: int
    api_calls: int
    error_message: Optional[str] = None


class SystemMonitor:
    """Monitor system health and performance"""

    def __init__(self):
        self.metrics_dir = AUDIT_DIR / "metrics"
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def get_system_metrics(self) -> SystemMetrics:
        """Capture current system metrics"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return SystemMetrics(
            timestamp=datetime.now(timezone.utc).isoformat(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            memory_available_mb=memory.available // (1024 * 1024),
            disk_free_gb=disk.free / (1024 ** 3),
            process_count=len(psutil.pids()),
        )

    def get_cpu_trend(self, minutes: int = 5) -> List[float]:
        """Get CPU usage trend over last N minutes"""
        # psutil doesn't have historical data, so we return current
        # In production, store metrics to database
        return [psutil.cpu_percent(interval=0.1) for _ in range(minutes)]

    def get_memory_trend(self, minutes: int = 5) -> List[float]:
        """Get memory usage trend over last N minutes"""
        return [psutil.virtual_memory().percent for _ in range(minutes)]

    def save_metrics(self, metrics: SystemMetrics) -> None:
        """Save metrics to file"""
        with self.lock:
            metrics_file = self.metrics_dir / "system_metrics.jsonl"

            with open(metrics_file, "a") as f:
                f.write(json.dumps(asdict(metrics)) + "\n")

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        metrics = self.get_system_metrics()

        # Determine status based on thresholds
        status = "HEALTHY"
        issues = []

        if metrics.cpu_percent > 80:
            status = "WARNING"
            issues.append(f"High CPU: {metrics.cpu_percent}%")

        if metrics.memory_percent > 85:
            status = "WARNING"
            issues.append(f"High memory: {metrics.memory_percent}%")

        if metrics.disk_percent > 90:
            status = "CRITICAL"
            issues.append(f"Disk space critical: {metrics.disk_percent}%")

        if metrics.memory_available_mb < 512:
            status = "WARNING"
            issues.append(f"Low memory: {metrics.memory_available_mb}MB available")

        return {
            "status": status,
            "metrics": asdict(metrics),
            "issues": issues,
        }


class PipelineMetrics:
    """Track pipeline run statistics"""

    def __init__(self):
        self.metrics_dir = AUDIT_DIR / "metrics"
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.agent_metrics_file = self.metrics_dir / "agent_metrics.jsonl"
        self.lock = threading.Lock()

    def record_agent_run(
        self,
        agent_name: str,
        run_id: str,
        duration_seconds: float,
        status: str,
        tokens_used: int = 0,
        api_calls: int = 0,
        error_message: str = None,
    ) -> None:
        """Record an agent run metric"""
        with self.lock:
            metric = AgentMetric(
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent_name=agent_name,
                run_id=run_id,
                duration_seconds=duration_seconds,
                status=status,
                tokens_used=tokens_used,
                api_calls=api_calls,
                error_message=error_message,
            )

            with open(self.agent_metrics_file, "a") as f:
                f.write(json.dumps(asdict(metric)) + "\n")

    def get_agent_statistics(self, agent_name: str = None) -> Dict[str, Any]:
        """Get statistics for one or all agents"""
        if not self.agent_metrics_file.exists():
            return {}

        stats = defaultdict(lambda: {
            "total_runs": 0,
            "successful": 0,
            "failed": 0,
            "avg_duration": 0,
            "total_duration": 0,
            "total_api_calls": 0,
            "total_tokens": 0,
            "error_rate": 0,
        })

        with open(self.agent_metrics_file, "r") as f:
            for line in f:
                try:
                    metric_dict = json.loads(line.strip())
                    name = metric_dict["agent_name"]

                    if agent_name and name != agent_name:
                        continue

                    s = stats[name]
                    s["total_runs"] += 1
                    s["total_duration"] += metric_dict["duration_seconds"]
                    s["total_api_calls"] += metric_dict.get("api_calls", 0)
                    s["total_tokens"] += metric_dict.get("tokens_used", 0)

                    if metric_dict["status"] == "success":
                        s["successful"] += 1
                    else:
                        s["failed"] += 1

                except Exception:
                    pass

        # Calculate derived metrics
        for name, s in stats.items():
            if s["total_runs"] > 0:
                s["avg_duration"] = s["total_duration"] / s["total_runs"]
                s["error_rate"] = (s["failed"] / s["total_runs"]) * 100

        if agent_name and agent_name in stats:
            return dict(stats[agent_name])

        return dict(stats)

    def get_pipeline_run_summary(self) -> Dict[str, Any]:
        """Get overall pipeline run summary"""
        stats = self.get_agent_statistics()

        total_runs = sum(s["total_runs"] for s in stats.values())
        total_success = sum(s["successful"] for s in stats.values())
        total_failed = sum(s["failed"] for s in stats.values())
        total_duration = sum(s["total_duration"] for s in stats.values())
        total_api_calls = sum(s["total_api_calls"] for s in stats.values())

        return {
            "total_runs": total_runs,
            "successful": total_success,
            "failed": total_failed,
            "success_rate": (total_success / total_runs * 100) if total_runs > 0 else 0,
            "total_duration_hours": total_duration / 3600,
            "avg_run_duration": total_duration / total_runs if total_runs > 0 else 0,
            "total_api_calls": total_api_calls,
            "agents": stats,
        }

    def get_error_summary(self) -> Dict[str, int]:
        """Get count of errors by type"""
        if not self.agent_metrics_file.exists():
            return {}

        error_counts = defaultdict(int)

        with open(self.agent_metrics_file, "r") as f:
            for line in f:
                try:
                    metric_dict = json.loads(line.strip())
                    if metric_dict["status"] == "failed" and metric_dict.get("error_message"):
                        # Extract error type
                        error_msg = metric_dict["error_message"]
                        error_type = error_msg.split(":")[0] if ":" in error_msg else error_msg[:50]
                        error_counts[error_type] += 1

                except Exception:
                    pass

        return dict(error_counts)

    def get_recent_failures(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent failed runs"""
        if not self.agent_metrics_file.exists():
            return []

        failures = []

        with open(self.agent_metrics_file, "r") as f:
            for line in f:
                try:
                    metric_dict = json.loads(line.strip())
                    if metric_dict["status"] == "failed":
                        failures.append(metric_dict)

                except Exception:
                    pass

        # Return most recent N
        return sorted(failures, key=lambda x: x["timestamp"], reverse=True)[:limit]


# Global singletons
_system_monitor: Optional[SystemMonitor] = None
_pipeline_metrics: Optional[PipelineMetrics] = None
_monitor_lock = threading.Lock()


def get_system_monitor() -> SystemMonitor:
    """Get global system monitor singleton"""
    global _system_monitor

    if _system_monitor is None:
        with _monitor_lock:
            if _system_monitor is None:
                _system_monitor = SystemMonitor()

    return _system_monitor


def get_pipeline_metrics() -> PipelineMetrics:
    """Get global pipeline metrics singleton"""
    global _pipeline_metrics

    if _pipeline_metrics is None:
        with _monitor_lock:
            if _pipeline_metrics is None:
                _pipeline_metrics = PipelineMetrics()

    return _pipeline_metrics
