import { useState } from "react";

/**
 * Section 3 — conceptual harness diagram.
 *
 * Replaces the previous data-driven inventory diagram. The composition
 * map below already shows every skill / MCP / domain. This component
 * shows the SHAPE of the harness — the four architectural pieces and
 * how they stack — without re-rendering the inventory.
 *
 * Hover any piece to see what it gives you in business terms.
 */

interface Piece {
  id: string;
  label: string;
  sub: string;
  caption: string;
  tone: "harness" | "skills" | "mcps" | "guarantees";
}

const PIECES: Piece[] = [
  {
    id: "harness",
    label: "Agent harness",
    sub: "spawn, run, tear down",
    tone: "harness",
    caption:
      "Agents are assembled when work arrives, do their job, and are torn down when done. There are no thousands of standing agents to manage. Orchestration, not an org chart.",
  },
  {
    id: "skills",
    label: "Skills",
    sub: "modular units of know-how",
    tone: "skills",
    caption:
      "A skill is a markdown file with a prompt, a tool allow-list, and a model choice. Adding one is not a project. Replacing one does not require a redeploy.",
  },
  {
    id: "mcps",
    label: "MCP tools",
    sub: "your systems, surfaced as tools",
    tone: "mcps",
    caption:
      "Workday, Concur, ServiceNow and the rest, exposed as MCP tools with negotiated auth and schemas. The MCP servers are pure capability. Agents borrow them; they never own them.",
  },
  {
    id: "guarantees",
    label: "Always-on guarantees",
    sub: "identity · validation · audit · policy",
    tone: "guarantees",
    caption:
      "Every agent runs under its own Entra Agent ID. Every output passes a validator before it leaves. Every step writes itself to an immutable audit ledger. Policy lives in YAML — compliance edits the rules, no engineer required. Blessed once. Carried into every domain after.",
  },
];

export function HarnessDiagram() {
  const [hover, setHover] = useState<string | null>(null);
  const active = PIECES.find((p) => p.id === hover);

  return (
    <div className="harness" onMouseLeave={() => setHover(null)}>
      <div className="harness__stack">
        {PIECES.map((p, i) => {
          const lit = hover === p.id;
          const dim = hover && hover !== p.id;
          const cls = [
            "harness__piece",
            `harness__piece--${p.tone}`,
            lit ? "harness__piece--lit" : "",
            dim ? "harness__piece--dim" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <div
              key={p.id}
              className={cls}
              onMouseEnter={() => setHover(p.id)}
              onFocus={() => setHover(p.id)}
              tabIndex={0}
            >
              <div className="harness__piece-num">0{i + 1}</div>
              <div className="harness__piece-body">
                <div className="harness__piece-label">{p.label}</div>
                <div className="harness__piece-sub">{p.sub}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className={`harness__caption${active ? " harness__caption--active" : ""}`}>
        {active
          ? active.caption
          : "Hover any piece to see what it actually gives you. The four together is the entire harness — there is no fifth thing."}
      </div>
    </div>
  );
}
