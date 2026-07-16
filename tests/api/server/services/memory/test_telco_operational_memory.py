import pytest

from api.server.services.memory.domain_memory import configured_memory_domains


def test_telco_profile_defaults_to_registered_telco_memory_domains():
    assert configured_memory_domains(
        raw=None,
        allowed=(
            "network-incident",
            "proactive-customer-care",
        ),
    ) == ["network-incident", "proactive-customer-care"]


def test_unset_profile_preserves_existing_hiring_default():
    assert configured_memory_domains(
        raw=None,
        allowed=("hiring",),
    ) == ["hiring"]


def test_explicit_memory_domains_must_belong_to_active_pack():
    with pytest.raises(
        ValueError,
        match="memory domains not in active pack: \\['vendor_kyc'\\]",
    ):
        configured_memory_domains(
            raw="vendor_kyc, network-incident",
            allowed=("network-incident",),
        )


def test_explicit_active_memory_domains_are_preserved():
    assert configured_memory_domains(
        raw="proactive-customer-care, network-incident",
        allowed=("network-incident", "proactive-customer-care"),
    ) == ["proactive-customer-care", "network-incident"]
