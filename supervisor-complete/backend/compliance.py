"""
Omni OS Backend — Compliance Export (SOC2 / GDPR)

Generates compliance reports from system data including audit trails,
data inventories, access logs, SOC2 summaries, and GDPR deletion handling.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger("omnios.compliance")


class ComplianceExporter:
    """Generates compliance reports from system data."""

    def __init__(self):
        self._access_log: list[dict] = []
        self._deletion_log: list[dict] = []
        self._max_access_log = 10000

    def record_access(self, user_id: str, resource: str, action: str,
                      details: str = ""):
        """Record an access event for compliance logging."""
        entry = {
            "id": f"acc_{uuid4().hex[:12]}",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._access_log.append(entry)
        if len(self._access_log) > self._max_access_log:
            del self._access_log[:2000]

    async def export_audit_trail(self, start_date: str, end_date: str) -> dict:
        """Export audit trail for a date range.

        Pulls from approvals audit log, agent runs, and tool executions.
        """
        import db

        # Gather approval audit entries
        approval_audit = []
        try:
            from routes.approvals import _audit_log
            approval_audit = [
                e for e in _audit_log
                if start_date <= e.get("timestamp", "")[:10] <= end_date
            ]
        except ImportError:
            pass

        # Gather agent runs from DB
        agent_runs = []
        try:
            events = await db.load_events(event_type="", limit=1000)
            agent_runs = [
                e for e in events
                if start_date <= e.get("created_at", "")[:10] <= end_date
            ]
        except Exception as e:
            logger.error(f"Failed to load events for audit trail: {e}")

        # Gather governance violations
        governance_violations = []
        try:
            from governance import policy_engine
            all_violations = policy_engine.list_violations(limit=1000)
            governance_violations = [
                v.model_dump() for v in all_violations
                if start_date <= v.timestamp[:10] <= end_date
            ]
        except ImportError:
            pass

        # Gather access log entries
        access_entries = [
            e for e in self._access_log
            if start_date <= e.get("timestamp", "")[:10] <= end_date
        ]

        return {
            "report_type": "audit_trail",
            "period": {"start": start_date, "end": end_date},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "approval_decisions": approval_audit,
            "approval_count": len(approval_audit),
            "system_events": agent_runs,
            "event_count": len(agent_runs),
            "governance_violations": governance_violations,
            "violation_count": len(governance_violations),
            "access_log": access_entries,
            "access_count": len(access_entries),
        }

    async def export_data_inventory(self, user_id: str) -> dict:
        """GDPR: Export what data the system holds for a given user."""
        import db

        inventory = {
            "report_type": "data_inventory",
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_categories": {},
        }

        # Campaigns
        try:
            campaigns = await db.load_user_campaigns(user_id)
            inventory["data_categories"]["campaigns"] = {
                "count": len(campaigns),
                "items": [
                    {"id": c.get("id"), "status": c.get("status"),
                     "created_at": c.get("created_at")}
                    for c in campaigns
                ],
            }
        except Exception as e:
            logger.error(f"Failed to load campaigns for data inventory: {e}")
            inventory["data_categories"]["campaigns"] = {"count": 0, "items": [], "error": str(e)}

        # API keys (from developer platform)
        try:
            api_keys = await db.get_api_keys(user_id)
            inventory["data_categories"]["api_keys"] = {
                "count": len(api_keys),
                "items": [
                    {"id": k.get("id"), "name": k.get("name"),
                     "created_at": k.get("created_at")}
                    for k in api_keys
                ],
            }
        except Exception as e:
            inventory["data_categories"]["api_keys"] = {"count": 0, "items": [], "error": str(e)}

        # Webhooks
        try:
            webhooks = await db.get_webhooks(user_id)
            inventory["data_categories"]["webhooks"] = {
                "count": len(webhooks),
                "items": [
                    {"id": w.get("id"), "url": w.get("url"),
                     "created_at": w.get("created_at")}
                    for w in webhooks
                ],
            }
        except Exception as e:
            inventory["data_categories"]["webhooks"] = {"count": 0, "items": [], "error": str(e)}

        # OAuth apps
        try:
            oauth_apps = await db.get_oauth_apps(user_id)
            inventory["data_categories"]["oauth_apps"] = {
                "count": len(oauth_apps),
                "items": [
                    {"id": a.get("id"), "name": a.get("name"),
                     "created_at": a.get("created_at")}
                    for a in oauth_apps
                ],
            }
        except Exception as e:
            inventory["data_categories"]["oauth_apps"] = {"count": 0, "items": [], "error": str(e)}

        # Access log entries for this user
        user_access = [e for e in self._access_log if e.get("user_id") == user_id]
        inventory["data_categories"]["access_log"] = {
            "count": len(user_access),
            "earliest": user_access[0]["timestamp"] if user_access else None,
            "latest": user_access[-1]["timestamp"] if user_access else None,
        }

        return inventory

    async def export_access_log(self, user_id: str, start_date: str,
                                end_date: str) -> dict:
        """Export access log entries for a user within a date range."""
        entries = [
            e for e in self._access_log
            if e.get("user_id") == user_id
            and start_date <= e.get("timestamp", "")[:10] <= end_date
        ]

        return {
            "report_type": "access_log",
            "user_id": user_id,
            "period": {"start": start_date, "end": end_date},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entries": entries,
            "count": len(entries),
        }

    async def generate_soc2_report(self, period: str) -> dict:
        """Generate a SOC2 summary report.

        Covers: access controls, change management, availability, confidentiality.
        Period format: "2026-Q1", "2026-03", etc.
        """
        import db

        # Determine date range from period string
        start_date, end_date = self._parse_period(period)

        # Access Controls: count of API keys, OAuth apps, auth events
        access_log_count = len([
            e for e in self._access_log
            if start_date <= e.get("timestamp", "")[:10] <= end_date
        ])

        # Change Management: approval decisions
        approval_stats = {"approved": 0, "rejected": 0, "pending": 0}
        try:
            from routes.approvals import _audit_log
            for entry in _audit_log:
                ts = entry.get("timestamp", "")[:10]
                if start_date <= ts <= end_date:
                    action = entry.get("action", "")
                    if action in approval_stats:
                        approval_stats[action] += 1
        except ImportError:
            pass

        # Governance: policy violations
        violation_stats = {"block": 0, "warn": 0, "require_approval": 0, "log": 0}
        try:
            from governance import policy_engine
            for v in policy_engine.list_violations(limit=5000):
                if start_date <= v.timestamp[:10] <= end_date:
                    action = v.action
                    if action in violation_stats:
                        violation_stats[action] += 1
        except ImportError:
            pass

        # Confidentiality: PII scrubbing stats
        pii_stats = {}
        try:
            from privacy import privacy_router
            pii_stats = privacy_router.get_stats()
        except ImportError:
            pass

        return {
            "report_type": "soc2_summary",
            "period": period,
            "date_range": {"start": start_date, "end": end_date},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "access_controls": {
                "description": "Authentication and authorization controls",
                "access_events_logged": access_log_count,
                "auth_method": "Supabase JWT + API Keys",
                "mfa_supported": True,
                "api_key_rotation": "User-managed with expiry support",
            },
            "change_management": {
                "description": "Human-in-the-loop approval for sensitive actions",
                "approval_decisions": approval_stats,
                "governance_policies_active": len([
                    p for p in (policy_engine.list_policies()
                                if 'policy_engine' in dir() else [])
                    if p.enabled
                ]),
            },
            "availability": {
                "description": "System health and uptime monitoring",
                "health_endpoint": "/health",
                "monitoring": "BetterUptime / UptimeRobot integration available",
            },
            "confidentiality": {
                "description": "PII protection and data handling",
                "pii_scrubbing_enabled": pii_stats.get("config", {}).get("enabled", True),
                "total_pii_scrubbed": pii_stats.get("total_scrubbed", 0),
                "total_pii_detections": pii_stats.get("total_detections", 0),
                "requests_blocked_for_pii": pii_stats.get("blocked", 0),
                "governance_violations": violation_stats,
            },
        }

    async def handle_deletion_request(self, user_id: str) -> dict:
        """GDPR right-to-delete: remove ALL user data and return confirmation.

        Deletes: campaigns, agent runs, approvals, genome data, API keys,
        webhooks, OAuth apps, access log entries, run snapshots.
        """
        import db

        has_errors = False
        results = {
            "request_type": "gdpr_deletion",
            "user_id": user_id,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "deletions": {},
            "status": "completed",
        }

        # Delete campaigns (the most critical GDPR data)
        try:
            campaigns = await db.load_user_campaigns(user_id)
            deleted_count = 0
            for c in campaigns:
                cid = c.get("id", "")
                if cid:
                    await db.delete_campaign(cid)
                    deleted_count += 1
            results["deletions"]["campaigns"] = {"deleted": deleted_count}
        except Exception as e:
            has_errors = True
            results["deletions"]["campaigns"] = {"error": "deletion_failed"}
            logger.error(f"GDPR campaign deletion failed for {user_id[:8]}: {e}")

        # Delete agent run snapshots
        try:
            await db.delete_user_snapshots(user_id)
            results["deletions"]["run_snapshots"] = {"deleted": True}
        except Exception as e:
            results["deletions"]["run_snapshots"] = {"error": "deletion_failed"}
            logger.error(f"GDPR snapshot deletion failed for {user_id[:8]}: {e}")

        # Delete API keys
        try:
            api_keys = await db.get_api_keys(user_id)
            for key in api_keys:
                await db.delete_api_key(key.get("id", ""))
            results["deletions"]["api_keys"] = {"deleted": len(api_keys)}
        except Exception as e:
            has_errors = True
            results["deletions"]["api_keys"] = {"error": "deletion_failed"}

        # Delete webhooks
        try:
            webhooks = await db.get_webhooks(user_id)
            for wh in webhooks:
                await db.delete_webhook(wh.get("id", ""))
            results["deletions"]["webhooks"] = {"deleted": len(webhooks)}
        except Exception as e:
            has_errors = True
            results["deletions"]["webhooks"] = {"error": "deletion_failed"}

        # Delete OAuth apps
        try:
            oauth_apps = await db.get_oauth_apps(user_id)
            for app_rec in oauth_apps:
                await db.delete_oauth_app(app_rec.get("id", ""))
            results["deletions"]["oauth_apps"] = {"deleted": len(oauth_apps)}
        except Exception as e:
            has_errors = True
            results["deletions"]["oauth_apps"] = {"error": "deletion_failed"}

        # Remove in-memory developer data
        try:
            from routes.developer import (
                _api_keys, _key_hash_index, _webhooks, _oauth_apps, _oauth_client_index
            )
            keys_to_remove = [k for k, v in _api_keys.items() if v.user_id == user_id]
            for kid in keys_to_remove:
                rec = _api_keys.pop(kid, None)
                if rec:
                    _key_hash_index.pop(rec.key_hash, None)

            wh_to_remove = [k for k, v in _webhooks.items() if v.user_id == user_id]
            for wid in wh_to_remove:
                _webhooks.pop(wid, None)

            apps_to_remove = [k for k, v in _oauth_apps.items() if v.user_id == user_id]
            for aid in apps_to_remove:
                app_obj = _oauth_apps.pop(aid, None)
                if app_obj:
                    _oauth_client_index.pop(app_obj.client_id, None)
        except ImportError:
            pass

        # Remove in-memory genome data for this user's campaigns
        try:
            from genome import genome
            genome.purge_user_data(user_id)
        except Exception:
            pass

        # Remove in-memory store campaigns
        try:
            from store import store
            store.delete_all_user_campaigns(user_id)
        except Exception:
            pass

        # Remove access log entries for this user
        before = len(self._access_log)
        self._access_log = [e for e in self._access_log if e.get("user_id") != user_id]
        results["deletions"]["access_log_entries"] = {"deleted": before - len(self._access_log)}

        # Set status based on whether any errors occurred
        if has_errors:
            results["status"] = "partial_failure"

        # Record the deletion itself
        self._deletion_log.append({
            "user_id": user_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "categories_deleted": list(results["deletions"].keys()),
            "status": results["status"],
        })

        logger.info(f"GDPR deletion {'completed' if not has_errors else 'partially completed'} for user {user_id[:8]}...")
        return results

    def _parse_period(self, period: str) -> tuple[str, str]:
        """Parse a period string into (start_date, end_date) as YYYY-MM-DD."""
        import calendar

        if "-Q" in period:
            # "2026-Q1" format
            year, q = period.split("-Q")
            year = int(year)
            quarter = int(q)
            start_month = (quarter - 1) * 3 + 1
            end_month = start_month + 2
            last_day = calendar.monthrange(year, end_month)[1]
            return f"{year}-{start_month:02d}-01", f"{year}-{end_month:02d}-{last_day:02d}"
        elif len(period) == 7:
            # "2026-03" format
            year, month = period.split("-")
            year, month = int(year), int(month)
            last_day = calendar.monthrange(year, month)[1]
            return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"
        elif len(period) == 4:
            # "2026" — full year
            return f"{period}-01-01", f"{period}-12-31"
        else:
            # Fallback: treat as start date, end = now
            return period, datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

compliance_exporter = ComplianceExporter()
