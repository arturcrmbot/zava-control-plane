from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


EXPECTED_WORKFLOWS = {
    "inventory-rebalancing",
    "demand-spike-response",
    "promotion-readiness",
    "markdown-governance",
    "supplier-delay-recovery",
    "fulfilment-exception-resolution",
    "marketplace-seller-exception",
    "returns-disposition",
}


def test_fashion_portfolio_contains_exactly_the_approved_workflows() -> None:
    assert set(FASHION_PROCESS_PROFILES) == EXPECTED_WORKFLOWS
    assert len(FASHION_PROCESS_PROFILES) == 8
    assert all(not profile.stub for profile in FASHION_PROCESS_PROFILES.values())


def test_inventory_rebalancing_is_the_only_hero_with_approved_phases() -> None:
    heroes = [
        profile
        for profile in FASHION_PROCESS_PROFILES.values()
        if profile.kind == "hero"
    ]

    assert [profile.workflow_type for profile in heroes] == [
        "inventory-rebalancing"
    ]
    assert tuple((phase.name, phase.kind) for phase in heroes[0].phases) == (
        ("Detect Imbalance", "deterministic"),
        ("Assess Demand and Constraints", "agent"),
        ("Plan Rebalance", "agent"),
        ("Approve Exception", "hitl"),
        ("Execute Stock Action", "deterministic"),
        ("Verify Outcome", "deterministic"),
    )
    assert heroes[0].command_type == "inventory.transfer"
    assert heroes[0].skills == (
        "inventory-imbalance-analysis",
        "inventory-rebalance-planner",
    )


def test_each_fashion_workflow_has_distinct_executable_contracts() -> None:
    profiles = tuple(FASHION_PROCESS_PROFILES.values())

    assert len({profile.sensor_id for profile in profiles}) == len(profiles)
    assert len({profile.objective_type for profile in profiles}) == len(profiles)
    assert len({profile.command_type for profile in profiles}) == len(profiles)
    assert len({profile.success_event for profile in profiles}) == len(profiles)
    assert len({profile.case_id for profile in profiles}) == len(profiles)
    assert all(profile.orchestrator_name for profile in profiles)
    assert all(profile.phases for profile in profiles)
    assert all(profile.command_type in profile.allowed_actions for profile in profiles)


def test_fashion_workflow_ownership_matches_the_approved_function_tree() -> None:
    ownership = {
        workflow_type: profile.function
        for workflow_type, profile in FASHION_PROCESS_PROFILES.items()
    }

    assert ownership == {
        "inventory-rebalancing": "merchandising-planning",
        "demand-spike-response": "merchandising-planning",
        "promotion-readiness": "merchandising-planning",
        "markdown-governance": "merchandising-planning",
        "supplier-delay-recovery": "supply-chain-fulfilment",
        "fulfilment-exception-resolution": "supply-chain-fulfilment",
        "marketplace-seller-exception": "marketplace-operations",
        "returns-disposition": "customer-returns",
    }


def test_all_approved_reasoning_skills_are_used_by_the_portfolio() -> None:
    used_skills = {
        skill
        for profile in FASHION_PROCESS_PROFILES.values()
        for skill in profile.skills
    }

    assert used_skills == {
        "inventory-imbalance-analysis",
        "inventory-rebalance-planner",
        "promotion-readiness-assessor",
        "markdown-option-advisor",
        "supplier-recovery-planner",
        "fulfilment-resolution-advisor",
        "seller-exception-assessor",
        "returns-disposition-advisor",
    }
