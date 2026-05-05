# compose-persona dry-run output

This directory holds the sandbox output of running `compose-persona` against
[`docs/superpowers/specs/controller-persona-brief.yaml`](../../../docs/superpowers/specs/controller-persona-brief.yaml).
The sandbox is the only place these files exist — `graduate.sh` is what
copies them into the live trees.

The dry run validates that:

1. The brief schema (`compose-persona` v1) is sufficient to author a
   persona that uses the delegated-authority MCP.
2. The generated SKILL.md compiles through the persona-responder sandbox.
3. The generated registry entry passes
   `tests/api/shared/test_personas_registry.py`.

Re-running `compose-persona` from the same brief overwrites the sandbox
contents but does not touch the live trees. Graduation is explicitly the
operator's call.
