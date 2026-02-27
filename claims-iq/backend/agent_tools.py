"""LLM-callable tools for insurance claims triage.

Six tools that the agent uses to process a claim through the pipeline:
classify_claim, lookup_policy, check_coverage, check_fraud_indicators,
get_adjuster, submit_decision.
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from claims_data import (
    Claim, Policy, Adjuster,
    POLICIES, ADJUSTERS, COVERAGE_MATRIX, SPECIALTY_CATEGORY_MAP,
    check_coverage_rules, get_fraud_risk, get_best_adjuster,
    validate_decision, get_claim, get_policy, get_prior_claims,
)


@dataclass
class ClaimProcessingState:
    """Tracks the processing state for a single claim."""
    claim: dict
    classified: bool = False
    policy_looked_up: bool = False
    coverage_checked: bool = False
    fraud_checked: bool = False
    prior_claims_checked: bool = False
    adjuster_assigned: bool = False
    decision_submitted: bool = False
    steps_taken: int = 0
    result: Optional[str] = None  # "approved" / "denied" / "escalated" / None
    correct: Optional[bool] = None
    rework_count: int = 0  # Times submit_decision was rejected
    classification_result: Optional[str] = None
    assigned_adjuster_id: Optional[str] = None


# Category keywords for classification
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "water_damage": [
        "burst pipe", "pipe burst", "leaking pipe", "plumbing", "dishwasher",
        "washing machine", "supply line", "water heater", "leaked water",
        "water damage", "pipe broke", "faucet", "toilet overflow",
        "internal plumbing", "pipe rupture", "sump pump", "water entered",
        "foundation cracks", "basement walls",
    ],
    "flood": [
        "flooding from rain", "flash flood", "river overflow", "storm surge",
        "creek overflow", "basement flooding from heavy rain", "flood damage",
        "hurricane", "external water", "standing water from storm",
        "flooded by rain", "floodwater", "rainstorm", "heavy rain",
        "water to seep", "basement walls",
    ],
    "fire": [
        "fire", "smoke damage", "electrical fire", "grease fire", "wildfire",
        "arson", "burned", "flames", "kitchen fire",
    ],
    "auto": [
        "collision", "accident", "vehicle", "car", "truck", "hit-and-run",
        "fender bender", "stolen vehicle", "vehicle stolen", "parking lot",
        "highway", "traffic", "rear-end",
    ],
    "property": [
        "tree fell", "roof", "vandalism", "broken window", "burglary",
        "theft", "storm damage", "hail damage", "break-in", "structural",
        "graffiti", "snow accumulation",
    ],
    "liability": [
        "slipped", "tripped", "fell", "dog bite", "injury at property",
        "guest injured", "visitor", "medical bills", "lawsuit",
    ],
    "health": [
        "emergency room", "hospital", "surgery", "medical", "injury",
        "physical therapy", "outpatient", "torn ligament",
    ],
}


def _classify_description(description: str) -> tuple[str, float, list[tuple[str, float]]]:
    """Classify a claim description into a category.

    Returns (category, confidence, ranked_scores) where ranked_scores is a
    list of (category, percentage) pairs sorted by score descending.
    """
    desc_lower = description.lower()
    scores: dict[str, int] = {}

    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in desc_lower)
        if score > 0:
            scores[category] = score

    if not scores:
        return "property", 0.3, [("property", 1.0)]

    # Water damage vs flood distinction — only resolve if clearly one-sided
    if "water_damage" in scores and "flood" in scores:
        internal = any(kw in desc_lower for kw in [
            "pipe", "plumbing", "dishwasher", "washing machine",
            "supply line", "water heater", "faucet", "toilet",
            "sump pump",
        ])
        external = any(kw in desc_lower for kw in [
            "rain", "river", "storm surge", "creek", "hurricane",
            "flash flood", "external", "floodwater", "rainstorm",
            "heavy rain", "seep",
        ])
        if internal and not external:
            del scores["flood"]
        elif external and not internal:
            del scores["water_damage"]
        # If both present or neither, keep both — ambiguous

    total = sum(scores.values())
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ranked_pcts = [(cat, score / total) for cat, score in ranked]

    best = ranked[0][0]
    confidence = scores[best] / total if total > 0 else 0.5

    return best, min(confidence, 0.95), ranked_pcts


class AgentTools:
    """LLM-callable tools for claim processing."""

    def __init__(self, claim: Claim):
        self.claim = claim
        self.state = ClaimProcessingState(claim={
            "claim_id": claim.claim_id,
            "category": claim.category,
            "description": claim.description,
            "policy_id": claim.policy_id,
            "region": claim.region,
            "amount": claim.amount,
        })

    def classify_claim(self, description: str) -> str:
        """Classify a claim description into a category."""
        self.state.steps_taken += 1
        category, confidence, ranked = _classify_description(description)
        self.state.classified = True
        self.state.classification_result = category

        # Check if top-2 categories are close (ambiguous)
        if len(ranked) >= 2:
            top_pct = ranked[0][1]
            second_pct = ranked[1][1]
            if top_pct - second_pct < 0.15:
                # Ambiguous result — show both
                top_cat, top_p = ranked[0]
                sec_cat, sec_p = ranked[1]
                return (
                    f"Top categories: {top_cat} ({top_p:.0%}), {sec_cat} ({sec_p:.0%}). "
                    f"Ambiguous — the description contains indicators for both. "
                    f"You must determine the correct category based on the root cause described."
                )

        subcategory = ""
        if category in ("water_damage", "flood", "fire"):
            subcategory = " (Property subcategory)"

        return f"Category: {category}{subcategory}. Confidence: {confidence:.0%}."

    def lookup_policy(self, policy_id: str) -> str:
        """Look up policy details by ID."""
        self.state.steps_taken += 1
        policy = get_policy(policy_id)
        if not policy:
            return f"ERROR: Policy '{policy_id}' not found in system."

        self.state.policy_looked_up = True
        return (
            f"Policy {policy.policy_id}: Type={policy.policy_type}, "
            f"Limit=${policy.coverage_limit:,.0f}, Deductible=${policy.deductible:,.0f}, "
            f"Status={policy.status}, Holder={policy.holder_name}"
        )

    def check_coverage(self, policy_type: str, claim_category: str) -> str:
        """Check if a policy type covers a claim category."""
        self.state.steps_taken += 1
        self.state.coverage_checked = True

        result = check_coverage_rules(policy_type, claim_category)

        if result["covered"]:
            note = f" Note: {result['notes']}" if result.get("notes") else ""
            return f"COVERED: {result['reason']}{note}"
        else:
            note = f" Note: {result['notes']}" if result.get("notes") else ""
            return f"NOT COVERED: {result['reason']}{note}"

    def check_fraud_indicators(self, claim_id: str) -> str:
        """Check for fraud indicators on a claim."""
        self.state.steps_taken += 1
        self.state.fraud_checked = True

        result = get_fraud_risk(claim_id)

        if result["risk_level"] == "unknown":
            return "ERROR: Claim not found."

        if result["risk_level"] == "low":
            return "FRAUD RISK: LOW. No indicators found."

        indicator_text = " ".join(
            f"({i+1}) {d}" for i, d in enumerate(result["details"])
        )
        return f"FRAUD RISK: {result['risk_level'].upper()}. Indicators: {indicator_text}"

    def check_prior_claims(self, policy_id: str) -> str:
        """Check prior claims history for a policy."""
        self.state.steps_taken += 1
        self.state.prior_claims_checked = True
        record = get_prior_claims(policy_id)
        if not record:
            return f"No prior claims history found for policy {policy_id}."
        lines = [f"Prior claims for {policy_id}: {record.claims_count} claim(s), {record.denial_count} denial(s)."]
        lines.append(record.notes)
        if record.fraud_flag:
            lines.append("WARNING: Prior fraud investigation on file. Recommend escalation to fraud specialist.")
        return " ".join(lines)

    def get_adjuster(self, claim_category: str, region: str, severity: str) -> str:
        """Find the best adjuster for a claim.

        Args:
            claim_category: The claim category (auto, property, etc.)
            region: Geographic region
            severity: "low" (<$10K), "medium" ($10K-$50K), "high" (>$50K)
        """
        self.state.steps_taken += 1
        self.state.adjuster_assigned = True

        severity_to_amount = {"low": 5_000, "medium": 30_000, "high": 75_000}
        amount = severity_to_amount.get(severity, 30_000)

        result = get_best_adjuster(claim_category, region, amount)
        self.state.assigned_adjuster_id = result["adjuster_id"]

        senior_note = ", Senior" if result["is_senior"] else ""
        return (
            f"Assigned: {result['name']} ({result['specialty'].title()} specialist, "
            f"{result['region']} region{senior_note}). "
            f"Reason: {result['reason']}."
        )

    def submit_decision(
        self,
        claim_id: str,
        decision: str,
        adjuster_id: str,
        payout_estimate: float,
        justification: str,
    ) -> str:
        """Submit a final claim decision for validation.

        Args:
            claim_id: The claim ID
            decision: "approved" | "denied" | "escalated"
            adjuster_id: Assigned adjuster ID
            payout_estimate: Estimated payout amount
            justification: Brief justification
        """
        self.state.steps_taken += 1
        self.state.decision_submitted = True

        result = validate_decision(
            claim_id, decision, adjuster_id, payout_estimate, justification,
            prior_claims_checked=self.state.prior_claims_checked,
        )

        if result["accepted"]:
            self.state.result = decision
            self.state.correct = True
            adjuster = ADJUSTERS.get(adjuster_id)
            adjuster_name = adjuster.name if adjuster else adjuster_id
            return (
                f"DECISION ACCEPTED: Claim #{claim_id} {decision}. "
                f"Payout: ${payout_estimate:,.2f}. Adjuster: {adjuster_name}."
            )
        else:
            self.state.correct = False
            self.state.rework_count += 1
            error_text = " ".join(result["errors"])
            hint_text = " ".join(result["hints"]) if result["hints"] else ""
            msg = f"DECISION REJECTED: {error_text}"
            if hint_text:
                msg += f" Hint: {hint_text}"
            msg += " Please review and resubmit."
            return msg


def get_tool_definitions() -> list[dict]:
    """Return OpenAI-format tool definitions for the 6 claim processing tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": "classify_claim",
                "description": "Classify a claim description into a category (auto, property, liability, health, water_damage, flood, fire).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "The claim description text to classify."
                        }
                    },
                    "required": ["description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "lookup_policy",
                "description": "Look up policy details by policy ID. Returns policy type, coverage limit, deductible, status, and holder name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "policy_id": {
                            "type": "string",
                            "description": "The policy ID (e.g., 'GLD-2001')."
                        }
                    },
                    "required": ["policy_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_coverage",
                "description": "Check if a policy type covers a specific claim category. Returns coverage status and any exclusions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "policy_type": {
                            "type": "string",
                            "description": "The policy type (e.g., 'Gold', 'Silver', 'Platinum', 'Bronze', 'Home Shield', 'Auto Plus')."
                        },
                        "claim_category": {
                            "type": "string",
                            "description": "The claim category (auto, property, liability, health, water_damage, flood, fire)."
                        }
                    },
                    "required": ["policy_type", "claim_category"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_fraud_indicators",
                "description": "Check for fraud indicators on a claim. Returns risk level and any fraud indicators found.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "claim_id": {
                            "type": "string",
                            "description": "The claim ID to check."
                        }
                    },
                    "required": ["claim_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_prior_claims",
                "description": "Check prior claims history for a policy. Returns any prior claims, denials, and fraud flags on file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "policy_id": {
                            "type": "string",
                            "description": "The policy ID to check prior claims for."
                        }
                    },
                    "required": ["policy_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_adjuster",
                "description": "Find the best adjuster for a claim based on category, region, and severity. Returns adjuster assignment with name, specialty, and region.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "claim_category": {
                            "type": "string",
                            "description": "The claim category (auto, property, liability, health, water_damage, flood, fire)."
                        },
                        "region": {
                            "type": "string",
                            "description": "Geographic region (northeast, southwest, southeast, west, midwest)."
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Severity based on amount: low (<$10K), medium ($10K-$50K), high (>$50K)."
                        }
                    },
                    "required": ["claim_category", "region", "severity"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "submit_decision",
                "description": "Submit a final claim decision for validation. The system will accept or reject based on coverage rules, adjuster assignment, and escalation thresholds.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "claim_id": {
                            "type": "string",
                            "description": "The claim ID."
                        },
                        "decision": {
                            "type": "string",
                            "enum": ["approved", "denied", "escalated"],
                            "description": "The claim decision."
                        },
                        "adjuster_id": {
                            "type": "string",
                            "description": "The assigned adjuster ID (e.g., 'ADJ-001')."
                        },
                        "payout_estimate": {
                            "type": "number",
                            "description": "Estimated payout amount (0 for denied claims)."
                        },
                        "justification": {
                            "type": "string",
                            "description": "Brief justification for the decision."
                        }
                    },
                    "required": ["claim_id", "decision", "adjuster_id", "payout_estimate", "justification"]
                }
            }
        },
    ]


def execute_tool(tools: AgentTools, tool_name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments."""
    method = getattr(tools, tool_name, None)
    if method is None:
        return f"ERROR: Unknown tool '{tool_name}'."
    try:
        return method(**arguments)
    except TypeError as e:
        return f"ERROR: Invalid arguments for {tool_name}: {e}"
