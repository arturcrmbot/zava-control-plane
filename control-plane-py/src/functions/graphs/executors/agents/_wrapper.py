# src/functions/graphs/executors/agents/_wrapper.py
"""
Helper for invoking a finance-agent skill via GitHubCopilotAgent.

Pattern: each agent executor function calls run_agent_skill(skill_name, prompt) which:
1. Loads the named SKILL.md as the agent instructions
2. Constructs a fresh GitHubCopilotAgent (ephemeral per invocation)
3. Runs the agent on the prompt
4. Parses the first JSON object from the response text
5. Returns the parsed dict (or {"raw": text, "parse_error": True} on failure)

The agent is named "finance-agent" universally — single agent identity across all 9 skills,
matching the spec's "specialisation via skills, not via separate agents" pattern.
"""
from __future__ import annotations
import json
from pathlib import Path
from agent_framework_github_copilot import GitHubCopilotAgent


_SKILLS_DIR = Path(__file__).resolve().parents[4] / "server" / "skills"


def _load_skill(name: str) -> str:
    return (_SKILLS_DIR / f"{name}.skill.md").read_text(encoding="utf-8")


async def run_agent_skill(skill_name: str, prompt: str, model: str = "gpt-4.1") -> dict:
    """Run a finance-agent ephemeral session loading the named skill, return parsed JSON output."""
    skill_text = _load_skill(skill_name)
    # model is passed via default_options; GitHubCopilotAgent has no direct model kwarg
    agent = GitHubCopilotAgent(
        skill_text,
        name="finance-agent",
        default_options={"model": model},
    )
    response = await agent.run(prompt)
    text = getattr(response, "text", None) or str(response)

    # Extract the first JSON object/array from the response text
    # Try object first, then array
    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    # Pick the earlier valid JSON
    if obj_start >= 0 and obj_end > obj_start:
        try:
            return json.loads(text[obj_start:obj_end + 1])
        except json.JSONDecodeError:
            pass
    if arr_start >= 0 and arr_end > arr_start:
        try:
            result = json.loads(text[arr_start:arr_end + 1])
            return {"items": result} if isinstance(result, list) else result
        except json.JSONDecodeError:
            pass
    return {"raw": text, "parse_error": True}
