import { StudioView } from "./StudioCockpit";
import type { CockpitState } from "../reducer";
import type { Composition, VisualStage } from "./types";
import sample from "./sampleComposition.json";

const DOC = `Staff request funding for capital assets. First we check the cost-centre budget. An analyst reviews policy and sets a risk level. The approver signs off — but anything above £50,000 needs an additional senior sign-off. Finally the asset is registered.`;

const STAGE_TO_AGENT: Record<VisualStage, string> = {
  read: "understanding",
  design: "brief",
  build: "composing",
  ready: "ready",
};

// Deterministic fake state per visual stage, for screenshots + manual QA.
// Route: /compose?preview=1&stage=build  (add &theme=dark handled by the app).
export function buildPreviewState(stage: VisualStage): CockpitState {
  const composition = stage === "read" ? undefined : (sample as Composition);
  const decisions =
    stage === "build" || stage === "ready"
      ? [{ question: "Who signs off above £50,000?", answer: "Escalate to the CFO" }]
      : [];
  const STAGE_LABEL: Record<VisualStage, string> = {
    read: "Reading the document",
    design: "Drafting the brief",
    build: "Composing the domain",
    ready: "Run complete",
  };
  return {
    stage: stage === "ready" ? "ready" : STAGE_TO_AGENT[stage],
    stageLabel: STAGE_LABEL[stage],
    thoughts: "",
    narration: "",
    tools: [],
    plan: [],
    decisions,
    composition,
    done: undefined,
  };
}

const SAMPLE_YAML = `domain:
  workflow_type: capex-approval
  display_name: Capital expenditure approval
phases:
  - name: capex_intake
    kind: deterministic
  - name: capex_approval
    kind: hitl
    persona: capex_finance_controller
# … full spec truncated for preview …`;

export function StudioPreview() {
  const params = new URLSearchParams(window.location.search);
  const stage = (params.get("stage") as VisualStage) || "build";
  const overlay = params.get("overlay");
  const state = { ...buildPreviewState(stage) };
  if (overlay === "question") {
    state.question = {
      request_id: "q",
      text:
        "Your document names “an approver” for sign-off and a separate senior sign-off above £50,000, but doesn’t say which finance role. Who should own the approval, with the CFO handling anything above £50,000?",
      options: [
        "A dedicated Finance Approver, with the CFO signing off anything above £50,000",
        "Finance Business Partner approves, CFO above £50,000",
        "Finance Controller approves, CFO above £50,000",
      ],
    };
  }
  if (overlay === "brief") state.brief = { request_id: "b", yaml: SAMPLE_YAML };
  if (overlay === "ignite") state.done = { workflow_type: "capex-approval", display_name: "Capital expenditure approval" };
  const source = params.get("nosrc") ? null : DOC;
  return (
    <StudioView
      state={state}
      source={source}
      onAnswer={() => {}}
      onApproveBrief={() => {}}
      onIgnite={() => {}}
    />
  );
}
