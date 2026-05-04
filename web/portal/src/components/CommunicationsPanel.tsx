// Recruiter-side panel listing every email sent to the candidate, newest
// first. Each row expands to show the full HTML body in a sandboxed iframe
// so we can preview without trusting the markup.
import { useState } from "react";
import type { CandidateEmail } from "../lib/api";

export default function CommunicationsPanel({ emails }: { emails: CandidateEmail[] }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span>Communications</span>
        <span className="chip-info">{emails.length} sent</span>
      </div>
      <div className="panel-body">
        {emails.length === 0 ? (
          <p className="text-sm text-slate-500 italic">
            No emails sent to this candidate yet.
          </p>
        ) : (
          <ol className="space-y-2 text-sm">
            {emails.map((e) => (
              <EmailRow key={e.id} email={e} />
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

function EmailRow({ email }: { email: CandidateEmail }) {
  const [open, setOpen] = useState(false);
  const when = email.sent_at
    ? new Date(email.sent_at * 1000).toLocaleString()
    : "—";
  return (
    <li className="border border-slate-200 rounded-lg bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 px-3 py-2 text-left hover:bg-slate-50 rounded-lg"
      >
        <span className="text-slate-400 text-xs mt-0.5">{open ? "▼" : "▶"}</span>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-slate-800 truncate">{email.subject || "(no subject)"}</div>
          <div className="text-xs text-slate-500 truncate">
            to {email.to} · {when}
          </div>
        </div>
      </button>
      {open && (
        <div className="border-t border-slate-200 px-3 py-3 space-y-2">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">message body</div>
          <iframe
            title={`email-${email.id}`}
            sandbox=""
            className="w-full min-h-[180px] border border-slate-200 rounded bg-slate-50"
            srcDoc={email.html_body}
          />
        </div>
      )}
    </li>
  );
}
