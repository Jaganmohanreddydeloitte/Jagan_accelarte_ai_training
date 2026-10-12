"""
STTM Version Control System

Manages version history of STTM rules with:
- Content-based versioning (detect actual changes)
- Metadata tracking (user, timestamp, change description)
- Version comparison (diff between versions)
- Rollback capability (restore previous versions)
- Thread-safe operations
"""

import json
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from difflib import unified_diff

from core.config import BRONZE_DIR, SILVER_DIR, GOLD_DIR, AUDIT_DIR


@dataclass
class STTMVersion:
    """Represents one version of STTM rules"""
    version_id: str
    layer: str  # "bronze", "silver", "gold"
    timestamp: str  # ISO format UTC
    user: str  # Username or "system"
    description: str  # Change description
    content_hash: str  # SHA256 of content
    file_path: str  # Path where rules were stored
    sttm_content: Dict[str, Any]  # Actual STTM rules
    row_count: int  # Number of transformation rules
    file_size_bytes: int  # Size of STTM file


class STTMVersionManager:
    """Manages STTM version history and rollback"""

    def __init__(self):
        self.versions_dir = AUDIT_DIR / "sttm_versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.versions_dir / "metadata.json"
        self.lock = threading.Lock()

        # Load metadata
        self.metadata: List[Dict[str, Any]] = self._load_metadata()

    def _load_metadata(self) -> List[Dict[str, Any]]:
        """Load version metadata from file"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_metadata(self) -> None:
        """Save version metadata to file"""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def _compute_hash(self, content: Dict[str, Any]) -> str:
        """Compute SHA256 hash of content"""
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def _generate_version_id(self, layer: str) -> str:
        """Generate version ID: layer_TIMESTAMP_SHORT_HASH"""
        timestamp = datetime.now(timezone.utc).isoformat().replace(":", "").replace(".", "")[:-6]
        return f"{layer}_{timestamp}"

    def save_version(
        self,
        layer: str,
        sttm_content: Dict[str, Any],
        file_path: str,
        user: str = "system",
        description: str = "Auto-saved",
    ) -> str:
        """
        Save a new version of STTM rules.
        Returns version_id if saved, or None if content unchanged.
        """
        with self.lock:
            content_hash = self._compute_hash(sttm_content)

            # Check if content changed since last version
            last_version = self._get_last_version(layer)
            if last_version and last_version["content_hash"] == content_hash:
                return None  # No change, don't create version

            version_id = self._generate_version_id(layer)
            timestamp = datetime.now(timezone.utc).isoformat()

            # Count rows
            row_count = len(sttm_content) if isinstance(sttm_content, dict) else 0

            # Determine file size
            file_size_bytes = len(json.dumps(sttm_content).encode())

            # Create version object
            version = STTMVersion(
                version_id=version_id,
                layer=layer,
                timestamp=timestamp,
                user=user,
                description=description,
                content_hash=content_hash,
                file_path=file_path,
                sttm_content=sttm_content,
                row_count=row_count,
                file_size_bytes=file_size_bytes,
            )

            # Save version content to file
            version_file = self.versions_dir / f"{version_id}.json"
            with open(version_file, "w") as f:
                json.dump(asdict(version), f, indent=2, default=str)

            # Update metadata
            metadata_entry = {
                "version_id": version_id,
                "layer": layer,
                "timestamp": timestamp,
                "user": user,
                "description": description,
                "content_hash": content_hash,
                "file_path": file_path,
                "row_count": row_count,
                "file_size_bytes": file_size_bytes,
            }
            self.metadata.append(metadata_entry)
            self._save_metadata()

            return version_id

    def get_version(self, version_id: str) -> Optional[STTMVersion]:
        """Retrieve a specific version"""
        version_file = self.versions_dir / f"{version_id}.json"
        if version_file.exists():
            with open(version_file, "r") as f:
                data = json.load(f)
                return STTMVersion(**data)
        return None

    def _get_last_version(self, layer: str) -> Optional[Dict[str, Any]]:
        """Get most recent version for a layer"""
        layer_versions = [v for v in self.metadata if v["layer"] == layer]
        if layer_versions:
            return sorted(layer_versions, key=lambda x: x["timestamp"])[-1]
        return None

    def get_version_history(self, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get version history, optionally filtered by layer"""
        if layer:
            history = [v for v in self.metadata if v["layer"] == layer]
        else:
            history = self.metadata

        # Sort by timestamp descending (newest first)
        return sorted(history, key=lambda x: x["timestamp"], reverse=True)

    def get_versions_by_layer(self, layer: str) -> List[Dict[str, Any]]:
        """Get all versions for a specific layer"""
        return self.get_version_history(layer)

    def diff_versions(self, version_id_1: str, version_id_2: str) -> str:
        """
        Compare two versions and return unified diff.
        Returns multi-line string with differences.
        """
        v1 = self.get_version(version_id_1)
        v2 = self.get_version(version_id_2)

        if not v1 or not v2:
            return "Version not found"

        # Format content as JSON lines for better diff
        content1_lines = json.dumps(v1.sttm_content, indent=2, sort_keys=True).split("\n")
        content2_lines = json.dumps(v2.sttm_content, indent=2, sort_keys=True).split("\n")

        # Generate unified diff
        diff_lines = unified_diff(
            content1_lines,
            content2_lines,
            fromfile=f"{version_id_1}",
            tofile=f"{version_id_2}",
            lineterm="",
        )

        return "\n".join(diff_lines)

    def restore_version(
        self, version_id: str, user: str = "system", restore_reason: str = "Manual restore"
    ) -> bool:
        """
        Restore STTM rules from a previous version.
        Creates a new version entry pointing to the restored content.
        Returns True if successful.
        """
        with self.lock:
            old_version = self.get_version(version_id)
            if not old_version:
                return False

            # Create new version with restored content
            restored_version_id = self.save_version(
                layer=old_version.layer,
                sttm_content=old_version.sttm_content,
                file_path=old_version.file_path,
                user=user,
                description=f"Restored from {version_id}: {restore_reason}",
            )

            return restored_version_id is not None

    def get_version_stats(self) -> Dict[str, Any]:
        """Get statistics about version history"""
        return {
            "total_versions": len(self.metadata),
            "layers": list(set(v["layer"] for v in self.metadata)),
            "versions_by_layer": {
                layer: len([v for v in self.metadata if v["layer"] == layer])
                for layer in set(v["layer"] for v in self.metadata)
            },
            "total_storage_bytes": sum(v.get("file_size_bytes", 0) for v in self.metadata),
            "users": list(set(v["user"] for v in self.metadata)),
        }

    def get_change_summary(self, version_id: str) -> Dict[str, Any]:
        """
        Get summary of changes in this version compared to previous.
        Shows: what changed, rows affected, metadata.
        """
        current_version = self.get_version(version_id)
        if not current_version:
            return {}

        # Find previous version for same layer
        layer_versions = sorted(
            [v for v in self.metadata if v["layer"] == current_version.layer],
            key=lambda x: x["timestamp"],
        )

        current_idx = next(
            (i for i, v in enumerate(layer_versions) if v["version_id"] == version_id), -1
        )

        summary = {
            "version_id": version_id,
            "layer": current_version.layer,
            "timestamp": current_version.timestamp,
            "user": current_version.user,
            "description": current_version.description,
            "row_count": current_version.row_count,
            "file_size_bytes": current_version.file_size_bytes,
            "is_first_version": current_idx == 0,
        }

        # If not first version, compute delta
        if current_idx > 0:
            prev_meta = layer_versions[current_idx - 1]
            prev_version = self.get_version(prev_meta["version_id"])

            if prev_version:
                # Calculate differences
                prev_keys = set(prev_version.sttm_content.keys())
                curr_keys = set(current_version.sttm_content.keys())

                summary["added_rules"] = len(curr_keys - prev_keys)
                summary["removed_rules"] = len(prev_keys - curr_keys)
                summary["modified_rules"] = sum(
                    1
                    for key in curr_keys & prev_keys
                    if prev_version.sttm_content[key] != current_version.sttm_content[key]
                )
                summary["previous_version_id"] = prev_meta["version_id"]
                summary["size_change_bytes"] = (
                    current_version.file_size_bytes - prev_version.file_size_bytes
                )

        return summary

    def export_version_as_csv(self, version_id: str, output_path: Path) -> bool:
        """Export version content as CSV for external use"""
        version = self.get_version(version_id)
        if not version:
            return False

        import csv

        try:
            with open(output_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Rule", "Transformation", "Version", "Timestamp"])

                for rule_name, rule_content in version.sttm_content.items():
                    rule_str = json.dumps(rule_content) if isinstance(rule_content, dict) else str(
                        rule_content
                    )
                    writer.writerow([rule_name, rule_str, version_id, version.timestamp])

            return True
        except Exception:
            return False

    def clear_old_versions(self, keep_count: int = 10, layer: Optional[str] = None) -> int:
        """
        Remove old versions, keeping only most recent N.
        Returns number of versions deleted.
        """
        with self.lock:
            if layer:
                layer_versions = sorted(
                    [v for v in self.metadata if v["layer"] == layer],
                    key=lambda x: x["timestamp"],
                    reverse=True,
                )
            else:
                layer_versions = sorted(self.metadata, key=lambda x: x["timestamp"], reverse=True)

            deleted_count = 0

            # Delete old versions
            for version_meta in layer_versions[keep_count:]:
                version_id = version_meta["version_id"]
                version_file = self.versions_dir / f"{version_id}.json"

                if version_file.exists():
                    version_file.unlink()
                    deleted_count += 1

                # Remove from metadata
                self.metadata = [v for v in self.metadata if v["version_id"] != version_id]

            self._save_metadata()
            return deleted_count


# Global singleton
_version_manager: Optional[STTMVersionManager] = None
_manager_lock = threading.Lock()


def get_version_manager() -> STTMVersionManager:
    """Get or create the global version manager singleton"""
    global _version_manager

    if _version_manager is None:
        with _manager_lock:
            if _version_manager is None:
                _version_manager = STTMVersionManager()

    return _version_manager
