# Splice into api/shared/personas.py inside the PERSONAS dict.
# Place under a new `# ----- AP / Finance -----` section header (or inside
# the existing finance block — operator's call).
"controller": Persona(
    role="controller",
    archetype="approver",
    scope_function="finance",
    workflow_label="AP / Finance",
    external_event_default="controller_signoff_decision",
    scope_business_unit="*",
    scope_geography="*",
    default_authority_band="£25k-£250k AP invoices and material expense claims",
    uses_authority_mcp=True,
    description="Approves AP invoices and material expense claims within the controller band; escalates to CFO above £250k.",
),
