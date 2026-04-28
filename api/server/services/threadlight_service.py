"""Threadlight — long-lived SME-interview accelerator (§4.14).

A second long-lived GHCP session running alongside Fleet Manager. It conducts
a guided Q&A with a domain SME (e.g. a senior recruiter who knows the
agency-Y voice for creative roles) and emits a `SKILL.md` to disk that the
runtime loads on the next ephemeral session.

Compared to Fleet Manager:
  - FleetManagerService listens on the event bus and reasons over fleet state.
  - ThreadlightService runs on a dedicated chat surface (the Threadlight UI
    route) and grows a single SKILL.md document iteratively.

For the spine this is a state machine over a chat transcript; per-track work
in Track E swaps in the real GHCP session and live SKILL.md emission.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SKILLS_DIR = Path(__file__).resolve().parents[2] / "server" / "skills"


@dataclass
class ThreadlightTurn:
    role: Literal["agent", "sme"]
    text: str
    skill_md_snapshot: str | None = None


@dataclass
class ThreadlightSession:
    session_id: str
    skill_target_name: str
    transcript: list[ThreadlightTurn] = field(default_factory=list)
    skill_md_draft: str = ""
    finalised: bool = False


class ThreadlightService:
    """Holds the in-flight SME interview state. One instance per process,
    started at FastAPI app startup alongside FleetManagerService."""

    def __init__(self) -> None:
        self._sessions: dict[str, ThreadlightSession] = {}
        self._lock = asyncio.Lock()

    async def start_session(self, *, skill_target_name: str) -> ThreadlightSession:
        async with self._lock:
            sid = f"TL-{len(self._sessions) + 1:04d}"
            session = ThreadlightSession(
                session_id=sid,
                skill_target_name=skill_target_name,
            )
            session.transcript.append(ThreadlightTurn(
                role="agent",
                text=(
                    f"Hi! I'm Threadlight. I'll grow a SKILL.md for `{skill_target_name}` "
                    f"by asking you a sequence of questions. We'll start with the role: "
                    f"in one paragraph, when does this skill fire, and what does success look like?"
                ),
            ))
            self._sessions[sid] = session
            return session

    async def append_sme_turn(self, session_id: str, text: str) -> ThreadlightSession:
        async with self._lock:
            session = self._sessions[session_id]
            session.transcript.append(ThreadlightTurn(role="sme", text=text))
            agent_reply = self._next_agent_question(session)
            snapshot = self._render_skill_md(session)
            session.skill_md_draft = snapshot
            session.transcript.append(ThreadlightTurn(
                role="agent", text=agent_reply, skill_md_snapshot=snapshot,
            ))
            return session

    async def finalise(self, session_id: str) -> Path:
        async with self._lock:
            session = self._sessions[session_id]
            target_dir = SKILLS_DIR / session.skill_target_name
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / "SKILL.md"
            target_path.write_text(session.skill_md_draft, encoding="utf-8")
            session.finalised = True
            return target_path

    # Stub Q&A flow — Track E2 replaces with the real GHCP-driven loop.
    def _next_agent_question(self, session: ThreadlightSession) -> str:
        n_sme_turns = sum(1 for t in session.transcript if t.role == "sme")
        catalogue = [
            "What inputs does this skill receive at runtime?",
            "What's the canonical step-by-step procedure?",
            "What's the JSON shape of the output you want the model to return?",
            "What are the most common mistakes you see people make on this task?",
            "Walk me through one fully-worked example, end-to-end.",
        ]
        if n_sme_turns - 1 < len(catalogue):
            return catalogue[n_sme_turns - 1]
        return "Looks complete. Say `finalise` to emit the SKILL.md, or keep going if there's more."

    def _render_skill_md(self, session: ThreadlightSession) -> str:
        sme_turns = [t for t in session.transcript if t.role == "sme"]
        body = "\n\n".join(f"- {t.text}" for t in sme_turns)
        return (
            f"---\n"
            f"name: {session.skill_target_name}\n"
            f"description: SME-authored skill (Threadlight session {session.session_id}).\n"
            f"---\n\n"
            f"You are the {session.skill_target_name} agent.\n\n"
            f"## Captured guidance from SME interview\n\n"
            f"{body}\n"
        )

    def get_session(self, session_id: str) -> ThreadlightSession | None:
        return self._sessions.get(session_id)


# Process-global singleton; main.py wires this up at app startup.
threadlight = ThreadlightService()
