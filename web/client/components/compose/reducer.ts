export type ToolItem = {
  id: string;
  title?: string;
  kind?: "read" | "edit" | "execute" | "search" | "other";
  status?: "pending" | "running" | "completed" | "failed";
  path?: string;
  diff?: { old: string; new: string };
  output?: string;
};

import type { Composition } from "./studio/types";

export type Decision = { question: string; answer: string };

export type ComposeEvent =
  | { type: "stage"; stage: string; label?: string }
  | { type: "thought"; text: string; partial?: boolean }
  | { type: "narration"; text: string; partial?: boolean }
  | ({ type: "tool" } & Partial<ToolItem> & { id: string })
  | { type: "plan"; entries: { title: string; status: string }[] }
  | { type: "question"; request_id: string; text: string; options?: string[] }
  | { type: "question_cleared"; request_id: string }
  | { type: "decision"; question: string; answer: string }
  | { type: "brief"; request_id: string; yaml: string; parsed?: Composition | null }
  | { type: "brief_cleared"; request_id: string }
  | { type: "done"; workflow_type: string; display_name: string }
  | { type: "error"; message: string; fatal?: boolean };

export type CockpitState = {
  stage: string;
  stageLabel: string;
  thoughts: string;
  narration: string;
  tools: ToolItem[];
  plan: { title: string; status: string }[];
  question?: { request_id: string; text: string; options: string[] };
  brief?: { request_id: string; yaml: string };
  composition?: Composition; // retained across brief_cleared — drives the canvas
  decisions: Decision[];
  done?: { workflow_type: string; display_name: string };
  error?: string;
};

export function initialState(): CockpitState {
  return { stage: "intake", stageLabel: "", thoughts: "", narration: "", tools: [], plan: [], decisions: [] };
}

export function composeReducer(state: CockpitState, ev: ComposeEvent): CockpitState {
  switch (ev.type) {
    case "stage":
      return { ...state, stage: ev.stage, stageLabel: ev.label ?? state.stageLabel };
    case "thought":
      return { ...state, thoughts: state.thoughts + ev.text };
    case "narration":
      return { ...state, narration: ev.partial ? state.narration + ev.text : ev.text };
    case "tool": {
      const idx = state.tools.findIndex((t) => t.id === ev.id);
      const { type: _type, ...patch } = ev;
      if (idx === -1) return { ...state, tools: [...state.tools, patch as ToolItem] };
      const tools = state.tools.slice();
      tools[idx] = { ...tools[idx], ...patch };
      return { ...state, tools };
    }
    case "plan":
      return { ...state, plan: ev.entries };
    case "question":
      return { ...state, question: { request_id: ev.request_id, text: ev.text, options: ev.options ?? [] } };
    case "question_cleared":
      return state.question?.request_id === ev.request_id ? { ...state, question: undefined } : state;
    case "decision":
      return { ...state, decisions: [...state.decisions, { question: ev.question, answer: ev.answer }] };
    case "brief":
      return {
        ...state,
        brief: { request_id: ev.request_id, yaml: ev.yaml },
        composition: ev.parsed ?? state.composition,
      };
    case "brief_cleared":
      return state.brief?.request_id === ev.request_id ? { ...state, brief: undefined } : state;
    case "done":
      return { ...state, done: { workflow_type: ev.workflow_type, display_name: ev.display_name } };
    case "error":
      return { ...state, error: ev.message };
    default:
      return state;
  }
}
