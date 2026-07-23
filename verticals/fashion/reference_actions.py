from __future__ import annotations


FASHION_REFERENCE_ACTIONS = {
    "inventory-rebalancing": {
        "type": "inventory.transfer",
        "required": (
            "command_id",
            "workflow_id",
            "source_location_id",
            "destination_location_id",
            "sku_id",
            "quantity",
            "ownership",
            "expected_source_version",
            "expected_destination_version",
            "policy_decision",
            "evidence_digest",
        ),
    },
    "demand-spike-response": {
        "type": "allocation.adjust",
        "required": ("case_id", "subject_ids", "action"),
    },
    "promotion-readiness": {
        "type": "promotion.prepare",
        "required": ("case_id", "subject_ids", "action"),
    },
    "markdown-governance": {
        "type": "markdown.recommend",
        "required": ("case_id", "subject_ids", "action", "approval_decision"),
    },
    "supplier-delay-recovery": {
        "type": "supplier.recover",
        "required": ("case_id", "subject_ids", "action", "approval_decision"),
    },
    "fulfilment-exception-resolution": {
        "type": "fulfilment.resolve",
        "required": ("case_id", "subject_ids", "action"),
    },
    "marketplace-seller-exception": {
        "type": "seller.offer.suppress",
        "required": ("case_id", "subject_ids", "action", "approval_decision"),
    },
    "returns-disposition": {
        "type": "return.disposition",
        "required": ("case_id", "subject_ids", "action"),
    },
}

