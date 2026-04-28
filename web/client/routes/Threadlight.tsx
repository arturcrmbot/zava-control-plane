// web/client/routes/Threadlight.tsx — POC2 §4.14 SME-interview accelerator UI.
//
// Two-pane chat surface: left = SME ↔ Threadlight transcript; right rail =
// the SKILL.md being assembled live. Hitting "Finalise" emits the SKILL.md
// to disk; the next ephemeral session picks it up.
//
// Spine stub. Track E2 polishes interaction + adds keyboard shortcuts.
import { useState } from "react";

type Turn = { role: "agent" | "sme"; text: string; skill_md_snapshot?: string };

export default function Threadlight() {
  const [skillName, setSkillName] = useState("recruiter-creative-direction");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [skillMd, setSkillMd] = useState<string>("");
  const [pending, setPending] = useState("");

  async function start() {
    const r = await fetch("/api/threadlight/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill_target_name: skillName }),
    });
    const data = await r.json();
    setSessionId(data.session_id);
    setTranscript(data.transcript);
    setSkillMd(data.skill_md_draft);
  }

  async function send() {
    if (!sessionId || !pending.trim()) return;
    const r = await fetch(`/api/threadlight/sessions/${sessionId}/turn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: pending }),
    });
    const data = await r.json();
    setTranscript(data.transcript);
    setSkillMd(data.skill_md_draft);
    setPending("");
  }

  async function finalise() {
    if (!sessionId) return;
    const r = await fetch(`/api/threadlight/sessions/${sessionId}/finalise`, {
      method: "POST",
    });
    const data = await r.json();
    alert(`SKILL.md emitted to ${data.skill_path}`);
  }

  return (
    <div className="grid grid-cols-2 gap-4 h-[calc(100vh-200px)]">
      <div className="flex flex-col bg-white rounded-lg border border-slate-200">
        <div className="px-4 py-3 border-b border-slate-200">
          <div className="text-xs uppercase tracking-wide text-slate-500">Threadlight session</div>
          {!sessionId && (
            <div className="mt-2 flex gap-2">
              <input value={skillName} onChange={e => setSkillName(e.target.value)}
                className="flex-1 text-sm border border-slate-300 rounded px-2 py-1"
                placeholder="skill-target-name" />
              <button onClick={start} className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded">Start</button>
            </div>
          )}
          {sessionId && <div className="mt-1 text-xs text-slate-600">{sessionId} · target: <code>{skillName}</code></div>}
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {transcript.map((t, i) => (
            <div key={i} className={`text-sm rounded px-3 py-2 ${t.role === "agent" ? "bg-blue-50 text-blue-900" : "bg-slate-50 text-slate-800"}`}>
              <span className="text-[10px] uppercase tracking-wide opacity-60 mr-2">{t.role}</span>
              {t.text}
            </div>
          ))}
        </div>
        <div className="border-t border-slate-200 p-3 flex gap-2">
          <input value={pending} onChange={e => setPending(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") send(); }}
            className="flex-1 text-sm border border-slate-300 rounded px-2 py-1"
            placeholder="Reply…" disabled={!sessionId} />
          <button onClick={send} disabled={!sessionId} className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded disabled:opacity-50">Send</button>
          <button onClick={finalise} disabled={!sessionId} className="text-xs bg-emerald-600 text-white px-3 py-1.5 rounded disabled:opacity-50">Finalise</button>
        </div>
      </div>
      <div className="bg-white rounded-lg border border-slate-200 flex flex-col">
        <div className="px-4 py-3 border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">SKILL.md preview</div>
        <pre className="flex-1 overflow-y-auto p-4 text-[11px] font-mono whitespace-pre-wrap text-slate-800">{skillMd || "(empty — start a session to populate)"}</pre>
      </div>
    </div>
  );
}
