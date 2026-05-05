/**
 * Build a substrate map: for every skill, MCP tool, and validator we know
 * about, claim one dot on the sunflower sphere by index. The remaining dots
 * stay as background "case of type" filler that twinkles at low intensity.
 *
 * Name aliasing matters here. The composition tree uses one form, the live
 * SSE event stream uses another:
 *   - skills: composition emits kebab ("audit-summariser"); events emit
 *             both kebab and snake ("audit_summariser"). We register both.
 *   - tools:  composition lists MCP names ("identity_provider") with their
 *             operations; events emit "<mcp>_<operation>" joined
 *             ("identity_provider_list_role_templates"). We register the
 *             joined form for every operation declared on the MCP, plus
 *             the bare MCP name as a fallback.
 *
 * Without these aliases, every pulse misses and the substrate looks dead.
 */

import type { CompositionTree } from "../types";
import type { SubstrateMap } from "./types";

function snakeOf(name: string): string {
  return name.replace(/-/g, "_");
}

export function buildSubstrateMap(
  composition: CompositionTree | null,
  totalDots = 2400,
): SubstrateMap {
  const skillIdx = new Map<string, number>();
  const toolIdx = new Map<string, number>();
  const validatorIdx = new Map<string, number>();
  const category = new Uint8Array(totalDots);

  if (!composition) {
    return { total: totalDots, skillIdx, toolIdx, validatorIdx, category };
  }

  const skills = [...composition.skills]
    .map((s) => s.name)
    .sort((a, b) => a.localeCompare(b));
  const mcps = [...composition.mcps].sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  // Validator names mirror the agent skill names with a "validate_" prefix
  // (snake_case is what the SSE stream emits, e.g. validate_classification_schema).
  const validators = skills.map((s) => `validate_${snakeOf(s)}`);

  let cursor = 0;

  // Skills: claim a dot for the kebab name, alias the snake form to it too.
  for (const name of skills) {
    if (cursor >= totalDots) break;
    skillIdx.set(name, cursor);
    skillIdx.set(snakeOf(name), cursor);
    category[cursor] = 1;
    cursor++;
  }

  // Tools: each (mcp, operation) pair gets its own dot keyed under
  //   "<mcp>_<operation>"
  // and the bare MCP name aliases to its first operation's dot as a fallback.
  for (const mcp of mcps) {
    if (cursor >= totalDots) break;
    const ops = mcp.operations ?? [];
    if (ops.length === 0) {
      // No operations declared — give the MCP itself one dot.
      toolIdx.set(mcp.name, cursor);
      category[cursor] = 2;
      cursor++;
      continue;
    }
    let firstDot = -1;
    for (const op of ops) {
      if (cursor >= totalDots) break;
      const joined = `${mcp.name}_${op}`;
      toolIdx.set(joined, cursor);
      if (firstDot < 0) firstDot = cursor;
      category[cursor] = 2;
      cursor++;
    }
    if (firstDot >= 0 && !toolIdx.has(mcp.name)) {
      toolIdx.set(mcp.name, firstDot);
    }
  }

  // Validators: one dot each, registered under the snake name the events emit.
  for (const name of validators) {
    if (cursor >= totalDots) break;
    validatorIdx.set(name, cursor);
    category[cursor] = 3;
    cursor++;
  }

  return { total: totalDots, skillIdx, toolIdx, validatorIdx, category };
}
