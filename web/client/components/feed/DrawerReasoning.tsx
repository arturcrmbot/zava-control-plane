// web/client/components/feed/DrawerReasoning.tsx
//
// AG-UI live reasoning section inside the workflow drawer. Connects to the
// per-workflow SSE stream at /api/workflows/{id}/agui and renders agent
// reasoning, tool calls, state deltas, and HITL interrupts in real time.
import { useEffect, useReducer } from "react";
import type { DrawerData } from "./Drawer";
import { replaceOrAppendById } from "@shared/replaceOrAppendById";

// ── Inline reducer (same logic as blueprint's runReducer) ───────────

interface MessageView { id: string; role: string; text: string; closed: boolean }
interface ToolCallView { id: string; name: string; args: string; closed: boolean }
interface RunState {
  messages: MessageView[];
  toolCalls: ToolCallView[];
  state: Record<string, any>;
  interrupt: { reason: string; persona?: string } | null;
  finished: boolean;
  error: string | null;
  customEvents: { name: string; value: any }[];
  connected: boolean;
}

function initialState(): RunState {
  return { messages: [], toolCalls: [], state: {}, interrupt: null, finished: false, error: null, customEvents: [], connected: false };
}

function applyJsonPatch(doc: Record<string, any>, ops: { op: string; path: string; value?: any }[]): Record<string, any> {
  const next = structuredClone(doc);
  for (const op of ops) {
    const segs = op.path.split("/").filter(Boolean);
    if ((op.op === "add" || op.op === "replace") && segs.length > 0) {
      let cur: any = next;
      for (let i = 0; i < segs.length - 1; i++) {
        if (cur[segs[i]] == null) cur[segs[i]] = {};
        cur = cur[segs[i]];
      }
      cur[segs[segs.length - 1]] = op.value;
    }
  }
  return next;
}

type Ev = { type: string; [k: string]: any };

function reducer(s: RunState, ev: Ev): RunState {
  switch (ev.type) {
    case "__CONNECTED":     return { ...s, connected: true };
    case "__DISCONNECTED":  return { ...s, connected: false };
    case "RUN_STARTED":     return { ...s, finished: false, error: null };
    case "RUN_FINISHED":    return { ...s, finished: true };
    case "RUN_ERROR":       return { ...s, finished: true, error: ev.message ?? "error" };
    case "RUN_INTERRUPTED": return { ...s, interrupt: { reason: ev.reason, persona: ev.persona } };
    case "TEXT_MESSAGE_START":
      return { ...s, messages: replaceOrAppendById(s.messages, { id: ev.messageId, role: ev.role ?? "assistant", text: "", closed: false }) };
    case "TEXT_MESSAGE_CONTENT":
      return { ...s, messages: s.messages.map(m => m.id === ev.messageId ? { ...m, text: m.text + ev.delta } : m) };
    case "TEXT_MESSAGE_END":
      return { ...s, messages: s.messages.map(m => m.id === ev.messageId ? { ...m, closed: true } : m) };
    case "TOOL_CALL_START":
      return { ...s, toolCalls: replaceOrAppendById(s.toolCalls, { id: ev.toolCallId, name: ev.toolCallName, args: "", closed: false }) };
    case "TOOL_CALL_ARGS":
      return { ...s, toolCalls: s.toolCalls.map(t => t.id === ev.toolCallId ? { ...t, args: t.args + ev.delta } : t) };
    case "TOOL_CALL_END":
      return { ...s, toolCalls: s.toolCalls.map(t => t.id === ev.toolCallId ? { ...t, closed: true } : t) };
    case "STATE_DELTA":
      return { ...s, state: applyJsonPatch(s.state, ev.delta ?? []) };
    case "CUSTOM":
      return { ...s, customEvents: [...s.customEvents, { name: ev.name, value: ev.value }] };
    default: return s;
  }
}

// ── Component ───────────────────────────────────────────────────────

// Module-level cache: survives drawer close/reopen within the same
// browser session. Keyed by workflow_id.
const _stateCache = new Map<string, RunState>();

export default function DrawerReasoning({ data }: { data: DrawerData }) {
  const wfId = data.workflow.id;
  const [s, dispatch] = useReducer(reducer, undefined, () =>
    _stateCache.get(wfId) ?? initialState());

  // Persist reducer state to cache on every update.
  useEffect(() => { _stateCache.set(wfId, s); }, [wfId, s]);

  useEffect(() => {
    const es = new EventSource(`/api/workflows/${wfId}/agui`);
    es.onopen = () => dispatch({ type: "__CONNECTED" });
    es.onmessage = (msg) => {
      try { dispatch(JSON.parse(msg.data)); } catch { /* skip */ }
    };
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) dispatch({ type: "__DISCONNECTED" });
    };
    return () => es.close();
  }, [wfId]);

  const hasContent = s.messages.length > 0 || s.toolCalls.length > 0 || Object.keys(s.state).length > 0;

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <h2 className="text-[11px] uppercase tracking-wide font-semibold text-slate-500 dark:text-slate-400">
          Live reasoning
        </h2>
        <span className={`w-2 h-2 rounded-full ${s.connected ? "bg-green-500 animate-pulse" : "bg-slate-300 dark:bg-slate-600"}`}
              title={s.connected ? "SSE connected" : "Disconnected"} />
        {s.finished && (
          <span className="text-[10px] uppercase tracking-wide bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400 px-1.5 py-0.5 rounded">
            finished
          </span>
        )}
        {s.error && (
          <span className="text-[10px] uppercase tracking-wide bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400 px-1.5 py-0.5 rounded">
            error
          </span>
        )}
      </div>

      {s.interrupt && (
        <div className="rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-3 text-sm text-amber-800 dark:text-amber-300">
          ⏸ Awaiting <strong>{s.interrupt.persona ?? "human"}</strong>: {s.interrupt.reason}
        </div>
      )}

      {!hasContent && s.connected && (
        <p className="text-xs text-slate-400 dark:text-slate-500 italic">
          Listening for agent events…
        </p>
      )}

      {/* Agent messages */}
      {s.messages.length > 0 && (
        <div className="space-y-2">
          {s.messages.map((m) => (
            <div key={m.id} className="rounded-md bg-slate-50 dark:bg-slate-800/60 p-3 text-sm">
              <div className="text-[10px] uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
                {m.role}{!m.closed && <span className="ml-1 animate-pulse">●</span>}
              </div>
              <p className="text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
                {m.text || <span className="text-slate-400 italic">thinking…</span>}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Tool calls */}
      {s.toolCalls.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] uppercase tracking-wide text-slate-400 dark:text-slate-500 font-medium">Tools</div>
          {s.toolCalls.map((t) => (
            <div key={t.id} className="flex items-start gap-2 text-xs font-mono">
              <span className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${t.closed ? "bg-green-500" : "bg-blue-500 animate-pulse"}`} />
              <span className="text-blue-600 dark:text-blue-400 font-semibold">{t.name}</span>
              {t.args && (
                <code className="text-slate-500 dark:text-slate-400 break-all">{t.args}</code>
              )}
            </div>
          ))}
        </div>
      )}

      {/* State (entities + decisions) */}
      {Object.keys(s.state).length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-400 dark:text-slate-500 font-medium mb-1">State</div>
          <pre className="text-xs bg-slate-50 dark:bg-slate-800/60 rounded-md p-3 overflow-x-auto text-slate-600 dark:text-slate-300 max-h-48">
            {JSON.stringify(s.state, null, 2)}
          </pre>
        </div>
      )}
    </section>
  );
}
