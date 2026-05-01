type TranscriptTurn = { role: string; text: string; ts: number };

export default function TranscriptList({ turns }: { turns: readonly TranscriptTurn[] }) {
  return (
    <>
      {turns.map((t, i) => (
        <div key={i} className="transcript-line">
          <span className={t.role === "agent" ? "transcript-role-agent" : "transcript-role-candidate"}>
            {t.role === "agent" ? "Agent" : "You"}
          </span>
          <span className="text-slate-800">{t.text}</span>
        </div>
      ))}
    </>
  );
}
