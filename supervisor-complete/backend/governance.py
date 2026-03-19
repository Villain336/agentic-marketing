"""
Omni OS Backend — Policy-as-Code Governance Framework

Evaluates governance policies against agent actions to enforce spend limits,
time-of-day restrictions, approval requirements, and PII blocking.

Uses safe expression evaluation (AST-based) — never exec/eval of arbitrary code.
"""
from __future__ import annotations

import ast
import logging
import operator
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger("omnios.governance")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class Policy(BaseModel):
    """A single governance policy that agents must follow."""
    id: str = Field(default_factory=lambda: f"pol_{uuid4().hex[:12]}")
    name: str = ""
    description: str = ""
    scope: str = "global"  # "global", "agent:{id}", "tool:{name}", "campaign:{id}"
    condition: str = ""  # Safe expression evaluated against context
    action: str = "block"  # "block", "warn", "require_approval", "log"
    enabled: bool = True
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyViolation(BaseModel):
    """Result of a policy evaluation that found a violation."""
    id: str = Field(default_factory=lambda: f"viol_{uuid4().hex[:12]}")
    policy_id: str = ""
    policy_name: str = ""
    action: str = ""  # "block", "warn", "require_approval", "log"
    message: str = ""
    context_summary: dict = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ═══════════════════════════════════════════════════════════════════════════════
# SAFE EXPRESSION EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

# Allowed operators for safe expression evaluation
_SAFE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.And: None,  # handled specially
    ast.Or: None,   # handled specially
    ast.Not: operator.not_,
    ast.Add: operator.add,
    ast.Sub: operator.sub,
}


def _safe_eval_node(node: ast.AST, context: dict) -> Any:
    """Recursively evaluate an AST node against a context dict.

    Only allows: comparisons, boolean logic, names (from context), constants,
    lists, and basic arithmetic. No function calls, attribute access, or imports.
    """
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body, context)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        # Allow True/False/None as names
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
        raise ValueError(f"Unknown variable: {node.id}")

    if isinstance(node, ast.List):
        return [_safe_eval_node(elt, context) for elt in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_safe_eval_node(elt, context) for elt in node.elts)

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _safe_eval_node(node.operand, context)
        if isinstance(node.op, ast.USub):
            return -_safe_eval_node(node.operand, context)
        raise ValueError(f"Unsupported unary op: {type(node.op).__name__}")

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_safe_eval_node(v, context) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_safe_eval_node(v, context) for v in node.values)
        raise ValueError(f"Unsupported bool op: {type(node.op).__name__}")

    if isinstance(node, ast.BinOp):
        left = _safe_eval_node(node.left, context)
        right = _safe_eval_node(node.right, context)
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"Unsupported binary op: {op_type.__name__}")
        return _SAFE_OPS[op_type](left, right)

    if isinstance(node, ast.Compare):
        left = _safe_eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _safe_eval_node(comparator, context)
            op_type = type(op)
            if op_type not in _SAFE_OPS:
                raise ValueError(f"Unsupported comparison: {op_type.__name__}")
            if not _SAFE_OPS[op_type](left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.IfExp):
        test = _safe_eval_node(node.test, context)
        return _safe_eval_node(node.body, context) if test else _safe_eval_node(node.orelse, context)

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def safe_eval(expression: str, context: dict) -> bool:
    """Safely evaluate a Python expression against a context dict.

    Supports: comparisons, boolean logic, 'in'/'not in', constants, lists,
    and variable references from context. No function calls or attribute access.

    Returns True if the condition matches (i.e., the policy is violated).
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}")

    # Security: walk the AST and reject dangerous node types
    for node in ast.walk(tree):
        if isinstance(node, (ast.Call, ast.Attribute, ast.Subscript,
                             ast.Lambda, ast.Dict, ast.Set,
                             ast.ListComp, ast.SetComp, ast.DictComp,
                             ast.GeneratorExp, ast.Await,
                             ast.JoinedStr, ast.FormattedValue)):
            raise ValueError(f"Forbidden expression element: {type(node).__name__}")

    return bool(_safe_eval_node(tree, context))


# ═══════════════════════════════════════════════════════════════════════════════
# PII DETECTION HELPER (uses patterns from privacy.py)
# ═══════════════════════════════════════════════════════════════════════════════

def _check_pii_in_content(content: str) -> bool:
    """Check if content contains PII using patterns from the privacy module."""
    try:
        from privacy import PII_PATTERNS
    except ImportError:
        PII_PATTERNS = {}

    for pii_type, config in PII_PATTERNS.items():
        if re.search(config["pattern"], content, re.IGNORECASE):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyEngine:
    """Evaluates policies against agent actions."""

    def __init__(self):
        self._policies: dict[str, Policy] = {}
        self._violations: list[PolicyViolation] = []
        self._max_violations = 5000

        # Load default policies
        self._load_defaults()

    def _load_defaults(self):
        """Install the four default policies."""
        defaults = [
            Policy(
                id="pol_max_spend_50",
                name="Max spend per tool call: $50",
                description="Block any single tool call that would spend more than $50",
                scope="global",
                condition="spend_amount > 50",
                action="block",
                enabled=True,
                created_by="system",
            ),
            Policy(
                id="pol_no_night_emails",
                name="No outbound emails 10pm-7am",
                description="Block outbound email sends between 22:00 and 07:00 UTC",
                scope="tool:send_email",
                condition="hour >= 22 or hour < 7",
                action="block",
                enabled=True,
                created_by="system",
            ),
            Policy(
                id="pol_infra_approval",
                name="Infrastructure changes require approval",
                description="Require human approval for any infrastructure-modifying tool call",
                scope="global",
                condition="tool_name in ['deploy_site', 'update_dns', 'create_instance', "
                          "'delete_instance', 'modify_security_group', 'create_stack', "
                          "'delete_stack', 'scale_cluster']",
                action="require_approval",
                enabled=True,
                created_by="system",
            ),
            Policy(
                id="pol_pii_outbound_block",
                name="PII in outbound content — block",
                description="Block outbound content (emails, social posts) that contains detected PII",
                scope="global",
                condition="has_pii == True",
                action="block",
                enabled=True,
                created_by="system",
            ),
        ]
        for p in defaults:
            self._policies[p.id] = p

    # -- CRUD ------------------------------------------------------------------

    def add_policy(self, policy: Policy) -> Policy:
        """Add or update a policy."""
        self._policies[policy.id] = policy
        logger.info(f"Policy added/updated: {policy.id} — {policy.name}")
        return policy

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy by ID. Returns True if removed."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            logger.info(f"Policy removed: {policy_id}")
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a single policy by ID."""
        return self._policies.get(policy_id)

    def list_policies(self) -> list[Policy]:
        """List all registered policies."""
        return list(self._policies.values())

    # -- Evaluation ------------------------------------------------------------

    def evaluate(self, context: dict) -> list[PolicyViolation]:
        """Evaluate all applicable policies against the given context.

        Context keys may include:
            agent_id, tool_name, tool_input, campaign_id, user_id,
            spend_amount, hour (0-23), has_pii, content, ...

        Returns a list of PolicyViolation for any policies that fire.
        """
        violations: list[PolicyViolation] = []

        # Enrich context with derived fields
        enriched = self._enrich_context(context)

        for policy in self._policies.values():
            if not policy.enabled:
                continue

            # Check scope applicability
            if not self._scope_matches(policy, enriched):
                continue

            # Evaluate condition
            try:
                fired = safe_eval(policy.condition, enriched)
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Policy {policy.id} condition error: {e}")
                continue

            if fired:
                violation = PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    action=policy.action,
                    message=f"Policy '{policy.name}' triggered: {policy.condition}",
                    context_summary={
                        k: v for k, v in enriched.items()
                        if k in ("agent_id", "tool_name", "campaign_id",
                                 "spend_amount", "hour", "has_pii", "user_id")
                    },
                )
                violations.append(violation)
                self._record_violation(violation)

        return violations

    def _enrich_context(self, context: dict) -> dict:
        """Add derived fields to the evaluation context."""
        enriched = dict(context)

        # Add current hour if not provided
        if "hour" not in enriched:
            enriched["hour"] = datetime.now(timezone.utc).hour

        # Add spend_amount default
        if "spend_amount" not in enriched:
            enriched["spend_amount"] = 0.0

        # Detect PII in content if present
        if "has_pii" not in enriched:
            content = enriched.get("content", "")
            tool_input = enriched.get("tool_input", {})
            text_to_check = content
            if isinstance(tool_input, dict):
                text_to_check += " " + " ".join(
                    str(v) for v in tool_input.values() if isinstance(v, str)
                )
            enriched["has_pii"] = _check_pii_in_content(text_to_check) if text_to_check.strip() else False

        return enriched

    def _scope_matches(self, policy: Policy, context: dict) -> bool:
        """Check if a policy's scope matches the current context."""
        scope = policy.scope

        if scope == "global":
            return True

        if scope.startswith("agent:"):
            return context.get("agent_id") == scope.split(":", 1)[1]

        if scope.startswith("tool:"):
            return context.get("tool_name") == scope.split(":", 1)[1]

        if scope.startswith("campaign:"):
            return context.get("campaign_id") == scope.split(":", 1)[1]

        return True  # Unknown scope = apply globally

    # -- Violations log --------------------------------------------------------

    def _record_violation(self, violation: PolicyViolation):
        """Record a violation for audit purposes."""
        self._violations.append(violation)
        if len(self._violations) > self._max_violations:
            self._violations = self._violations[-self._max_violations:]
        logger.warning(f"Policy violation: {violation.policy_name} [{violation.action}]")

    def list_violations(self, limit: int = 100, policy_id: str = "") -> list[PolicyViolation]:
        """List recent violations, optionally filtered by policy."""
        violations = self._violations
        if policy_id:
            violations = [v for v in violations if v.policy_id == policy_id]
        return violations[-limit:]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

policy_engine = PolicyEngine()
