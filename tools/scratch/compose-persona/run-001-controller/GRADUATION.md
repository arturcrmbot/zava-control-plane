# Graduation — controller persona

`graduate.sh` mechanically performs steps 1–2 below. Steps 3–4 are
manual operator calls.

1. Copy `api/server/personae/controller/SKILL.md` from this sandbox
   into the live tree at `api/server/personae/controller/SKILL.md`.
2. Print the contents of `REGISTRY-ENTRY.py` to stdout for the operator
   to paste into `api/shared/personas.py`.
3. **Manual:** open `api/shared/personas.py` and splice the printed
   entry into the `PERSONAS` dict. Place under a new `# ----- AP /
   Finance -----` section header, or inside the existing finance block
   — operator's call.
4. **Manual:** run `uv run pytest tests/api/shared/test_personas_registry.py`
   and confirm the new entry validates.

Optional follow-ups (not done by `graduate.sh`):

- Add `controller` to `PERSONA_AUTO_CLOSE` env var only if a demo
  profile expects this persona to auto-close gates. Production-honest
  default: leave it off so a real human drives the gate.
- Add a regression test under
  `tests/api/server/personae/test_authority_parity.py` parameterised
  on `controller` to keep parity with the other authority-MCP-using
  personae.
