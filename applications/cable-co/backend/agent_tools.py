"""CableConnect — 19 tools (lookup + action) with business rule hints for CSR."""

import json
from datetime import datetime, timedelta

from telecom_data import (
    ACCOUNTS, PLANS, RATE_CODES, ADJUSTMENT_HISTORY,
    SIGNAL_TEST_RESULTS, DEFAULT_SIGNAL_TEST, DISPATCH_SLOTS,
    RETENTION_OFFERS,
    get_account, get_billing_statement, get_outage_for_node, get_outage_for_area,
    get_open_ticket, create_trouble_ticket as _create_ticket,
    has_diagnostics_run, mark_diagnostics_run,
    has_retention_checked, mark_retention_checked,
    Adjustment,
)


# ---------------------------------------------------------------------------
# Tool type classification
# ---------------------------------------------------------------------------

LOOKUP_TOOLS = {
    "get_account_summary", "get_service_agreement", "get_account_flags",
    "get_billing_statement", "get_adjustment_history", "get_service_codes",
    "get_equipment_inventory", "check_node_status", "run_signal_test",
    "check_dispatch_availability", "check_retention_eligibility", "get_retention_offers",
}

ACTION_TOOLS = {
    "suggest_response",
    "post_adjustment", "create_service_order", "create_trouble_ticket",
    "schedule_dispatch", "create_equipment_order", "apply_retention_offer",
    "resolve_interaction",
}

TERMINAL_TOOLS: set[str] = set()


# ---------------------------------------------------------------------------
# Tool definitions for LLM
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    # === Lookup Tools ===
    {
        "type": "function",
        "function": {
            "name": "get_account_summary",
            "description": "Retrieve a customer account summary including name, plan, tenure, node ID, area, address, and equipment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID (e.g. ACC-1001)"}
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_agreement",
            "description": "Retrieve the service agreement details for an account, including contract status, terms, early termination fee, and expiration date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"}
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_flags",
            "description": "Retrieve internal account flags, notes, and alerts for a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"}
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_billing_statement",
            "description": "Retrieve the billing statement for an account showing line items, charges, credits, and balance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"},
                    "period": {"type": "string", "description": "Billing period (e.g. 'current', '2025-02')", "default": "current"},
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_adjustment_history",
            "description": "Retrieve the history of billing adjustments on an account, including dates, codes, and amounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"}
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_codes",
            "description": "Retrieve the rate codes and feature codes for a service plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_name": {"type": "string", "description": "The plan name (basic, standard, premium, ultra)"}
                },
                "required": ["plan_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_equipment_inventory",
            "description": "Retrieve the equipment inventory for an account, including model, tier, and serial numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"}
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_node_status",
            "description": "Check the health and status of a network node, including any active outages and affected services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "The network node ID (e.g. NODE-DT-02)"}
                },
                "required": ["node_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_signal_test",
            "description": "Run remote signal diagnostics on a customer's line, returning signal levels, packet loss, and speed test results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"}
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_dispatch_availability",
            "description": "Check available technician dispatch time slots for an area and job type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "Service area (northside, downtown, westend, southend, eastside)"},
                    "job_type": {"type": "string", "description": "Job type (repair, install, upgrade)", "default": "repair"},
                },
                "required": ["area"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_retention_eligibility",
            "description": "Check if a customer is eligible for retention offers based on account history and value score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"}
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_retention_offers",
            "description": "Retrieve available retention offers for an eligible customer account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"}
                },
                "required": ["account_id"],
            },
        },
    },
    # === Action Tools ===
    {
        "type": "function",
        "function": {
            "name": "suggest_response",
            "description": "Suggest a response message to send to the customer. The CSR will review and approve or edit before sending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"},
                    "message": {"type": "string", "description": "The suggested message to send to the customer"},
                },
                "required": ["account_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_adjustment",
            "description": "Post a billing adjustment (credit or charge) to a customer account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"},
                    "adjustment_code": {"type": "string", "description": "Adjustment code (COURTESY, OUTAGE, BILLING_ERROR, PROMO, SERVICE_ISSUE)"},
                    "amount": {"type": "number", "description": "Credit amount (positive number, will be applied as credit)"},
                    "memo": {"type": "string", "description": "Memo/reason for the adjustment"},
                },
                "required": ["account_id", "adjustment_code", "amount", "memo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_service_order",
            "description": "Create a service order for plan changes, transfers, or disconnects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"},
                    "order_type": {"type": "string", "description": "Order type: CHG (change), TRF (transfer), DIS (disconnect)"},
                    "params": {"type": "object", "description": "Order parameters (varies by type — rate_code for CHG, address for TRF, reason_code for DIS)"},
                },
                "required": ["account_id", "order_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_trouble_ticket",
            "description": "Create a trouble ticket for a customer's service issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"},
                    "symptom_code": {"type": "string", "description": "Symptom code (SLOW_INTERNET, NO_INTERNET, CABLE_FREEZE, NO_CABLE, INTERMITTENT)"},
                    "description": {"type": "string", "description": "Description of the issue"},
                },
                "required": ["account_id", "symptom_code", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_dispatch",
            "description": "Schedule a technician dispatch for an open trouble ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "The trouble ticket ID"},
                    "slot_id": {"type": "string", "description": "The dispatch slot ID from check_dispatch_availability"},
                },
                "required": ["ticket_id", "slot_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_equipment_order",
            "description": "Create an equipment order for swap, upgrade, or return.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"},
                    "action": {"type": "string", "description": "Action: SWAP, UPGRADE, RETURN"},
                    "equipment_type": {"type": "string", "description": "Equipment type: modem, cable_box, router"},
                },
                "required": ["account_id", "action", "equipment_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_retention_offer",
            "description": "Apply a retention offer to a customer account to prevent cancellation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"},
                    "offer_code": {"type": "string", "description": "The retention offer code from get_retention_offers"},
                },
                "required": ["account_id", "offer_code"],
            },
        },
    },
    # === Resolve (CSR-gated) ===
    {
        "type": "function",
        "function": {
            "name": "resolve_interaction",
            "description": "Mark the customer interaction as resolved. Only use this AFTER the customer has confirmed they are satisfied or has said goodbye. Do NOT resolve while the customer still has questions or concerns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "The customer account ID"},
                    "resolution_code": {"type": "string", "description": "Resolution code: RESOLVED, ESCALATED, CANCELLED, FOLLOWUP"},
                    "summary": {"type": "string", "description": "Summary of what was done and the outcome"},
                },
                "required": ["account_id", "resolution_code", "summary"],
            },
        },
    },
]


def get_tool_definitions() -> list[dict]:
    return TOOL_DEFINITIONS


# ---------------------------------------------------------------------------
# Lookup tool implementations
# ---------------------------------------------------------------------------

def _exec_get_account_summary(account_id: str) -> str:
    acct = get_account(account_id)
    if not acct:
        return f"Account {account_id} not found."
    plan = PLANS.get(acct.plan_id)
    return json.dumps({
        "account_id": acct.account_id,
        "name": acct.name,
        "plan": plan.name if plan else acct.plan_id,
        "monthly_rate": f"${plan.monthly_rate:.2f}" if plan else "N/A",
        "internet_speed": f"{plan.internet_mbps}Mbps" if plan else "N/A",
        "cable_channels": plan.cable_channels if plan else "N/A",
        "tenure_months": acct.tenure_months,
        "area": acct.area,
        "node_id": acct.node_id,
        "address": acct.address,
        "equipment_count": len(acct.equipment),
    })


def _exec_get_service_agreement(account_id: str) -> str:
    acct = get_account(account_id)
    if not acct:
        return f"Account {account_id} not found."
    if acct.contract_months > 0:
        remaining = max(0, acct.contract_months - acct.tenure_months)
        etf = remaining * 10
        expiration = (datetime.now() + timedelta(days=remaining * 30)).strftime("%Y-%m-%d")
        return json.dumps({
            "account_id": acct.account_id,
            "contract_status": "active",
            "contract_term": f"{acct.contract_months} months",
            "months_remaining": remaining,
            "early_termination_fee": f"${etf:.2f}",
            "expiration_date": expiration,
        })
    return json.dumps({
        "account_id": acct.account_id,
        "contract_status": "month-to-month",
        "contract_term": "None",
        "early_termination_fee": "$0.00",
    })


def _exec_get_account_flags(account_id: str) -> str:
    acct = get_account(account_id)
    if not acct:
        return f"Account {account_id} not found."
    return json.dumps({
        "account_id": acct.account_id,
        "flags": acct.flags if acct.flags else ["none"],
        "notes": acct.notes if acct.notes else ["No notes"],
    })


def _exec_get_billing_statement(account_id: str, period: str = "current") -> str:
    stmt = get_billing_statement(account_id, period)
    if not stmt:
        return f"No billing statement found for {account_id}."
    return json.dumps({
        "account_id": stmt.account_id,
        "period": stmt.period,
        "line_items": stmt.line_items,
        "total": f"${stmt.total:.2f}",
        "balance_due": f"${stmt.balance:.2f}",
    })


def _exec_get_adjustment_history(account_id: str) -> str:
    history = ADJUSTMENT_HISTORY.get(account_id, [])
    if not history:
        return json.dumps({"account_id": account_id, "adjustments": [], "message": "No adjustment history found."})
    return json.dumps({
        "account_id": account_id,
        "adjustments": [
            {"date": a.date, "code": a.adjustment_code, "amount": f"${a.amount:.2f}", "memo": a.memo}
            for a in history
        ],
    })


def _exec_get_service_codes(plan_name: str) -> str:
    codes = RATE_CODES.get(plan_name.lower())
    if not codes:
        return f"Unknown plan: {plan_name}. Valid plans: basic, standard, premium, ultra."
    return json.dumps({"plan": plan_name, **codes})


def _exec_get_equipment_inventory(account_id: str) -> str:
    acct = get_account(account_id)
    if not acct:
        return f"Account {account_id} not found."
    return json.dumps({
        "account_id": acct.account_id,
        "equipment": [
            {"id": e.equipment_id, "type": e.equipment_type, "model": e.model, "tier": e.tier, "serial": e.serial}
            for e in acct.equipment
        ],
    })


def _exec_check_node_status(node_id: str) -> str:
    outage = get_outage_for_node(node_id)
    if outage:
        return json.dumps({
            "node_id": node_id,
            "status": "outage",
            "outage_id": outage.outage_id,
            "affected_services": outage.affected_services,
            "started": outage.started,
            "estimated_resolution": outage.estimated_resolution,
            "auto_credit_per_day": f"${outage.auto_credit_per_day:.2f}",
        })
    return json.dumps({"node_id": node_id, "status": "healthy", "active_outages": 0})


def _exec_run_signal_test(account_id: str) -> str:
    mark_diagnostics_run(account_id)
    result = SIGNAL_TEST_RESULTS.get(account_id, DEFAULT_SIGNAL_TEST)
    return json.dumps({"account_id": account_id, **result})


def _exec_check_dispatch_availability(area: str, job_type: str = "repair") -> str:
    slots = DISPATCH_SLOTS.get(area, [])
    matching = [s for s in slots if s["job_type"] == job_type]
    return json.dumps({"area": area, "job_type": job_type, "available_slots": matching})


def _exec_check_retention_eligibility(account_id: str) -> str:
    acct = get_account(account_id)
    if not acct:
        return f"Account {account_id} not found."
    mark_retention_checked(account_id)
    eligible = acct.tenure_months >= 24
    value_score = min(100, acct.tenure_months * 3 + (10 if acct.plan_id in ("premium", "ultra") else 0))
    return json.dumps({
        "account_id": acct.account_id,
        "eligible": eligible,
        "tenure_months": acct.tenure_months,
        "value_score": value_score,
        "reason": "Meets 24-month tenure requirement" if eligible else f"Does not meet 24-month tenure requirement ({acct.tenure_months} months)",
    })


def _exec_get_retention_offers(account_id: str) -> str:
    offers = RETENTION_OFFERS.get(account_id, [])
    if not offers:
        return json.dumps({"account_id": account_id, "offers": [], "message": "No retention offers available."})
    return json.dumps({"account_id": account_id, "offers": offers})


# ---------------------------------------------------------------------------
# Execute lookup tools (auto-run, no CSR gate)
# ---------------------------------------------------------------------------

def execute_lookup(tool_name: str, arguments: dict) -> str:
    """Execute a lookup tool. Returns result text."""
    dispatch = {
        "get_account_summary": lambda a: _exec_get_account_summary(a["account_id"]),
        "get_service_agreement": lambda a: _exec_get_service_agreement(a["account_id"]),
        "get_account_flags": lambda a: _exec_get_account_flags(a["account_id"]),
        "get_billing_statement": lambda a: _exec_get_billing_statement(a["account_id"], a.get("period", "current")),
        "get_adjustment_history": lambda a: _exec_get_adjustment_history(a["account_id"]),
        "get_service_codes": lambda a: _exec_get_service_codes(a["plan_name"]),
        "get_equipment_inventory": lambda a: _exec_get_equipment_inventory(a["account_id"]),
        "check_node_status": lambda a: _exec_check_node_status(a["node_id"]),
        "run_signal_test": lambda a: _exec_run_signal_test(a["account_id"]),
        "check_dispatch_availability": lambda a: _exec_check_dispatch_availability(a["area"], a.get("job_type", "repair")),
        "check_retention_eligibility": lambda a: _exec_check_retention_eligibility(a["account_id"]),
        "get_retention_offers": lambda a: _exec_get_retention_offers(a["account_id"]),
    }
    fn = dispatch.get(tool_name)
    if fn:
        return fn(arguments)
    return f"Unknown lookup tool: {tool_name}"


# ---------------------------------------------------------------------------
# Execute action tools (called AFTER CSR approves)
# ---------------------------------------------------------------------------

def execute_action(tool_name: str, arguments: dict) -> str:
    """Execute an action tool after CSR approval. Returns result text."""
    if tool_name == "suggest_response":
        return arguments.get("message", "")

    if tool_name == "post_adjustment":
        adj = Adjustment(
            date=datetime.now().strftime("%Y-%m-%d"),
            adjustment_code=arguments["adjustment_code"],
            amount=float(arguments["amount"]),
            memo=arguments.get("memo", ""),
        )
        ADJUSTMENT_HISTORY.setdefault(arguments["account_id"], []).append(adj)
        return f"Credit of ${float(arguments['amount']):.2f} ({arguments['adjustment_code']}) posted to {arguments['account_id']}."

    if tool_name == "create_service_order":
        return f"Service order {arguments['order_type']} created for {arguments['account_id']}."

    if tool_name == "create_trouble_ticket":
        ticket = _create_ticket(arguments["account_id"], arguments["symptom_code"], arguments.get("description", ""))
        return f"Trouble ticket {ticket['ticket_id']} created for {arguments['account_id']}."

    if tool_name == "schedule_dispatch":
        slot_id = arguments["slot_id"]
        for area_slots in DISPATCH_SLOTS.values():
            for slot in area_slots:
                if slot["slot_id"] == slot_id:
                    return f"Technician dispatch scheduled for {slot['date']} {slot['window']} (ticket {arguments['ticket_id']})."
        return f"Dispatch scheduled with slot {slot_id} for ticket {arguments['ticket_id']}."

    if tool_name == "create_equipment_order":
        return f"Equipment order ({arguments['action']}) for {arguments['equipment_type']} created for {arguments['account_id']}."

    if tool_name == "apply_retention_offer":
        return f"Retention offer {arguments['offer_code']} applied to {arguments['account_id']}."

    if tool_name == "resolve_interaction":
        return f"INTERACTION RESOLVED: {arguments.get('resolution_code', 'RESOLVED')} — {arguments.get('summary', '')}"

    return f"Unknown action tool: {tool_name}"


# ---------------------------------------------------------------------------
# Execute terminal tool
# ---------------------------------------------------------------------------

def execute_terminal(tool_name: str, arguments: dict) -> str:
    if tool_name == "resolve_interaction":
        return f"INTERACTION RESOLVED: {arguments.get('resolution_code', 'RESOLVED')} — {arguments.get('summary', '')}"
    return f"Unknown terminal tool: {tool_name}"


# ---------------------------------------------------------------------------
# Business rule hints — suggest rejection feedback to the presenter
# ---------------------------------------------------------------------------

def get_rejection_hint(tool_name: str, arguments: dict) -> str | None:
    """Check business rules and return a suggested rejection reason, or None if OK."""
    if tool_name == "post_adjustment":
        return _hint_post_adjustment(arguments)
    if tool_name == "create_service_order":
        return _hint_create_service_order(arguments)
    if tool_name == "create_trouble_ticket":
        return _hint_create_trouble_ticket(arguments)
    if tool_name == "schedule_dispatch":
        return _hint_schedule_dispatch(arguments)
    if tool_name == "apply_retention_offer":
        return _hint_apply_retention_offer(arguments)
    return None


def _hint_post_adjustment(args: dict) -> str | None:
    amount = float(args.get("amount", 0))
    if amount > 25:
        return (
            "That's over our $25 per-adjustment limit. You'd need to cap it at $25 "
            "or escalate to a supervisor for the full amount."
        )
    code = args.get("adjustment_code", "").upper()
    if code == "OUTAGE":
        acct = get_account(args.get("account_id", ""))
        if acct:
            outage = get_outage_for_area(acct.area)
            if outage:
                return (
                    f"There's an active outage in their area — automatic credits of "
                    f"${outage.auto_credit_per_day:.2f}/day will post when it's resolved. "
                    f"We don't do manual outage credits while it's still ongoing."
                )
    history = ADJUSTMENT_HISTORY.get(args.get("account_id", ""), [])
    if history:
        last = history[-1]
        last_date = datetime.strptime(last.date, "%Y-%m-%d")
        next_eligible = last_date + timedelta(days=90)
        if datetime.now() < next_eligible:
            return (
                f"This account already got an adjustment on {last.date}. "
                f"We can only do one per 90 days. Next eligible: {next_eligible.strftime('%Y-%m-%d')}."
            )
    return None


def _hint_create_service_order(args: dict) -> str | None:
    acct = get_account(args.get("account_id", ""))
    if not acct:
        return None
    order_type = args.get("order_type", "").upper()
    params = args.get("params") or {}
    if order_type == "CHG" and acct.contract_months > 0:
        remaining = max(0, acct.contract_months - acct.tenure_months)
        if remaining > 0:
            etf = remaining * 10
            exp = (datetime.now() + timedelta(days=remaining * 30)).strftime("%Y-%m-%d")
            return (
                f"They're under contract until {exp}. Can't downgrade without the "
                f"early termination fee. You need to disclose the ${etf:.2f} ETF before proceeding."
            )
    if order_type == "CHG" and "rate_code" not in params:
        return "You need to include the rate code for the new plan. Look it up with get_service_codes first."
    if order_type == "DIS" and "reason_code" not in params:
        return "Need a disconnect reason code — VOLUNTARY, NONPAY, MOVE_NOSERVICE, or DECEASED."
    return None


def _hint_create_trouble_ticket(args: dict) -> str | None:
    acct = get_account(args.get("account_id", ""))
    if not acct:
        return None
    outage = get_outage_for_node(acct.node_id)
    if outage:
        return (
            "There's already an area-wide outage on their node. We don't create individual "
            "tickets during outages — they'll get notified when it's resolved."
        )
    return None


def _hint_schedule_dispatch(args: dict) -> str | None:
    from telecom_data import _trouble_tickets
    ticket = _trouble_tickets.get(args.get("ticket_id", ""))
    if not ticket:
        return "You need an open trouble ticket before you can schedule a dispatch."
    account_id = ticket.get("account_id")
    if account_id and not has_diagnostics_run(account_id):
        return (
            "We need to run remote diagnostics first. Company policy — 70% of issues are "
            "fixable remotely and it saves a $150 truck roll."
        )
    if account_id:
        acct = get_account(account_id)
        if acct:
            outage = get_outage_for_area(acct.area)
            if outage:
                return f"Dispatch is suspended in {acct.area} during the active outage."
    return None


def _hint_apply_retention_offer(args: dict) -> str | None:
    acct = get_account(args.get("account_id", ""))
    if not acct:
        return None
    if not has_retention_checked(args.get("account_id", "")):
        return "Need to run a retention eligibility check first before pulling up offers."
    if acct.tenure_months < 24:
        return (
            f"Retention offers are only for customers with 24+ months tenure. "
            f"This customer has {acct.tenure_months} months. Just process the standard cancellation."
        )
    return None
