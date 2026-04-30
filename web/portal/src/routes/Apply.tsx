import { useState, FormEvent } from "react";

const ROLE_OPTIONS = [
  { id: "REQ-SDE-USA-DEMO", label: "Senior Data Engineer", market: "USA", flag: "🇺🇸" },
  { id: "REQ-SDE-DE-DEMO",  label: "Senior Data Engineer", market: "Germany", flag: "🇩🇪" },
  { id: "REQ-CD-USA-DEMO",  label: "Creative Director",    market: "USA", flag: "🇺🇸" },
];

type Confirmation = { candidate_id: string; workflow_id: string };

export default function Apply() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [selectedRole, setSelectedRole] = useState<string>("");
  const [filename, setFilename] = useState<string>("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const fd = new FormData(e.currentTarget);
    try {
      const resp = await fetch("/api/portal/apply", { method: "POST", body: fd });
      if (resp.status !== 202) {
        const text = await resp.text();
        setError(`Apply failed (${resp.status}): ${text}`);
        return;
      }
      const body = (await resp.json()) as Confirmation;
      setConfirmation(body);
    } catch (err) {
      setError(`Network error: ${(err as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  }

  if (confirmation) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10 space-y-6">
        <div className="hero">
          <div className="hero-eyebrow">Application received</div>
          <h1 className="hero-title">Thanks — we've got your CV.</h1>
          <p className="hero-subtitle">
            We'll review your application and email you a personal portal
            link as soon as you're shortlisted. Average review time is under
            an hour.
          </p>
        </div>
        <div className="panel">
          <div className="panel-header">What happens next</div>
          <div className="panel-body space-y-4 text-sm text-slate-700">
            <Step n={1} title="CV review">
              Our agent extracts your structured profile and matches it to
              the role's success criteria.
            </Step>
            <Step n={2} title="Voice screening (60 seconds)">
              You'll receive a link to a 4-question call with our screening
              agent. Take it whenever it suits you.
            </Step>
            <Step n={3} title="Interview & offer">
              The hiring manager reviews your transcript, schedules an
              interview, and the offer arrives via the portal.
            </Step>
            <Step n={4} title="Onboarding">
              Day 1 starts with a personalised welcome video and your
              ServiceNow tickets pre-provisioned.
            </Step>
            <div className="border-t border-slate-100 pt-4 text-xs text-slate-500">
              Reference: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{confirmation.candidate_id}</code> ·
              Workflow: <code className="bg-slate-100 px-1.5 py-0.5 rounded">{confirmation.workflow_id}</code>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 sm:p-10 space-y-6">
      <div className="hero">
        <div className="hero-eyebrow">Apply for a role</div>
        <h1 className="hero-title">Build the future with us.</h1>
        <p className="hero-subtitle">
          One form. Smart screening. Zero recruiter back-and-forth. We'll get
          you to a hiring decision in days, not weeks.
        </p>
      </div>

      <form onSubmit={onSubmit} className="panel">
        <div className="panel-header">Your application</div>
        <div className="panel-body space-y-5">
          <fieldset className="space-y-2">
            <legend className="form-label">Role</legend>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {ROLE_OPTIONS.map((r) => (
                <label
                  key={r.id}
                  className={
                    "cursor-pointer rounded-lg border p-3 text-sm transition " +
                    (selectedRole === r.id
                      ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100"
                      : "border-slate-200 hover:border-slate-300 bg-white")
                  }
                >
                  <input
                    type="radio"
                    name="role_id"
                    value={r.id}
                    required
                    className="sr-only"
                    onChange={(e) => setSelectedRole(e.target.value)}
                  />
                  <div className="flex items-center gap-1 text-xs text-slate-500">
                    <span>{r.flag}</span><span>{r.market}</span>
                  </div>
                  <div className="mt-1 font-medium text-slate-800">{r.label}</div>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className="form-label">Full name</span>
              <input type="text" name="name" required className="form-input" placeholder="Alex Doe"/>
            </label>
            <label className="block">
              <span className="form-label">Email</span>
              <input type="email" name="email" required className="form-input" placeholder="alex@example.com"/>
            </label>
          </div>

          <label className="block">
            <span className="form-label">CV (PDF)</span>
            <input
              type="file"
              name="cv"
              accept="application/pdf"
              required
              className="form-file"
              onChange={(e) => setFilename(e.target.files?.[0]?.name ?? "")}
            />
            {filename && (
              <p className="form-help">Selected: <code>{filename}</code></p>
            )}
            {!filename && (
              <p className="form-help">PDF only, max 10 MB. Your CV stays private to the hiring team.</p>
            )}
          </label>

          {error && (
            <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <p className="text-xs text-slate-500">
              By applying you agree to our processing of your CV per the GDPR/UK-DPA notice on this page.
            </p>
            <button type="submit" className="btn-primary btn-large" disabled={submitting}>
              {submitting ? <><span className="spinner"/> Submitting…</> : "Submit application →"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="phase-bubble phase-bubble-done shrink-0">{n}</div>
      <div>
        <div className="text-sm font-semibold text-slate-800">{title}</div>
        <p className="text-sm text-slate-600">{children}</p>
      </div>
    </div>
  );
}
