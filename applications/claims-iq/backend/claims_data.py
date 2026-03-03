"""Domain simulation engine for insurance claims triage.

Contains all policy types, adjusters, coverage rules, fraud indicators,
claim scenarios, and validation logic.
"""

import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Policy types and coverage matrix
# ---------------------------------------------------------------------------

COVERAGE_MATRIX: dict[str, dict[str, bool]] = {
    "Platinum": {
        "auto": True, "property": True, "liability": True, "health": True,
        "water_damage": True, "flood": True, "fire": True,
    },
    "Gold": {
        "auto": True, "property": True, "liability": True, "health": False,
        "water_damage": True, "flood": False, "fire": True,
    },
    "Silver": {
        "auto": True, "property": True, "liability": False, "health": False,
        "water_damage": True, "flood": False, "fire": False,
    },
    "Bronze": {
        "auto": True, "property": False, "liability": False, "health": False,
        "water_damage": False, "flood": False, "fire": False,
    },
    "Home Shield": {
        "auto": False, "property": True, "liability": True, "health": False,
        "water_damage": True, "flood": True, "fire": True,
    },
    "Auto Plus": {
        "auto": True, "property": False, "liability": True, "health": False,
        "water_damage": False, "flood": False, "fire": False,
    },
}

COVERAGE_EXCLUSION_REASONS: dict[str, str] = {
    "flood": "Flood damage requires a separate flood insurance rider.",
    "fire": "Fire coverage is only available on Platinum, Gold, and Home Shield policies.",
    "health": "Health coverage is only available on Platinum policies.",
    "liability": "Liability coverage requires Gold, Platinum, Home Shield, or Auto Plus.",
    "water_damage": "Water damage from internal plumbing is only covered on Silver+ or Home Shield.",
    "property": "Property coverage is not included in Bronze or Auto Plus.",
    "auto": "Auto coverage is not included in Home Shield.",
}

# ---------------------------------------------------------------------------
# Policies (lookup by ID)
# ---------------------------------------------------------------------------

@dataclass
class Policy:
    policy_id: str
    policy_type: str
    holder_name: str
    coverage_limit: float
    deductible: float
    start_date: str
    status: str  # "active" | "expired" | "suspended"

POLICIES: dict[str, Policy] = {
    "PLT-1001": Policy("PLT-1001", "Platinum", "Margaret Chen", 500_000, 500, "2024-01-15", "active"),
    "GLD-2001": Policy("GLD-2001", "Gold", "Robert Martinez", 100_000, 1_000, "2024-03-01", "active"),
    "GLD-2002": Policy("GLD-2002", "Gold", "Susan Park", 75_000, 1_000, "2023-11-15", "active"),
    "SLV-3001": Policy("SLV-3001", "Silver", "James Thompson", 50_000, 2_000, "2024-06-01", "active"),
    "SLV-3002": Policy("SLV-3002", "Silver", "Karen White", 50_000, 2_000, "2024-02-20", "active"),
    "BRZ-4001": Policy("BRZ-4001", "Bronze", "David Lee", 25_000, 5_000, "2024-04-10", "active"),
    "BRZ-4002": Policy("BRZ-4002", "Bronze", "Amy Rodriguez", 25_000, 5_000, "2023-09-01", "active"),
    "HSH-5001": Policy("HSH-5001", "Home Shield", "William Foster", 200_000, 1_500, "2024-01-01", "active"),
    "HSH-5002": Policy("HSH-5002", "Home Shield", "Linda Chang", 150_000, 1_500, "2024-05-15", "active"),
    "APL-6001": Policy("APL-6001", "Auto Plus", "Thomas Brown", 75_000, 2_000, "2024-07-01", "active"),
    "GLD-2003": Policy("GLD-2003", "Gold", "Patricia Nguyen", 100_000, 1_000, "2024-08-01", "active"),
    "PLT-1002": Policy("PLT-1002", "Platinum", "Richard Kim", 500_000, 500, "2024-02-01", "active"),
}

# ---------------------------------------------------------------------------
# Adjusters
# ---------------------------------------------------------------------------

@dataclass
class Adjuster:
    adjuster_id: str
    name: str
    specialty: str  # "property" | "auto" | "liability" | "health" | "multi"
    region: str  # "northeast" | "southwest" | "southeast" | "west" | "midwest" | "all"
    is_senior: bool
    available: bool = True

# ---------------------------------------------------------------------------
# Prior claims history
# ---------------------------------------------------------------------------

@dataclass
class PriorClaimRecord:
    claims_count: int
    denial_count: int
    fraud_flag: bool
    notes: str

PRIOR_CLAIMS: dict[str, PriorClaimRecord] = {
    "GLD-2003": PriorClaimRecord(3, 1, True, "Previous claim for roof damage denied due to pre-existing condition. Investigated for inflated valuations."),
    "APL-6001": PriorClaimRecord(2, 1, True, "Prior auto claim denied for inconsistent accident report. Flagged for possible staged collision."),
    "HSH-5001": PriorClaimRecord(4, 2, True, "Multiple property claims in short period. Two denied for insufficient evidence. Pattern consistent with fraud ring activity."),
    "PLT-1002": PriorClaimRecord(5, 0, False, "Frequent claimant but all claims verified legitimate. High-value property in storm-prone area."),
    "BRZ-4002": PriorClaimRecord(1, 0, False, "Single prior auto claim, resolved normally."),
}


def get_prior_claims(policy_id: str) -> PriorClaimRecord | None:
    return PRIOR_CLAIMS.get(policy_id)


ADJUSTERS: dict[str, Adjuster] = {
    "ADJ-001": Adjuster("ADJ-001", "Sarah Chen", "property", "northeast", True),
    "ADJ-002": Adjuster("ADJ-002", "Mike Torres", "auto", "southwest", True),
    "ADJ-003": Adjuster("ADJ-003", "James Wilson", "auto", "northeast", False),
    "ADJ-004": Adjuster("ADJ-004", "Priya Patel", "liability", "southeast", True),
    "ADJ-005": Adjuster("ADJ-005", "David Kim", "property", "west", False),
    "ADJ-006": Adjuster("ADJ-006", "Lisa Johnson", "health", "midwest", True),
    "ADJ-007": Adjuster("ADJ-007", "Carlos Rivera", "multi", "all", True),
    "ADJ-008": Adjuster("ADJ-008", "Emma Zhang", "property", "west", False),
}

# Specialty → category mapping (which specialties handle which claim categories)
SPECIALTY_CATEGORY_MAP: dict[str, list[str]] = {
    "property": ["property", "water_damage", "flood", "fire"],
    "auto": ["auto"],
    "liability": ["liability"],
    "health": ["health"],
    "multi": ["auto", "property", "liability", "health", "water_damage", "flood", "fire"],
}

# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------

SENIOR_ADJUSTER_THRESHOLD = 50_000
MANAGER_REVIEW_THRESHOLD = 100_000

# ---------------------------------------------------------------------------
# Fraud indicators
# ---------------------------------------------------------------------------

FRAUD_INDICATORS_DESCRIPTIONS = {
    "multiple_claims_address": "Multiple claims at same address within 6 months",
    "near_policy_limit": "Claim amount is within 5% of policy limit",
    "incident_on_boundary": "Incident date matches policy start or end date",
    "total_loss_minor": 'Description mentions "total loss" for minor incidents',
}

# ---------------------------------------------------------------------------
# Claim scenarios
# ---------------------------------------------------------------------------

@dataclass
class ClaimScenario:
    """A pre-built claim template with known correct outcomes."""
    scenario_id: str
    category: str  # auto, property, liability, health, water_damage, flood, fire
    description_template: str
    policy_id: str
    region: str
    amount_range: tuple[float, float]
    correct_decision: str  # "approved" | "denied" | "escalated"
    correct_adjuster_id: str
    fraud_indicators: list[str] = field(default_factory=list)
    has_prior_fraud_flag: bool = False
    notes: str = ""

SCENARIOS: list[ClaimScenario] = [
    # --- Water damage (covered by Gold) ---
    ClaimScenario(
        "SC-001", "water_damage",
        "Burst pipe in kitchen caused flooding. Water damage to hardwood floors and lower cabinets.",
        "GLD-2001", "northeast", (8_000, 15_000),
        "approved", "ADJ-001",
        notes="Water damage from internal plumbing — covered by Gold.",
    ),
    ClaimScenario(
        "SC-002", "water_damage",
        "Dishwasher malfunction leaked water overnight. Damage to kitchen floor tiles and subfloor.",
        "SLV-3001", "west", (5_000, 12_000),
        "approved", "ADJ-005",
        notes="Internal water damage — covered by Silver.",
    ),
    ClaimScenario(
        "SC-003", "water_damage",
        "Bathroom pipe burst during winter freeze. Water damage to bathroom and hallway.",
        "GLD-2002", "northeast", (10_000, 20_000),
        "approved", "ADJ-001",
        notes="Internal plumbing failure — water damage, not flood.",
    ),
    # --- Flood (NOT covered by Gold) ---
    ClaimScenario(
        "SC-004", "flood",
        "Basement flooding from heavy rain. Standing water caused extensive damage to finished basement.",
        "GLD-2001", "northeast", (20_000, 40_000),
        "denied", "ADJ-001",
        notes="Flood from external source — NOT covered by Gold. Key distinction from water damage.",
    ),
    ClaimScenario(
        "SC-005", "flood",
        "River overflow after hurricane damaged ground floor. Muddy water ruined carpets and drywall.",
        "GLD-2002", "northeast", (30_000, 50_000),
        "denied", "ADJ-001",
        notes="Flood damage — NOT covered by Gold.",
    ),
    ClaimScenario(
        "SC-006", "flood",
        "Storm surge flooded coastal property. Extensive water damage to first floor and foundation.",
        "HSH-5001", "southeast", (40_000, 80_000),
        "approved", "ADJ-004",
        notes="Flood damage — covered by Home Shield.",
    ),
    # --- Auto ---
    ClaimScenario(
        "SC-007", "auto",
        "Rear-end collision at intersection. Bumper and trunk damage to policyholder's vehicle.",
        "GLD-2001", "southwest", (3_000, 8_000),
        "approved", "ADJ-002",
    ),
    ClaimScenario(
        "SC-008", "auto",
        "Parking lot hit-and-run. Driver's side door dented and paint scratched.",
        "BRZ-4001", "northeast", (1_500, 4_000),
        "approved", "ADJ-003",
    ),
    ClaimScenario(
        "SC-009", "auto",
        "Multi-vehicle highway accident. Significant front-end damage, airbags deployed.",
        "APL-6001", "southwest", (15_000, 35_000),
        "approved", "ADJ-002",
    ),
    ClaimScenario(
        "SC-010", "auto",
        "Vehicle stolen from parking garage. Total loss claimed.",
        "BRZ-4001", "northeast", (20_000, 24_000),
        "approved", "ADJ-003",
        fraud_indicators=["near_policy_limit"],
        notes="Amount suspiciously close to policy limit.",
    ),
    # --- Property ---
    ClaimScenario(
        "SC-011", "property",
        "Tree fell on roof during windstorm. Significant structural damage to roof and attic.",
        "GLD-2003", "northeast", (15_000, 30_000),
        "escalated", "ADJ-007",
        has_prior_fraud_flag=True,
        notes="Claimant has prior fraud flags — must escalate to fraud specialist.",
    ),
    ClaimScenario(
        "SC-012", "property",
        "Vandalism at property. Broken windows and graffiti on exterior walls.",
        "HSH-5002", "west", (2_000, 6_000),
        "approved", "ADJ-005",
    ),
    ClaimScenario(
        "SC-013", "property",
        "Roof collapse after heavy snow accumulation. Damage to attic and second floor.",
        "BRZ-4002", "northeast", (25_000, 45_000),
        "denied", "ADJ-001",
        notes="Property claims NOT covered by Bronze.",
    ),
    # --- Fire ---
    ClaimScenario(
        "SC-014", "fire",
        "Kitchen fire from grease. Smoke and fire damage to kitchen, dining room, and hallway.",
        "PLT-1001", "northeast", (30_000, 60_000),
        "approved", "ADJ-001",
    ),
    ClaimScenario(
        "SC-015", "fire",
        "Electrical fire in garage. Extensive damage to garage and two vehicles inside.",
        "HSH-5001", "west", (50_000, 120_000),
        "approved", "ADJ-008",
        notes="High amount — may require senior adjuster / manager review depending on value.",
    ),
    ClaimScenario(
        "SC-016", "fire",
        "Small kitchen fire. Minor smoke damage to cabinets and ceiling.",
        "SLV-3002", "northeast", (3_000, 8_000),
        "denied", "ADJ-001",
        notes="Fire NOT covered by Silver.",
    ),
    # --- Liability ---
    ClaimScenario(
        "SC-017", "liability",
        "Guest slipped on wet floor at policyholder's home. Broken wrist requiring surgery.",
        "PLT-1002", "southeast", (25_000, 50_000),
        "approved", "ADJ-004",
    ),
    ClaimScenario(
        "SC-018", "liability",
        "Dog bite incident at policyholder's property. Neighbor's child required stitches.",
        "HSH-5001", "southeast", (10_000, 25_000),
        "approved", "ADJ-004",
    ),
    ClaimScenario(
        "SC-019", "liability",
        "Visitor tripped on broken sidewalk. Medical bills and lost wages claimed.",
        "SLV-3001", "southeast", (15_000, 30_000),
        "denied", "ADJ-004",
        notes="Liability NOT covered by Silver.",
    ),
    # --- Health ---
    ClaimScenario(
        "SC-020", "health",
        "Emergency room visit after workplace injury. Surgery and 3-day hospital stay.",
        "PLT-1001", "midwest", (40_000, 80_000),
        "approved", "ADJ-006",
    ),
    ClaimScenario(
        "SC-021", "health",
        "Outpatient surgery for torn ligament. Physical therapy sessions included.",
        "GLD-2001", "midwest", (15_000, 30_000),
        "denied", "ADJ-006",
        notes="Health NOT covered by Gold.",
    ),
    # --- Fraud scenarios ---
    ClaimScenario(
        "SC-022", "property",
        "Total loss of contents after reported burglary. All electronics and jewelry claimed stolen.",
        "GLD-2003", "northeast", (90_000, 99_000),
        "escalated", "ADJ-007",
        fraud_indicators=["near_policy_limit", "total_loss_minor"],
        notes="Fraud red flags: amount near limit, total loss claim.",
    ),
    ClaimScenario(
        "SC-023", "auto",
        "Vehicle total loss in single-car accident. No witnesses, occurred late at night.",
        "APL-6001", "southwest", (70_000, 74_000),
        "escalated", "ADJ-007",
        fraud_indicators=["near_policy_limit"],
        notes="Fraud indicator: amount near policy limit.",
    ),
    ClaimScenario(
        "SC-024", "water_damage",
        "Extensive water damage from burst pipes. Multiple claims filed at same address.",
        "PLT-1002", "northeast", (80_000, 150_000),
        "escalated", "ADJ-007",
        fraud_indicators=["multiple_claims_address"],
        notes="Fraud: multiple claims at same address. High amount needs senior + manager review.",
    ),
    # --- High amount escalation ---
    ClaimScenario(
        "SC-025", "property",
        "Major storm damage to entire roof and exterior. Temporary relocation needed.",
        "PLT-1001", "northeast", (120_000, 200_000),
        "approved", "ADJ-001",
        notes="Over $100K — requires senior adjuster AND manager review.",
    ),
    ClaimScenario(
        "SC-026", "auto",
        "Commercial vehicle accident with cargo loss. Multiple vehicles involved.",
        "PLT-1002", "southwest", (55_000, 90_000),
        "approved", "ADJ-002",
        notes="Over $50K — requires senior adjuster.",
    ),
    # --- Auto Plus edge case ---
    ClaimScenario(
        "SC-027", "property",
        "Home break-in with property stolen. Windows broken and door damaged.",
        "APL-6001", "northeast", (8_000, 15_000),
        "denied", "ADJ-007",
        has_prior_fraud_flag=True,
        notes="Property NOT covered by Auto Plus. Claimant has prior fraud flags.",
    ),
    # --- Tricky water vs flood ---
    ClaimScenario(
        "SC-028", "water_damage",
        "Washing machine supply line ruptured. Water leaked through floor to basement.",
        "GLD-2002", "west", (12_000, 25_000),
        "approved", "ADJ-005",
        notes="Internal plumbing — water damage, not flood. Covered by Gold.",
    ),
    ClaimScenario(
        "SC-029", "flood",
        "Flash flood from creek overflow damaged crawl space and foundation.",
        "GLD-2001", "southwest", (25_000, 45_000),
        "denied", "ADJ-002",
        notes="External water source = flood. NOT covered by Gold.",
    ),
    ClaimScenario(
        "SC-030", "fire",
        "Wildfire reached property perimeter. Fence, shed, and exterior wall damaged.",
        "PLT-1002", "west", (60_000, 110_000),
        "approved", "ADJ-008",
        notes="Fire covered by Platinum. High amount needs senior adjuster.",
    ),
    # --- Ambiguous / trap scenarios ---
    ClaimScenario(
        "SC-031", "water_damage",
        "Sump pump failed during heavy rainstorm, water entered through foundation cracks. "
        "Extensive damage to basement walls and flooring.",
        "GLD-2001", "northeast", (12_000, 25_000),
        "approved", "ADJ-001",
        notes="Trap: sounds like flood but sump pump failure is internal source = water_damage. "
              "Gold covers water_damage. Agent may misclassify as flood and wrongly deny.",
    ),
    ClaimScenario(
        "SC-032", "flood",
        "Heavy rain caused water to seep through basement walls and damaged the finished "
        "basement floor. No plumbing involvement.",
        "GLD-2002", "northeast", (15_000, 30_000),
        "denied", "ADJ-001",
        notes="External water source (rain seepage) = flood. Gold does NOT cover flood. "
              "Agent may confuse with water_damage and wrongly approve.",
    ),
    ClaimScenario(
        "SC-033", "auto",
        "Minor fender bender in parking lot. Small dent on rear bumper, paint scratched.",
        "APL-6001", "southwest", (1_500, 4_000),
        "escalated", "ADJ-007",
        has_prior_fraud_flag=True,
        notes="Clean current claim but claimant has prior fraud flag. "
              "Must check prior claims and escalate to fraud specialist.",
    ),
    ClaimScenario(
        "SC-034", "auto",
        "Highway accident with significant front-end damage. Airbags deployed, vehicle towed.",
        "GLD-2001", "northeast", (55_000, 70_000),
        "approved", "ADJ-002",
        notes="High amount requires senior auto adjuster. Default northeast auto adjuster "
              "ADJ-003 is non-senior — must find senior auto (ADJ-002).",
    ),
    ClaimScenario(
        "SC-035", "liability",
        "Guest slipped on icy steps at policyholder's home, required emergency surgery. "
        "Medical bills and rehabilitation costs claimed.",
        "PLT-1001", "southeast", (30_000, 60_000),
        "approved", "ADJ-004",
        notes="Liability claim despite medical keywords. Should be classified as liability "
              "(not health), covered by Platinum. Southeast region → ADJ-004.",
    ),
]

# ---------------------------------------------------------------------------
# Active claims state
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    claim_id: str
    scenario_id: str
    category: str
    description: str
    policy_id: str
    region: str
    amount: float
    claimant_name: str
    incident_date: str
    fraud_indicators: list[str]
    correct_decision: str
    correct_adjuster_id: str
    has_prior_fraud_flag: bool = False

# In-memory store of generated claims
_active_claims: dict[str, Claim] = {}

# Claimant name pool
_CLAIMANT_NAMES = [
    "John Smith", "Maria Garcia", "Alex Johnson", "Wei Zhang", "Sarah O'Brien",
    "Mohammed Ali", "Emily Davis", "Carlos Mendez", "Jennifer Lee", "Michael Brown",
    "Anna Petrov", "Ryan Nakamura", "Fatima Hassan", "Daniel Kim", "Laura Wilson",
    "Tom Anderson", "Rachel Green", "Chris Martin", "Nina Patel", "Jake Turner",
]

_INCIDENT_DATES = [
    "2024-10-15", "2024-10-22", "2024-11-03", "2024-11-18", "2024-12-01",
    "2024-12-10", "2025-01-05", "2025-01-14", "2025-01-28", "2025-02-02",
]


def generate_claim(scenario_id: str | None = None) -> Claim:
    """Generate a claim from a random or specific scenario."""
    if scenario_id:
        scenario = next((s for s in SCENARIOS if s.scenario_id == scenario_id), None)
        if not scenario:
            raise ValueError(f"Unknown scenario: {scenario_id}")
    else:
        scenario = random.choice(SCENARIOS)

    amount = round(random.uniform(*scenario.amount_range), 2)
    claim_id = f"CLM-{random.randint(1000, 9999)}"

    # Determine correct adjuster considering escalation
    correct_adjuster_id = scenario.correct_adjuster_id
    if scenario.fraud_indicators or scenario.has_prior_fraud_flag:
        correct_adjuster_id = "ADJ-007"  # Carlos Rivera for fraud
    elif amount > SENIOR_ADJUSTER_THRESHOLD:
        # Need a senior adjuster for the category/region
        adjuster = ADJUSTERS[scenario.correct_adjuster_id]
        if not adjuster.is_senior:
            # Find a senior for same specialty
            correct_adjuster_id = _find_senior_adjuster(scenario.category, scenario.region)

    correct_decision = scenario.correct_decision
    # If fraud indicators, always escalate
    if scenario.fraud_indicators:
        correct_decision = "escalated"
    # If prior fraud flag and claim would be approved, escalate instead
    elif scenario.has_prior_fraud_flag and correct_decision != "denied":
        correct_decision = "escalated"

    claim = Claim(
        claim_id=claim_id,
        scenario_id=scenario.scenario_id,
        category=scenario.category,
        description=scenario.description_template,
        policy_id=scenario.policy_id,
        region=scenario.region,
        amount=amount,
        claimant_name=random.choice(_CLAIMANT_NAMES),
        incident_date=random.choice(_INCIDENT_DATES),
        fraud_indicators=scenario.fraud_indicators.copy(),
        correct_decision=correct_decision,
        correct_adjuster_id=correct_adjuster_id,
        has_prior_fraud_flag=scenario.has_prior_fraud_flag,
    )
    _active_claims[claim.claim_id] = claim
    return claim


def _find_senior_adjuster(category: str, region: str) -> str:
    """Find the best senior adjuster for a category and region."""
    # First try exact specialty + region match
    for adj_id, adj in ADJUSTERS.items():
        if adj.is_senior and category in SPECIALTY_CATEGORY_MAP.get(adj.specialty, []) and adj.region in (region, "all"):
            return adj_id
    # Then try just specialty
    for adj_id, adj in ADJUSTERS.items():
        if adj.is_senior and category in SPECIALTY_CATEGORY_MAP.get(adj.specialty, []):
            return adj_id
    # Fallback to Carlos Rivera (multi/senior)
    return "ADJ-007"


def get_claim(claim_id: str) -> Claim | None:
    return _active_claims.get(claim_id)


def get_policy(policy_id: str) -> Policy | None:
    return POLICIES.get(policy_id)


def check_coverage_rules(policy_type: str, category: str) -> dict:
    """Check whether a policy type covers a claim category.

    Returns dict with: covered (bool), reason (str), notes (str | None)
    """
    matrix = COVERAGE_MATRIX.get(policy_type)
    if not matrix:
        return {"covered": False, "reason": f"Unknown policy type: {policy_type}", "notes": None}

    covered = matrix.get(category, False)
    if covered:
        notes = None
        if category == "water_damage":
            notes = "Water damage from internal plumbing is distinct from flood damage caused by external water sources."
        return {"covered": True, "reason": f"{policy_type} policies cover {category} claims.", "notes": notes}
    else:
        reason = COVERAGE_EXCLUSION_REASONS.get(category, f"{category} is not covered by {policy_type}.")
        notes = None
        if category == "flood" and policy_type == "Gold":
            notes = "Gold covers water_damage but NOT flood. This is a common distinction."
        elif category == "water_damage" and not covered:
            notes = "Water damage from internal plumbing requires Silver, Gold, Platinum, or Home Shield."
        return {"covered": False, "reason": reason, "notes": notes}


def get_fraud_risk(claim_id: str) -> dict:
    """Get fraud risk assessment for a claim.

    Returns dict with: risk_level (str), indicators (list[str]), details (list[str])
    """
    claim = _active_claims.get(claim_id)
    if not claim:
        return {"risk_level": "unknown", "indicators": [], "details": ["Claim not found."]}

    indicators = claim.fraud_indicators
    details = [FRAUD_INDICATORS_DESCRIPTIONS[ind] for ind in indicators if ind in FRAUD_INDICATORS_DESCRIPTIONS]

    # Check amount vs policy limit
    policy = POLICIES.get(claim.policy_id)
    if policy and claim.amount >= policy.coverage_limit * 0.95:
        if "near_policy_limit" not in indicators:
            indicators = indicators + ["near_policy_limit"]
            details.append(f"Claim amount (${claim.amount:,.2f}) is {claim.amount/policy.coverage_limit*100:.0f}% of policy limit (${policy.coverage_limit:,.2f}).")

    if len(indicators) >= 2:
        risk_level = "high"
    elif len(indicators) == 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {"risk_level": risk_level, "indicators": indicators, "details": details}


def get_best_adjuster(category: str, region: str, amount: float) -> dict:
    """Find the best adjuster for a claim category, region, and amount.

    Returns dict with: adjuster_id, name, specialty, region, is_senior, reason
    """
    needs_senior = amount > SENIOR_ADJUSTER_THRESHOLD
    candidates = []

    for adj_id, adj in ADJUSTERS.items():
        if adj.specialty == "multi":
            continue  # Don't auto-assign fraud specialist
        if category in SPECIALTY_CATEGORY_MAP.get(adj.specialty, []):
            if adj.region in (region, "all"):
                candidates.append(adj)

    if not candidates:
        # Broaden to any region
        for adj_id, adj in ADJUSTERS.items():
            if adj.specialty == "multi":
                continue
            if category in SPECIALTY_CATEGORY_MAP.get(adj.specialty, []):
                candidates.append(adj)

    if needs_senior:
        senior_candidates = [c for c in candidates if c.is_senior]
        if senior_candidates:
            candidates = senior_candidates

    if not candidates:
        adj = ADJUSTERS["ADJ-007"]
        return {
            "adjuster_id": adj.adjuster_id,
            "name": adj.name,
            "specialty": adj.specialty,
            "region": adj.region,
            "is_senior": adj.is_senior,
            "reason": "No specialist available; assigned to multi-specialist.",
        }

    best = candidates[0]
    reason = f"{best.specialty.title()} specialist"
    if best.region == region:
        reason += f", {region} region"
    if best.is_senior:
        reason += ", Senior"

    return {
        "adjuster_id": best.adjuster_id,
        "name": best.name,
        "specialty": best.specialty,
        "region": best.region,
        "is_senior": best.is_senior,
        "reason": reason,
    }


def compute_optimal_steps(claim: Claim) -> int:
    """Compute minimum tool calls needed for a claim.

    Optimal workflow:
    1. classify_claim
    2. lookup_policy
    3. check_coverage
    4. check_fraud_indicators
    5. check_prior_claims
    6. get_adjuster
    7. submit_decision
    = 7 steps
    """
    return 7


def validate_decision(
    claim_id: str,
    decision: str,
    adjuster_id: str,
    payout_estimate: float,
    justification: str = "",
    prior_claims_checked: bool = False,
) -> dict:
    """Validate a claim decision against ground truth.

    Returns dict with: accepted (bool), errors (list[str]), hints (list[str])
    """
    claim = _active_claims.get(claim_id)
    if not claim:
        return {"accepted": False, "errors": ["Claim not found."], "hints": []}

    errors = []
    hints = []

    policy = POLICIES.get(claim.policy_id)
    if not policy:
        errors.append(f"Policy {claim.policy_id} not found.")
        return {"accepted": False, "errors": errors, "hints": hints}

    # Check coverage
    coverage = check_coverage_rules(policy.policy_type, claim.category)
    is_covered = coverage["covered"]

    # Check fraud
    fraud = get_fraud_risk(claim_id)
    has_high_fraud = fraud["risk_level"] in ("high", "medium") and len(fraud["indicators"]) >= 1

    # Check prior fraud flag
    if claim.has_prior_fraud_flag and not prior_claims_checked:
        errors.append("Prior claims history has not been reviewed. Claimant has documented history requiring review.")
        hints.append("Use check_prior_claims to review the claimant's prior claims history before submitting a decision.")
    if claim.has_prior_fraud_flag and decision != "escalated" and adjuster_id != "ADJ-007":
        errors.append("Claimant has prior fraud flags on file. Must be escalated to fraud specialist (ADJ-007).")
        hints.append("Claimants with prior fraud flags must always be escalated to Carlos Rivera (ADJ-007) regardless of current claim details.")

    # Validate decision
    if has_high_fraud and len(fraud["indicators"]) >= 2:
        # High fraud — must escalate
        if decision != "escalated":
            errors.append("High fraud risk detected. This claim should be escalated to the fraud specialist.")
            hints.append("Claims with multiple fraud indicators must be escalated to Carlos Rivera (fraud specialist).")
        if adjuster_id != "ADJ-007":
            errors.append(f"Fraud cases must be routed to Carlos Rivera (ADJ-007), not {adjuster_id}.")
            hints.append("Carlos Rivera handles all fraud investigations regardless of claim type or region.")
    elif not is_covered:
        # Not covered — must deny
        if decision != "denied":
            errors.append(f"Claim category '{claim.category}' is NOT covered by {policy.policy_type} policies.")
            hints.append(coverage.get("notes") or coverage["reason"])
        if payout_estimate > 0:
            errors.append("Payout should be $0 for denied claims.")
    else:
        # Covered — should approve (or escalate for high amounts)
        needs_manager = claim.amount > MANAGER_REVIEW_THRESHOLD
        if needs_manager and decision not in ("approved", "escalated"):
            errors.append(f"Claim amount ${claim.amount:,.2f} exceeds $100K. Requires approval with manager review flag or escalation.")

        if decision == "denied":
            errors.append(f"'{claim.category}' IS covered by {policy.policy_type}. This claim should be approved, not denied.")

        # Validate adjuster
        if adjuster_id:
            adjuster = ADJUSTERS.get(adjuster_id)
            if adjuster:
                # Check specialty match
                valid_categories = SPECIALTY_CATEGORY_MAP.get(adjuster.specialty, [])
                if claim.category not in valid_categories and adjuster.specialty != "multi":
                    correct = ADJUSTERS.get(claim.correct_adjuster_id)
                    errors.append(f"Incorrect adjuster specialty. {adjuster.name} handles {adjuster.specialty}, not {claim.category}.")
                    if correct:
                        hints.append(f"{claim.category.replace('_', ' ').title()} claims in {claim.region} should go to {correct.name}.")

                # Check seniority for high amounts
                if claim.amount > SENIOR_ADJUSTER_THRESHOLD and not adjuster.is_senior:
                    errors.append(f"Claims over $50K require a senior adjuster. {adjuster.name} is not senior.")
                    hints.append("Check the adjuster roster for senior adjusters in the same specialty.")
            else:
                errors.append(f"Unknown adjuster ID: {adjuster_id}")

        # Validate payout
        if payout_estimate > policy.coverage_limit:
            errors.append(f"Payout ${payout_estimate:,.2f} exceeds policy limit of ${policy.coverage_limit:,.2f}.")
        if payout_estimate > claim.amount * 1.1:
            errors.append(f"Payout ${payout_estimate:,.2f} significantly exceeds claim amount ${claim.amount:,.2f}.")

    accepted = len(errors) == 0
    return {"accepted": accepted, "errors": errors, "hints": hints}


def claim_to_dict(claim: Claim) -> dict:
    """Convert a Claim to a JSON-serializable dict."""
    return {
        "claimId": claim.claim_id,
        "scenarioId": claim.scenario_id,
        "category": claim.category,
        "description": claim.description,
        "policyId": claim.policy_id,
        "region": claim.region,
        "amount": claim.amount,
        "claimantName": claim.claimant_name,
        "incidentDate": claim.incident_date,
    }


def list_scenarios() -> list[dict]:
    """List all available scenarios (without correct answers)."""
    return [
        {
            "scenarioId": s.scenario_id,
            "category": s.category,
            "policyId": s.policy_id,
            "region": s.region,
            "amountRange": list(s.amount_range),
            "description": s.description_template[:80] + "...",
        }
        for s in SCENARIOS
    ]
