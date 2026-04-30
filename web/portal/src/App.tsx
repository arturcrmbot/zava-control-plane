import { Route, Routes, Navigate, Link } from "react-router-dom";

function Placeholder({ label }: { label: string }) {
  return (
    <div className="max-w-xl mx-auto p-8">
      <div className="panel">
        <div className="panel-header">{label}</div>
        <div className="panel-body text-sm text-slate-500">
          Route under construction.
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <div className="min-h-full flex flex-col">
      <header className="flex items-center gap-4 px-6 h-14 border-b border-slate-200 bg-white">
        <Link to="/apply" className="font-semibold text-slate-900">Candidate Portal</Link>
        <span className="text-slate-300">·</span>
        <div className="text-sm text-slate-500">Apply, track, onboard</div>
      </header>
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/apply" replace />} />
          <Route path="/apply" element={<Placeholder label="/apply" />} />
          <Route path="/portal" element={<Placeholder label="/portal" />} />
          <Route path="/screen" element={<Placeholder label="/screen" />} />
        </Routes>
      </main>
    </div>
  );
}
