"""
Supervisor Backend — Agent Memory Versioning
Tracks what changed between agent runs — diffs, snapshots, rollback support.
"""
from __future__ import annotations
import copy
import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("supervisor.versioning")


class MemoryVersion:
    """A single snapshot of campaign memory after an agent run."""

    def __init__(self, version_id: int, agent_id: str, campaign_id: str,
                 snapshot: dict[str, Any], changes: dict[str, Any]):
        self.version_id = version_id
        self.agent_id = agent_id
        self.campaign_id = campaign_id
        self.snapshot = snapshot        # Full memory state after this run
        self.changes = changes          # Only the fields that changed
        self.created_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "agent_id": self.agent_id,
            "campaign_id": self.campaign_id,
            "changes": self.changes,
            "fields_changed": list(self.changes.keys()),
            "created_at": self.created_at.isoformat(),
        }


class VersionManager:
    """Tracks memory versions per campaign with diff detection."""

    def __init__(self):
        # campaign_id -> list of versions (ordered by version_id)
        self._versions: dict[str, list[MemoryVersion]] = {}
        # campaign_id -> last known memory state for diff computation
        self._last_state: dict[str, dict[str, Any]] = {}

    def snapshot(self, campaign_id: str, agent_id: str,
                 memory_dict: dict[str, Any]) -> MemoryVersion:
        """Take a snapshot after an agent run. Computes diff from last state."""
        if campaign_id not in self._versions:
            self._versions[campaign_id] = []

        previous = self._last_state.get(campaign_id, {})
        changes = self._compute_diff(previous, memory_dict)

        version_id = len(self._versions[campaign_id]) + 1
        version = MemoryVersion(
            version_id=version_id,
            agent_id=agent_id,
            campaign_id=campaign_id,
            snapshot=copy.deepcopy(memory_dict),
            changes=changes,
        )

        self._versions[campaign_id].append(version)
        # Bound per-campaign version history (keep most recent 200)
        if len(self._versions[campaign_id]) > 200:
            self._versions[campaign_id] = self._versions[campaign_id][-200:]
        # Bound total campaigns tracked
        if len(self._versions) > 5000:
            oldest = next(iter(self._versions))
            del self._versions[oldest]
            self._last_state.pop(oldest, None)
        self._last_state[campaign_id] = copy.deepcopy(memory_dict)

        if changes:
            logger.debug(
                f"Memory v{version_id} for campaign {campaign_id} "
                f"after {agent_id}: {list(changes.keys())}"
            )

        return version

    def _compute_diff(self, old: dict, new: dict) -> dict[str, Any]:
        """Compute which fields changed between two memory states."""
        changes = {}
        all_keys = set(list(old.keys()) + list(new.keys()))

        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)

            if old_val != new_val:
                if isinstance(old_val, str) and isinstance(new_val, str):
                    # For string fields, track length change
                    old_len = len(old_val) if old_val else 0
                    new_len = len(new_val) if new_val else 0
                    changes[key] = {
                        "action": "created" if not old_val else "updated",
                        "old_length": old_len,
                        "new_length": new_len,
                        "delta_chars": new_len - old_len,
                        "preview": (new_val[:200] + "...") if new_val and len(new_val) > 200 else new_val,
                    }
                elif isinstance(new_val, (int, float, bool)):
                    changes[key] = {
                        "action": "updated",
                        "old_value": old_val,
                        "new_value": new_val,
                    }
                elif isinstance(new_val, dict):
                    changes[key] = {
                        "action": "created" if not old_val else "updated",
                        "keys_changed": list(new_val.keys()),
                    }
                else:
                    changes[key] = {
                        "action": "created" if old_val is None else "updated",
                        "type": type(new_val).__name__,
                    }

        return changes

    def get_history(self, campaign_id: str, agent_id: str = "",
                    limit: int = 50) -> list[dict]:
        """Get version history for a campaign, optionally filtered by agent."""
        versions = self._versions.get(campaign_id, [])
        if agent_id:
            versions = [v for v in versions if v.agent_id == agent_id]
        return [v.to_dict() for v in versions[-limit:]]

    def get_version(self, campaign_id: str, version_id: int) -> Optional[dict]:
        """Get a specific version's full snapshot."""
        versions = self._versions.get(campaign_id, [])
        for v in versions:
            if v.version_id == version_id:
                return {
                    **v.to_dict(),
                    "snapshot": v.snapshot,
                }
        return None

    def diff_versions(self, campaign_id: str, v1: int, v2: int) -> dict:
        """Diff two specific versions."""
        versions = self._versions.get(campaign_id, [])
        snap1 = snap2 = None
        for v in versions:
            if v.version_id == v1:
                snap1 = v.snapshot
            if v.version_id == v2:
                snap2 = v.snapshot

        if not snap1 or not snap2:
            return {"error": "Version not found"}

        return {
            "from_version": v1,
            "to_version": v2,
            "changes": self._compute_diff(snap1, snap2),
        }

    def get_field_timeline(self, campaign_id: str, field: str) -> list[dict]:
        """Get the timeline of changes for a specific memory field."""
        versions = self._versions.get(campaign_id, [])
        timeline = []
        for v in versions:
            if field in v.changes:
                timeline.append({
                    "version_id": v.version_id,
                    "agent_id": v.agent_id,
                    "change": v.changes[field],
                    "timestamp": v.created_at.isoformat(),
                })
        return timeline

    @property
    def stats(self) -> dict:
        return {
            "campaigns_tracked": len(self._versions),
            "total_versions": sum(len(v) for v in self._versions.values()),
        }


# Singleton
versioner = VersionManager()
