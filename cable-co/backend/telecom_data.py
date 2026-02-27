"""CableConnect — Domain data: accounts, plans, billing, outages, scenarios, business rules."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    plan_id: str
    name: str
    monthly_rate: float
    internet_mbps: int
    cable_channels: int


PLANS = {
    "basic": Plan("basic", "Basic", 49.99, 100, 60),
    "standard": Plan("standard", "Standard", 79.99, 300, 150),
    "premium": Plan("premium", "Premium", 109.99, 500, 250),
    "ultra": Plan("ultra", "Ultra", 149.99, 1000, 400),
}


# ---------------------------------------------------------------------------
# Rate codes (per plan)
# ---------------------------------------------------------------------------

RATE_CODES = {
    "basic": {"rate_code": "RC-BAS-50", "features": ["INET-100", "TV-60"]},
    "standard": {"rate_code": "RC-STD-80", "features": ["INET-300", "TV-150", "DVR-STD"]},
    "premium": {"rate_code": "RC-PRM-110", "features": ["INET-500", "TV-250", "DVR-HD", "HBO-INC"]},
    "ultra": {"rate_code": "RC-ULT-150", "features": ["INET-1G", "TV-400", "DVR-4K", "HBO-INC", "SHOWTIME-INC"]},
}


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

@dataclass
class Equipment:
    equipment_id: str
    equipment_type: str
    model: str
    tier: str
    serial: str


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@dataclass
class Account:
    account_id: str
    name: str
    plan_id: str
    tenure_months: int
    contract_months: int  # 0 = no contract
    balance: float
    area: str
    node_id: str
    address: str
    equipment: list[Equipment] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _make_accounts() -> dict[str, Account]:
    return {
        "ACC-1001": Account(
            account_id="ACC-1001",
            name="Sarah Johnson",
            plan_id="standard",
            tenure_months=36,
            contract_months=0,
            balance=0.0,
            area="northside",
            node_id="NODE-NS-04",
            address="142 Maple Ave, Northside",
            equipment=[
                Equipment("EQ-10011", "modem", "SB8200", "standard", "SN-88201A"),
                Equipment("EQ-10012", "cable_box", "X1-STD", "standard", "SN-X1-3382"),
            ],
            flags=[],
            notes=["Loyal customer, always pays on time"],
        ),
        "ACC-1002": Account(
            account_id="ACC-1002",
            name="Mike Chen",
            plan_id="premium",
            tenure_months=18,
            contract_months=24,
            balance=0.0,
            area="downtown",
            node_id="NODE-DT-02",
            address="890 Market St #4B, Downtown",
            equipment=[
                Equipment("EQ-10021", "modem", "SB8200", "premium", "SN-88202B"),
                Equipment("EQ-10022", "cable_box", "X1-HD", "premium", "SN-X1-4410"),
            ],
            flags=[],
            notes=["Signed 24-month contract at signup"],
        ),
        "ACC-1003": Account(
            account_id="ACC-1003",
            name="Lisa Park",
            plan_id="standard",
            tenure_months=10,
            contract_months=0,
            balance=0.0,
            area="westend",
            node_id="NODE-WE-07",
            address="55 Oak Ln, West End",
            equipment=[
                Equipment("EQ-10031", "modem", "SB6190", "standard", "SN-61903C"),
                Equipment("EQ-10032", "cable_box", "X1-STD", "standard", "SN-X1-5501"),
            ],
            flags=[],
            notes=[],
        ),
        "ACC-1004": Account(
            account_id="ACC-1004",
            name="James Wilson",
            plan_id="premium",
            tenure_months=12,
            contract_months=0,
            balance=0.0,
            area="southend",
            node_id="NODE-SE-03",
            address="320 Pine St, South End",
            equipment=[
                Equipment("EQ-10041", "modem", "SB8200", "premium", "SN-88204D"),
                Equipment("EQ-10042", "cable_box", "X1-HD", "premium", "SN-X1-6622"),
            ],
            flags=[],
            notes=["Called last month about channel lineup question"],
        ),
        "ACC-1005": Account(
            account_id="ACC-1005",
            name="Maria Garcia",
            plan_id="basic",
            tenure_months=8,
            contract_months=12,
            balance=0.0,
            area="eastside",
            node_id="NODE-ES-01",
            address="77 Elm Dr, Eastside",
            equipment=[
                Equipment("EQ-10051", "modem", "SB6190", "basic", "SN-61905E"),
                Equipment("EQ-10052", "cable_box", "X1-BAS", "basic", "SN-X1-7701"),
            ],
            flags=[],
            notes=["12-month contract, ETF $120"],
        ),
        "ACC-1006": Account(
            account_id="ACC-1006",
            name="David Brown",
            plan_id="standard",
            tenure_months=6,
            contract_months=0,
            balance=0.0,
            area="northside",
            node_id="NODE-NS-02",
            address="210 Birch Rd, Northside",
            equipment=[
                Equipment("EQ-10061", "modem", "SB6190", "standard", "SN-61906F"),
                Equipment("EQ-10062", "cable_box", "X1-STD", "standard", "SN-X1-8833"),
            ],
            flags=[],
            notes=["New customer, signed up 6 months ago"],
        ),
        "ACC-1007": Account(
            account_id="ACC-1007",
            name="Amy Rodriguez",
            plan_id="ultra",
            tenure_months=30,
            contract_months=0,
            balance=0.0,
            area="downtown",
            node_id="NODE-DT-02",
            address="1200 Central Blvd #12A, Downtown",
            equipment=[
                Equipment("EQ-10071", "modem", "SB8200", "ultra", "SN-88207G"),
                Equipment("EQ-10072", "cable_box", "X1-4K", "ultra", "SN-X1-9944"),
                Equipment("EQ-10073", "cable_box", "X1-4K", "ultra", "SN-X1-9945"),
            ],
            flags=[],
            notes=["VIP customer, 30 months tenure, Ultra plan"],
        ),
        "ACC-1008": Account(
            account_id="ACC-1008",
            name="Tom Nakamura",
            plan_id="premium",
            tenure_months=24,
            contract_months=0,
            balance=0.0,
            area="westend",
            node_id="NODE-WE-07",
            address="88 Cedar Way, West End",
            equipment=[
                Equipment("EQ-10081", "modem", "SB8200", "premium", "SN-88208H"),
                Equipment("EQ-10082", "cable_box", "X1-HD", "premium", "SN-X1-1055"),
            ],
            flags=[],
            notes=[],
        ),
    }


ACCOUNTS = _make_accounts()


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

@dataclass
class BillingStatement:
    account_id: str
    period: str
    line_items: list[dict]
    total: float
    balance: float


def get_billing_statement(account_id: str, period: str = "current") -> BillingStatement | None:
    acct = ACCOUNTS.get(account_id)
    if not acct:
        return None
    plan = PLANS.get(acct.plan_id)
    if not plan:
        return None

    items = [
        {"description": f"{plan.name} Plan - Internet {plan.internet_mbps}Mbps", "amount": plan.monthly_rate * 0.55},
        {"description": f"{plan.name} Plan - Cable {plan.cable_channels} channels", "amount": plan.monthly_rate * 0.35},
        {"description": "Equipment rental", "amount": 10.00},
        {"description": "Taxes & fees", "amount": round(plan.monthly_rate * 0.08, 2)},
    ]

    # James Wilson gets an overcharge
    if account_id == "ACC-1004" and period in ("current", "2025-02"):
        items.append({"description": "Premium Sports Add-on (error)", "amount": 40.00})

    total = round(sum(i["amount"] for i in items), 2)
    return BillingStatement(account_id, period, items, total, acct.balance)


# ---------------------------------------------------------------------------
# Adjustment history
# ---------------------------------------------------------------------------

@dataclass
class Adjustment:
    date: str
    adjustment_code: str
    amount: float
    memo: str


ADJUSTMENT_HISTORY: dict[str, list[Adjustment]] = {
    "ACC-1001": [],
    "ACC-1002": [],
    "ACC-1003": [],
    "ACC-1004": [],
    "ACC-1005": [],
    "ACC-1006": [],
    "ACC-1007": [],
    "ACC-1008": [],
}


# ---------------------------------------------------------------------------
# Outages
# ---------------------------------------------------------------------------

@dataclass
class Outage:
    outage_id: str
    area: str
    node_ids: list[str]
    affected_services: list[str]
    started: str
    estimated_resolution: str
    auto_credit_per_day: float


ACTIVE_OUTAGES = [
    Outage(
        outage_id="OUT-2025-0312",
        area="downtown",
        node_ids=["NODE-DT-02", "NODE-DT-03"],
        affected_services=["internet", "cable"],
        started="2025-03-01T14:30:00",
        estimated_resolution="2025-03-04T18:00:00",
        auto_credit_per_day=2.50,
    ),
]


def get_outage_for_node(node_id: str) -> Outage | None:
    for o in ACTIVE_OUTAGES:
        if node_id in o.node_ids:
            return o
    return None


def get_outage_for_area(area: str) -> Outage | None:
    for o in ACTIVE_OUTAGES:
        if o.area == area:
            return o
    return None


# ---------------------------------------------------------------------------
# Signal test results
# ---------------------------------------------------------------------------

SIGNAL_TEST_RESULTS: dict[str, dict] = {
    "ACC-1003": {
        "downstream_snr": 28.5,
        "upstream_snr": 32.1,
        "downstream_power": -2.3,
        "upstream_power": 38.7,
        "packet_loss": 4.2,
        "speed_test": {"download_mbps": 85, "upload_mbps": 12, "expected_download": 300, "expected_upload": 20},
        "status": "degraded",
        "diagnosis": "Packet loss above threshold (>2%). Signal levels marginal. Likely local wiring or connector issue.",
    },
    "ACC-1008": {
        "downstream_snr": 25.1,
        "upstream_snr": 29.8,
        "downstream_power": -4.1,
        "upstream_power": 41.2,
        "packet_loss": 6.8,
        "speed_test": {"download_mbps": 120, "upload_mbps": 8, "expected_download": 500, "expected_upload": 25},
        "status": "degraded",
        "diagnosis": "High packet loss (6.8%). Signal power outside optimal range. Cable signal intermittent — likely splitter or drop cable issue.",
    },
}

# Default healthy result
DEFAULT_SIGNAL_TEST = {
    "downstream_snr": 38.2,
    "upstream_snr": 40.5,
    "downstream_power": 0.5,
    "upstream_power": 37.0,
    "packet_loss": 0.0,
    "speed_test": {"download_mbps": 298, "upload_mbps": 19, "expected_download": 300, "expected_upload": 20},
    "status": "normal",
    "diagnosis": "All signal levels within normal parameters. No issues detected.",
}


# ---------------------------------------------------------------------------
# Dispatch availability
# ---------------------------------------------------------------------------

DISPATCH_SLOTS = {
    "northside": [
        {"slot_id": "SLOT-NS-01", "date": "2025-03-05", "window": "8am-12pm", "job_type": "repair"},
        {"slot_id": "SLOT-NS-02", "date": "2025-03-05", "window": "1pm-5pm", "job_type": "repair"},
        {"slot_id": "SLOT-NS-03", "date": "2025-03-06", "window": "8am-12pm", "job_type": "repair"},
    ],
    "downtown": [
        {"slot_id": "SLOT-DT-01", "date": "2025-03-07", "window": "8am-12pm", "job_type": "repair"},
    ],
    "westend": [
        {"slot_id": "SLOT-WE-01", "date": "2025-03-05", "window": "8am-12pm", "job_type": "repair"},
        {"slot_id": "SLOT-WE-02", "date": "2025-03-06", "window": "1pm-5pm", "job_type": "repair"},
    ],
    "southend": [
        {"slot_id": "SLOT-SE-01", "date": "2025-03-05", "window": "1pm-5pm", "job_type": "repair"},
    ],
    "eastside": [
        {"slot_id": "SLOT-ES-01", "date": "2025-03-06", "window": "8am-12pm", "job_type": "repair"},
    ],
}


# ---------------------------------------------------------------------------
# Retention offers
# ---------------------------------------------------------------------------

RETENTION_OFFERS = {
    "ACC-1005": [
        {"offer_code": "RET-DISC-20", "description": "20% discount for 6 months", "monthly_savings": 10.00},
        {"offer_code": "RET-UPG-FREE", "description": "Free upgrade to Standard plan for 3 months", "monthly_savings": 30.00},
    ],
    "ACC-1006": [
        {"offer_code": "RET-DISC-15", "description": "15% discount for 6 months", "monthly_savings": 12.00},
        {"offer_code": "RET-HBO-FREE", "description": "Free HBO add-on for 6 months", "monthly_savings": 15.00},
    ],
    "ACC-1007": [
        {"offer_code": "RET-DISC-25", "description": "25% discount for 12 months", "monthly_savings": 37.50},
        {"offer_code": "RET-UPG-4K", "description": "Free 4K equipment upgrade", "monthly_savings": 0},
    ],
    "ACC-1008": [
        {"offer_code": "RET-DISC-20", "description": "20% discount for 6 months", "monthly_savings": 22.00},
    ],
}


# ---------------------------------------------------------------------------
# Scenarios — the 8 customers in order
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    scenario_index: int
    account_id: str
    customer_message: str
    category: str
    learning_pair_id: str | None
    is_learning_test: bool


SCENARIOS = [
    Scenario(
        scenario_index=1,
        account_id="ACC-1001",
        customer_message="My bill seems higher than usual, can you help me understand the charges?",
        category="billing",
        learning_pair_id=None,
        is_learning_test=False,
    ),
    Scenario(
        scenario_index=2,
        account_id="ACC-1002",
        customer_message="My internet was out for almost a week last month. I think I deserve some compensation.",
        category="credit",
        learning_pair_id="PAIR-A",
        is_learning_test=False,
    ),
    Scenario(
        scenario_index=3,
        account_id="ACC-1003",
        customer_message="My internet has been really slow for the past few days. Can you send someone to look at it?",
        category="technical",
        learning_pair_id="PAIR-B",
        is_learning_test=False,
    ),
    Scenario(
        scenario_index=4,
        account_id="ACC-1004",
        customer_message="I was overcharged $40 on my last bill. I need this corrected.",
        category="credit",
        learning_pair_id="PAIR-A",
        is_learning_test=True,
    ),
    Scenario(
        scenario_index=5,
        account_id="ACC-1005",
        customer_message="I want to cancel my service. I found a better deal with another provider.",
        category="retention",
        learning_pair_id="PAIR-C",
        is_learning_test=False,
    ),
    Scenario(
        scenario_index=6,
        account_id="ACC-1006",
        customer_message="Cancel my cable service. I'm just going to use streaming.",
        category="retention",
        learning_pair_id="PAIR-C",
        is_learning_test=True,
    ),
    Scenario(
        scenario_index=7,
        account_id="ACC-1007",
        customer_message="My internet has been down for 3 days! I want a credit for the downtime.",
        category="outage",
        learning_pair_id=None,
        is_learning_test=False,
    ),
    Scenario(
        scenario_index=8,
        account_id="ACC-1008",
        customer_message="My cable keeps freezing up and the picture cuts out every few minutes.",
        category="technical",
        learning_pair_id="PAIR-B",
        is_learning_test=True,
    ),
]


def get_scenario(index: int) -> Scenario | None:
    """Get scenario by 1-based index."""
    for s in SCENARIOS:
        if s.scenario_index == index:
            return s
    return None


def get_account(account_id: str) -> Account | None:
    return ACCOUNTS.get(account_id)


# ---------------------------------------------------------------------------
# Trouble ticket tracking (runtime state)
# ---------------------------------------------------------------------------

_trouble_tickets: dict[str, dict] = {}
_next_ticket_id = 1
_diagnostics_run: dict[str, bool] = {}  # account_id -> bool


def create_trouble_ticket(account_id: str, symptom_code: str, description: str) -> dict:
    global _next_ticket_id
    ticket_id = f"TT-{_next_ticket_id:04d}"
    _next_ticket_id += 1
    ticket = {
        "ticket_id": ticket_id,
        "account_id": account_id,
        "symptom_code": symptom_code,
        "description": description,
        "status": "open",
        "created": datetime.now().isoformat(),
    }
    _trouble_tickets[ticket_id] = ticket
    return ticket


def get_open_ticket(account_id: str) -> dict | None:
    for t in _trouble_tickets.values():
        if t["account_id"] == account_id and t["status"] == "open":
            return t
    return None


def mark_diagnostics_run(account_id: str):
    _diagnostics_run[account_id] = True


def has_diagnostics_run(account_id: str) -> bool:
    return _diagnostics_run.get(account_id, False)


def reset_runtime_state():
    """Reset ticket/diagnostic state between demo resets."""
    global _next_ticket_id
    _trouble_tickets.clear()
    _diagnostics_run.clear()
    _next_ticket_id = 1


# ---------------------------------------------------------------------------
# Retention eligibility check tracking
# ---------------------------------------------------------------------------

_retention_checked: dict[str, bool] = {}


def mark_retention_checked(account_id: str):
    _retention_checked[account_id] = True


def has_retention_checked(account_id: str) -> bool:
    return _retention_checked.get(account_id, False)
