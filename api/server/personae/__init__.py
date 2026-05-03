"""Personae (compose-domain v1).

Each subdirectory is one persona role used by a generated-domain HITL
gate. The SKILL.md inside states the persona's decision policy and the
external event payload they emit when they decide.

Personae are NOT loaded by the runtime GHCP SDK in the same way as
`api/server/skills/` — they are intended for the persona-responder
service that closes HITL gates by reading the parked workflow and
emitting the resolving external event. (That responder service does not
yet exist; v1 closes gates manually via the existing
`/internal/durable_event` route.)
"""
