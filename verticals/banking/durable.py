"""Zava Bank Durable registration root.

Creates the pack's single DFApp and wires every orchestrator and activity
onto it. One app, two modules: the hero and the shared supporting engine.
"""
from __future__ import annotations

from api.functions.kernel_registration import create_app

app = create_app()

from verticals.banking import fraud_durable  # noqa: E402

fraud_durable.register(app)

from verticals.banking import supporting_durable  # noqa: E402

supporting_durable.register(app)
