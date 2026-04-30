import { Route, Routes, Navigate, Link } from "react-router-dom";
import Apply from "./routes/Apply";
import Portal from "./routes/Portal";
import Screen from "./routes/Screen";

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
          <Route path="/apply" element={<Apply />} />
          <Route path="/portal" element={<Portal />} />
          <Route path="/screen" element={<Screen />} />
        </Routes>
      </main>
    </div>
  );
}
