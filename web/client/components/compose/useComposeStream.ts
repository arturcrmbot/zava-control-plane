import { useEffect, useReducer, useRef } from "react";
import { composeReducer, initialState, type ComposeEvent, type CockpitState } from "./reducer";
import { postAnswer, postBrief, postIgnite } from "./api";

export function useComposeStream(cid: string | null) {
  const [state, dispatch] = useReducer(composeReducer, undefined, initialState);
  const esRef = useRef<EventSource | null>(null);
  const stateRef = useRef<CockpitState>(state);
  stateRef.current = state;

  useEffect(() => {
    if (!cid) return;
    const es = new EventSource(`/api/compose/${cid}/stream`);
    esRef.current = es;
    es.onmessage = (m) => {
      try { dispatch(JSON.parse(m.data) as ComposeEvent); } catch { /* ignore */ }
    };
    es.onerror = () => { es.close(); };
    return () => es.close();
  }, [cid]);

  return {
    state,
    async answer(request_id: string, value: string) {
      if (!cid) return;
      const q = stateRef.current.question;
      if (q?.request_id === request_id) dispatch({ type: "decision", question: q.text, answer: value });
      await postAnswer(cid, request_id, value);
      dispatch({ type: "question_cleared", request_id });
    },
    async approveBrief(request_id: string, approved: boolean, yaml: string) {
      if (!cid) return;
      await postBrief(cid, request_id, approved, yaml);
      dispatch({ type: "brief_cleared", request_id });
    },
    async ignite() {
      if (!cid) return;
      await postIgnite(cid);
    },
  };
}
