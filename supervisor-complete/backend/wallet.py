"""
Omni OS Backend — Agent Wallet & Budget Management
Manages per-agent budget allocations and spend tracking.

Security: asyncio.Lock per campaign prevents TOCTOU race conditions.
All spend is persisted to Supabase for audit trail survival across restarts.
"""
from __future__ import annotations
import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from models import SpendEntry

logger = logging.getLogger("supervisor.wallet")


def _get_db():
    """Lazy import to avoid circular dependency."""
    import db
    return db


class AgentWallet:
    """Manages per-agent budget allocations and spend tracking.

    Thread safety: one asyncio.Lock per campaign_id ensures atomic
    reserve-and-spend operations.
    """

    def __init__(self):
        # campaign_id -> agent_id -> budget info
        self._budgets: dict[str, dict[str, dict]] = {}
        # campaign_id -> list of spend entries
        self._spend_log: dict[str, list[SpendEntry]] = {}
        # Per-campaign locks for atomic budget operations (CRITICAL-01/02 fix)
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def allocate_budget(self, campaign_id: str, agent_id: str,
                               amount: float, period: str = "monthly") -> dict:
        """Set weekly/monthly budget for an agent."""
        async with self._locks[campaign_id]:
            if campaign_id not in self._budgets:
                self._budgets[campaign_id] = {}

            self._budgets[campaign_id][agent_id] = {
                "allocated": amount,
                "spent": 0.0,
                "period": period,
                "updated_at": datetime.utcnow().isoformat(),
            }

        logger.info(f"Budget allocated: {agent_id} = ${amount:.2f}/{period} for campaign {campaign_id[:8]}")
        return {"allocated": True, "agent_id": agent_id, "amount": amount, "period": period}

    async def reserve_and_spend(self, campaign_id: str, agent_id: str,
                                 amount: float, tool: str, description: str,
                                 approval_threshold: float = 100.0) -> dict:
        """Atomic budget check + reservation. Prevents TOCTOU race conditions.

        Returns {"approved": bool, "entry": SpendEntry|None, "reason": str}.
        If approved, spend is already recorded — no separate record_spend needed.
        """
        async with self._locks[campaign_id]:
            budget = self._budgets.get(campaign_id, {}).get(agent_id)

            if not budget:
                if amount > approval_threshold:
                    return {"approved": False, "entry": None,
                            "reason": f"${amount:.2f} exceeds ${approval_threshold:.2f} threshold with no budget set"}
                # Auto-approve small amounts with no budget — still record it
                entry = await self._record_spend_locked(
                    campaign_id, agent_id, amount, tool, description)
                return {"approved": True, "entry": entry,
                        "reason": "Below threshold, no budget cap set"}

            remaining = budget["allocated"] - budget["spent"]

            if amount > remaining:
                return {"approved": False, "entry": None,
                        "reason": f"Requested ${amount:.2f} but only ${remaining:.2f} remaining"}

            if amount > approval_threshold:
                return {"approved": False, "entry": None,
                        "reason": f"Amount ${amount:.2f} exceeds auto-approval threshold"}

            # Approved — atomically deduct and record
            entry = await self._record_spend_locked(
                campaign_id, agent_id, amount, tool, description)
            return {"approved": True, "entry": entry,
                    "reason": f"Within budget (${remaining - amount:.2f} remaining)"}

    async def _record_spend_locked(self, campaign_id: str, agent_id: str,
                                    amount: float, tool: str, description: str,
                                    approved_by: str = "auto") -> SpendEntry:
        """Record spend while already holding the campaign lock."""
        entry = SpendEntry(
            campaign_id=campaign_id,
            agent_id=agent_id,
            amount=amount,
            tool=tool,
            description=description,
            approved_by=approved_by,
        )

        if campaign_id not in self._spend_log:
            self._spend_log[campaign_id] = []
        self._spend_log[campaign_id].append(entry)

        # Update budget spent
        if campaign_id in self._budgets and agent_id in self._budgets[campaign_id]:
            self._budgets[campaign_id][agent_id]["spent"] += amount

        # Persist to database (CRITICAL-05 fix: survive restarts)
        try:
            db = _get_db()
            await db.save_spend_entry(entry.model_dump() if hasattr(entry, 'model_dump') else {
                "campaign_id": campaign_id, "agent_id": agent_id,
                "amount": amount, "tool": tool, "description": description,
                "approved_by": approved_by,
            })
        except Exception as e:
            logger.warning(f"Spend persistence failed (in-memory still updated): {e}")

        logger.info(f"Spend recorded: {agent_id} spent ${amount:.2f} via {tool} ({description})")
        return entry

    async def request_spend(self, campaign_id: str, agent_id: str,
                             amount: float, description: str,
                             approval_threshold: float = 100.0) -> dict:
        """Check if spend is within budget. Returns approval status.

        NOTE: For atomic check+spend, prefer reserve_and_spend() instead.
        This method is retained for backward compatibility but uses locking.
        """
        async with self._locks[campaign_id]:
            budget = self._budgets.get(campaign_id, {}).get(agent_id)

            if not budget:
                if amount <= approval_threshold:
                    return {"approved": True, "method": "auto", "reason": "Below threshold, no budget cap set"}
                return {"approved": False, "method": "requires_approval",
                        "reason": f"${amount:.2f} exceeds ${approval_threshold:.2f} threshold with no budget set"}

            remaining = budget["allocated"] - budget["spent"]

            if amount <= remaining:
                if amount <= approval_threshold:
                    return {"approved": True, "method": "auto",
                            "reason": f"Within budget (${remaining:.2f} remaining)"}
                return {"approved": False, "method": "requires_approval",
                        "reason": f"Amount ${amount:.2f} exceeds auto-approval threshold"}

            return {"approved": False, "method": "over_budget",
                    "reason": f"Requested ${amount:.2f} but only ${remaining:.2f} remaining"}

    async def record_spend(self, campaign_id: str, agent_id: str,
                            amount: float, tool: str, description: str,
                            approved_by: str = "auto") -> SpendEntry:
        """Record actual spend with full attribution."""
        async with self._locks[campaign_id]:
            return await self._record_spend_locked(
                campaign_id, agent_id, amount, tool, description, approved_by)

    async def get_balance(self, campaign_id: str, agent_id: str) -> dict:
        """Current budget remaining, total spent, ROI if measurable."""
        budget = self._budgets.get(campaign_id, {}).get(agent_id)
        if not budget:
            total_spent = sum(e.amount for e in self._spend_log.get(campaign_id, [])
                            if e.agent_id == agent_id)
            return {"agent_id": agent_id, "allocated": 0, "spent": total_spent,
                    "remaining": 0, "has_budget": False}

        return {
            "agent_id": agent_id,
            "allocated": budget["allocated"],
            "spent": budget["spent"],
            "remaining": budget["allocated"] - budget["spent"],
            "period": budget["period"],
            "has_budget": True,
        }

    async def get_campaign_summary(self, campaign_id: str) -> dict:
        """Full budget summary for a campaign."""
        budgets = self._budgets.get(campaign_id, {})
        spend_log = self._spend_log.get(campaign_id, [])

        total_allocated = sum(b["allocated"] for b in budgets.values())
        total_spent = sum(e.amount for e in spend_log)

        by_agent = {}
        for agent_id, budget in budgets.items():
            agent_spend = sum(e.amount for e in spend_log if e.agent_id == agent_id)
            by_agent[agent_id] = {
                "allocated": budget["allocated"],
                "spent": agent_spend,
                "remaining": budget["allocated"] - agent_spend,
            }

        # Include agents with spend but no budget
        for entry in spend_log:
            if entry.agent_id not in by_agent:
                agent_spend = sum(e.amount for e in spend_log if e.agent_id == entry.agent_id)
                by_agent[entry.agent_id] = {
                    "allocated": 0, "spent": agent_spend, "remaining": 0,
                }

        return {
            "campaign_id": campaign_id,
            "total_allocated": total_allocated,
            "total_spent": total_spent,
            "total_remaining": total_allocated - total_spent,
            "by_agent": by_agent,
            "transaction_count": len(spend_log),
        }

    async def reallocate(self, campaign_id: str, from_agent: str,
                          to_agent: str, amount: float) -> dict:
        """Move budget between agents (Supervisor meta-agent does this)."""
        budgets = self._budgets.get(campaign_id, {})
        from_budget = budgets.get(from_agent)
        to_budget = budgets.get(to_agent)

        if not from_budget:
            return {"success": False, "error": f"No budget set for {from_agent}"}

        remaining = from_budget["allocated"] - from_budget["spent"]
        if amount > remaining:
            return {"success": False,
                    "error": f"Only ${remaining:.2f} available to reallocate from {from_agent}"}

        from_budget["allocated"] -= amount
        if to_budget:
            to_budget["allocated"] += amount
        else:
            budgets[to_agent] = {
                "allocated": amount, "spent": 0.0,
                "period": from_budget["period"],
                "updated_at": datetime.utcnow().isoformat(),
            }

        logger.info(f"Budget reallocated: ${amount:.2f} from {from_agent} to {to_agent}")
        return {"success": True, "from_agent": from_agent, "to_agent": to_agent, "amount": amount}

    async def get_spend_log(self, campaign_id: str, agent_id: Optional[str] = None,
                             limit: int = 50) -> list[dict]:
        """Get spend log entries."""
        entries = self._spend_log.get(campaign_id, [])
        if agent_id:
            entries = [e for e in entries if e.agent_id == agent_id]
        entries = sorted(entries, key=lambda e: e.created_at, reverse=True)[:limit]
        return [e.model_dump() for e in entries]


wallet = AgentWallet()
