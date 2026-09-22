from verticals._helpers import lazy_projection
from verticals.banking.fraud_constants import FRAUD_WORKFLOW_TYPE
from verticals.banking.support_constants import (
    MERCHANT_WORKFLOW_TYPE,
    MULE_WORKFLOW_TYPE,
)


BANKING_PROJECTIONS = {
    FRAUD_WORKFLOW_TYPE: lazy_projection(
        "verticals.banking.entity_projections.fraud"
    ),
    MULE_WORKFLOW_TYPE: lazy_projection(
        "verticals.banking.entity_projections.supporting"
    ),
    MERCHANT_WORKFLOW_TYPE: lazy_projection(
        "verticals.banking.entity_projections.supporting"
    ),
}
