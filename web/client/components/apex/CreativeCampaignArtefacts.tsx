// web/client/components/apex/CreativeCampaignArtefacts.tsx
//
// POC3 Phase 5 — renders the brief scorecard, 3 concept tiles, and
// storyboard strip for a creative-campaign workflow.
//
// Derives AG-UI component specs from `workflow.payload`. Mounted inside
// WorkflowDetail.tsx when workflow.type === "creative-campaign".
//
// One important UX choice: the "Lock route" button on each concept tile
// raises the `concept_lock_decision` external event directly via
// /internal/durable-event, advancing the workflow to Phase 7 (storyboard
// render) without going through the persona auto-close. That's the
// storyboard's ◆2 beat live in the operator surface.

import { useCallback } from "react";
import type { Workflow } from "@shared/types";
import AgentDrivenComponent, { type AgentComponentSpec } from "../AgentDrivenComponent";

type CreativeBriefJson = {
  id?: string;
  client_brand?: string;
  category?: string;
  audience?: string;
  mandatory_messages?: string[];
  channels?: string[];
  kpis?: Record<string, string>;
  jurisdictions?: string[];
  constraints?: string[];
};

type CreativeRoute = {
  route_name: string;
  headline?: string;
  description?: string;
  stills: string[];
  brand_fit: number;
  distinctiveness: number;
};

type CreativePayload = {
  brief?: CreativeBriefJson;
  brief_synthesis?: { brief_json?: CreativeBriefJson; phase?: string };
  concept_fanout?: { routes?: CreativeRoute[]; phase?: string };
  storyboard_render?: { frames?: string[]; frame_captions?: string[]; phase?: string };
  package_handoff?: { figma_file_url?: string; deliverables?: string[]; phase?: string };
  concept_lock_decision?: { decision?: string; locked_route?: string };
};

export default function CreativeCampaignArtefacts({ workflow, onChange }: {
  workflow: Workflow;
  onChange: () => void;
}) {
  const payload = (workflow.payload ?? {}) as unknown as CreativePayload;
  const brief = payload.brief_synthesis?.brief_json ?? payload.brief;
  const fanout = payload.concept_fanout;
  const storyboard = payload.storyboard_render;
  const handoff = payload.package_handoff;
  const lockedRoute = payload.concept_lock_decision?.locked_route;

  const lockRoute = useCallback(async (routeName: string) => {
    // Raise the concept_lock_decision external event with locked_route
    // so the orchestrator advances. Go via /internal/durable-event so the
    // event bus + persona responder both see it consistently.
    await fetch("/internal/durable-event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workflow_id: workflow.id,
        kind: "concept_lock_decision",
        payload: {
          decision: "approve",
          locked_route: routeName,
          reason: `operator-locked ${routeName} via Control Plane`,
        },
      }),
    }).catch(() => {});
    onChange();
  }, [workflow.id, onChange]);

  const specs: AgentComponentSpec[] = [];

  if (brief && brief.audience && brief.mandatory_messages && brief.kpis) {
    specs.push({
      kind: "brief_scorecard",
      title: "Creative brief",
      client_brand: brief.client_brand ?? "—",
      category: brief.category ?? "—",
      audience: brief.audience,
      mandatory_messages: brief.mandatory_messages,
      channels: brief.channels ?? [],
      kpis: brief.kpis,
      jurisdictions: brief.jurisdictions,
      constraints: brief.constraints,
    });
  }

  if (fanout?.routes && fanout.routes.length > 0) {
    specs.push({
      kind: "concept_tiles",
      title: "Concept routes",
      routes: fanout.routes,
      // Show the Lock button only when the gate is still open (no locked route yet).
      onLockRoute: lockedRoute ? undefined : lockRoute,
      lockedRoute,
    });
  }

  if (storyboard?.frames && storyboard.frames.length > 0) {
    specs.push({
      kind: "storyboard_strip",
      title: "Storyboard",
      frames: storyboard.frames,
      frame_captions: storyboard.frame_captions,
    });
  }

  if (specs.length === 0) {
    return (
      <div className="panel panel-body text-sm text-slate-500" data-testid="creative-empty">
        No creative artefacts yet — workflow is still in the brief intake phase.
      </div>
    );
  }

  return (
    <section data-testid="creative-campaign-artefacts" className="space-y-3">
      {specs.map((spec, i) => (
        <AgentDrivenComponent key={`${spec.kind}-${i}`} spec={spec} />
      ))}
      {handoff?.figma_file_url && (
        <div className="panel">
          <div className="panel-header">Handoff</div>
          <div className="panel-body text-sm text-slate-700 flex items-center justify-between">
            <span>Asset bundle pushed to Figma — designer takes it from here.</span>
            <a
              href={handoff.figma_file_url}
              target="_blank"
              rel="noreferrer"
              data-testid="creative-figma-link"
              className="text-blue-700 hover:underline text-xs font-medium"
            >
              Open in Figma →
            </a>
          </div>
        </div>
      )}
    </section>
  );
}
