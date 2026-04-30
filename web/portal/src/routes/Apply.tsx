import { useState, FormEvent } from "react";

const ROLE_OPTIONS = [
  { id: "REQ-SDE-USA-DEMO", label: "Senior Data Engineer — USA" },
  { id: "REQ-SDE-DE-DEMO", label: "Senior Data Engineer — Germany" },
  { id: "REQ-CD-USA-DEMO", label: "Creative Director — USA" },
];

type Confirmation = { candidate_id: string };

export default function Apply() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);

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
      <div className="max-w-xl mx-auto p-8">
        <div className="panel">
          <div className="panel-header">Application submitted</div>
          <div className="panel-body space-y-2">
            <p className="text-sm text-slate-700">
              Your application has been <strong>submitted</strong>.
            </p>
            <p className="text-sm text-slate-500">
              Candidate ID: <code>{confirmation.candidate_id}</code>
            </p>
            <p className="text-sm text-slate-500">
              We will email you a personal portal link once the recruiter team has reviewed your CV.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto p-8">
      <div className="panel">
        <div className="panel-header">Apply for a role</div>
        <form onSubmit={onSubmit} className="panel-body space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Role</span>
            <select
              name="role_id"
              required
              defaultValue=""
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="" disabled>Select a role…</option>
              {ROLE_OPTIONS.map((r) => (
                <option key={r.id} value={r.id}>{r.label}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Name</span>
            <input
              type="text"
              name="name"
              required
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              name="email"
              required
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">CV (PDF)</span>
            <input
              type="file"
              name="cv"
              accept="application/pdf"
              required
              className="mt-1 block w-full text-sm"
            />
          </label>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "Submitting…" : "Apply"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
