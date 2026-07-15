import type { BaseEvent } from "@ag-ui/core";
import { replaceOrAppendById } from "@shared/replaceOrAppendById";

export interface MessageView {
  id: string;
  role: string;
  text: string;
  closed: boolean;
}

export interface ToolCallView {
  id: string;
  name: string;
  args: string;
  closed: boolean;
}

export interface RunState {
  messages: MessageView[];
  toolCalls: ToolCallView[];
  state: Record<string, any>;
  interrupt: { reason: string; persona?: string } | null;
  finished: boolean;
  error: string | null;
  customEvents: { name: string; value: any }[];
}

export function initialRunState(): RunState {
  return {
    messages: [],
    toolCalls: [],
    state: {},
    interrupt: null,
    finished: false,
    error: null,
    customEvents: [],
  };
}

function applyJsonPatch(
  doc: Record<string, any>,
  ops: { op: string; path: string; value?: any }[],
): Record<string, any> {
  const next = structuredClone(doc);
  for (const op of ops) {
    const segs = op.path.split("/").filter(Boolean);
    if (op.op === "add" || op.op === "replace") {
      let cur: any = next;
      for (let i = 0; i < segs.length - 1; i++) {
        const k = segs[i];
        if (cur[k] === undefined || cur[k] === null) cur[k] = {};
        cur = cur[k];
      }
      cur[segs[segs.length - 1]] = op.value;
    } else if (op.op === "remove") {
      let cur: any = next;
      for (let i = 0; i < segs.length - 1; i++) cur = cur?.[segs[i]];
      if (cur && segs.length > 0) delete cur[segs[segs.length - 1]];
    }
  }
  return next;
}

export function applyEvent(state: RunState, ev: BaseEvent & any): RunState {
  switch (ev.type) {
    case "RUN_STARTED":
      return { ...state, finished: false, error: null };
    case "RUN_FINISHED":
      return { ...state, finished: true };
    case "RUN_ERROR":
      return { ...state, finished: true, error: ev.message ?? "error" };
    case "RUN_INTERRUPTED":
      return {
        ...state,
        interrupt: { reason: ev.reason, persona: ev.persona },
      };
    case "TEXT_MESSAGE_START":
      return {
        ...state,
        messages: replaceOrAppendById(state.messages, {
          id: ev.messageId,
          role: ev.role ?? "assistant",
          text: "",
          closed: false,
        }),
      };
    case "TEXT_MESSAGE_CONTENT":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === ev.messageId ? { ...m, text: m.text + ev.delta } : m,
        ),
      };
    case "TEXT_MESSAGE_END":
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === ev.messageId ? { ...m, closed: true } : m,
        ),
      };
    case "TOOL_CALL_START":
      return {
        ...state,
        toolCalls: replaceOrAppendById(state.toolCalls, {
          id: ev.toolCallId,
          name: ev.toolCallName,
          args: "",
          closed: false,
        }),
      };
    case "TOOL_CALL_ARGS":
      return {
        ...state,
        toolCalls: state.toolCalls.map((t) =>
          t.id === ev.toolCallId ? { ...t, args: t.args + ev.delta } : t,
        ),
      };
    case "TOOL_CALL_END":
      return {
        ...state,
        toolCalls: state.toolCalls.map((t) =>
          t.id === ev.toolCallId ? { ...t, closed: true } : t,
        ),
      };
    case "STATE_DELTA":
      return { ...state, state: applyJsonPatch(state.state, ev.delta ?? []) };
    case "CUSTOM":
      return {
        ...state,
        customEvents: [...state.customEvents, { name: ev.name, value: ev.value }],
      };
    default:
      return state;
  }
}
