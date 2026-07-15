from api.server.services.memory.domain_memory import configured_memory_domains


def test_telco_profile_defaults_to_registered_telco_memory_domains():
    assert configured_memory_domains(
        raw=None,
        vertical_name="telco",
        registered_workflow_types=(
            "network-incident",
            "proactive-customer-care",
            "hiring",
        ),
    ) == ["network-incident", "proactive-customer-care"]


def test_unset_profile_preserves_existing_hiring_default():
    assert configured_memory_domains(
        raw=None,
        vertical_name=None,
        registered_workflow_types=("network-incident", "hiring"),
    ) == ["hiring"]


def test_explicit_memory_domains_override_vertical_default():
    assert configured_memory_domains(
        raw="vendor_kyc, network-incident",
        vertical_name="telco",
        registered_workflow_types=("network-incident",),
    ) == ["vendor_kyc", "network-incident"]
