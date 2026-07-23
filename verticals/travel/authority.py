"""Travel: the fourteen-row bounded GBP authority matrix (generated
by verticals.travel.generator.pack_templates).

Eight process roles plus their six escalation heads. Every bound is
cross-checked against the locked reference-case fixtures in
tests/api/world/actor/test_travel_process_commands.py.

Do not hand-edit -- change the generator template (or
verticals.travel.generator.portfolio) and regenerate via
`uv run python -m verticals.travel.generator`.
"""
from __future__ import annotations

from api.shared.authority_contracts import AuthorityRow

TRAVEL_AUTHORITY: dict[str, AuthorityRow] = {
    'travel_adviser': AuthorityRow(
        role='travel_adviser',
        spend_limit_gbp=2000.0,
        approval_actions=('confirm_package_booking',),
        delegate_to='head_of_commercial',
    ),
    'revenue_manager': AuthorityRow(
        role='revenue_manager',
        spend_limit_gbp=5000.0,
        approval_actions=('adjust_package_allotment',),
        delegate_to='head_of_commercial',
    ),
    'operations_controller': AuthorityRow(
        role='operations_controller',
        spend_limit_gbp=750.0,
        approval_actions=('reaccommodate_travellers',),
        delegate_to='head_of_operations',
    ),
    'accommodation_manager': AuthorityRow(
        role='accommodation_manager',
        spend_limit_gbp=5000.0,
        approval_actions=('move_hotel_allotment',),
        delegate_to='head_of_accommodation',
    ),
    'finance_operations_lead': AuthorityRow(
        role='finance_operations_lead',
        spend_limit_gbp=2000.0,
        approval_actions=('cancel_and_refund_booking',),
        delegate_to='head_of_customer_finance',
    ),
    'payments_specialist': AuthorityRow(
        role='payments_specialist',
        spend_limit_gbp=5000.0,
        approval_actions=('resolve_payment_exception',),
        delegate_to='head_of_customer_finance',
    ),
    'destination_operations_manager': AuthorityRow(
        role='destination_operations_manager',
        spend_limit_gbp=1000.0,
        approval_actions=('dispatch_replacement_transfer',),
        delegate_to='head_of_destination_operations',
    ),
    'customer_care_lead': AuthorityRow(
        role='customer_care_lead',
        spend_limit_gbp=500.0,
        approval_actions=('issue_customer_care_action',),
        delegate_to='head_of_customer_care',
    ),
    'head_of_commercial': AuthorityRow(
        role='head_of_commercial',
        spend_limit_gbp=50000.0,
        approval_actions=('confirm_package_booking', 'adjust_package_allotment'),
        delegate_to=None,
    ),
    'head_of_operations': AuthorityRow(
        role='head_of_operations',
        spend_limit_gbp=2000000.0,
        approval_actions=('reaccommodate_travellers',),
        delegate_to=None,
    ),
    'head_of_accommodation': AuthorityRow(
        role='head_of_accommodation',
        spend_limit_gbp=50000.0,
        approval_actions=('move_hotel_allotment',),
        delegate_to=None,
    ),
    'head_of_customer_finance': AuthorityRow(
        role='head_of_customer_finance',
        spend_limit_gbp=50000.0,
        approval_actions=('cancel_and_refund_booking', 'resolve_payment_exception'),
        delegate_to=None,
    ),
    'head_of_destination_operations': AuthorityRow(
        role='head_of_destination_operations',
        spend_limit_gbp=50000.0,
        approval_actions=('dispatch_replacement_transfer',),
        delegate_to=None,
    ),
    'head_of_customer_care': AuthorityRow(
        role='head_of_customer_care',
        spend_limit_gbp=20000.0,
        approval_actions=('issue_customer_care_action',),
        delegate_to=None,
    ),
}
