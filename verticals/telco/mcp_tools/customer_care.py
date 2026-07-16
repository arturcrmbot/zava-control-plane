"""SDK-native tools used by proactive customer-care agents."""
from __future__ import annotations

import json

from copilot.tools import ToolResult, define_tool
from pydantic import BaseModel, Field


def lookup_entitlement(
    segment: str, vulnerable: bool, approval_required: bool
) -> dict:
    if approval_required:
        credit = 50.0
    elif vulnerable:
        credit = 20.0
    elif segment == "priority_business":
        credit = 10.0
    else:
        credit = 5.0
    return {
        "credit_amount": credit,
        "channel": "email" if segment == "priority_business" else "sms",
        "requires_approval": approval_required,
        "policy": "TELCO-CARE-001",
    }


def prepare_notification(account_id: str, channel: str) -> dict:
    return {
        "account_id": account_id,
        "channel": channel,
        "message": "We restored your service and applied the appropriate care package.",
    }


def prepare_credit(account_id: str, amount: float, approved: bool) -> dict:
    return {
        "account_id": account_id,
        "credit_amount": amount,
        "authority_approved": approved,
    }


class _EntitlementParams(BaseModel):
    segment: str
    vulnerable: bool = False
    approval_required: bool = False


@define_tool(
    name="customer_care_policy_lookup",
    description="Resolve the synthetic Telco care entitlement for an impacted account.",
)
def customer_care_policy_lookup_tool(params: _EntitlementParams) -> ToolResult:
    return ToolResult(
        text_result_for_llm=json.dumps(
            lookup_entitlement(
                params.segment, params.vulnerable, params.approval_required
            )
        )
    )


class _NotificationParams(BaseModel):
    account_id: str
    channel: str = Field(pattern="^(sms|email)$")


@define_tool(
    name="customer_care_prepare_notification",
    description="Prepare a truthful service-restoration notification.",
)
def customer_care_prepare_notification_tool(
    params: _NotificationParams,
) -> ToolResult:
    return ToolResult(
        text_result_for_llm=json.dumps(
            prepare_notification(params.account_id, params.channel)
        )
    )


class _CreditParams(BaseModel):
    account_id: str
    amount: float = Field(ge=0)
    approved: bool


@define_tool(
    name="customer_care_prepare_credit",
    description="Prepare a governed credit adjustment for world execution.",
)
def customer_care_prepare_credit_tool(params: _CreditParams) -> ToolResult:
    return ToolResult(
        text_result_for_llm=json.dumps(
            prepare_credit(params.account_id, params.amount, params.approved)
        )
    )
