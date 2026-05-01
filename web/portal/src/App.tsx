import { Route, Routes, Navigate, NavLink, Link } from "react-router-dom";
import Apply from "./routes/Apply";
import Portal from "./routes/Portal";
import Screen from "./routes/Screen";
import Recruiter from "./routes/Recruiter";
import RecruiterCandidate from "./routes/RecruiterCandidate";

export default function App() {
  return (
    <div className="min-h-full flex flex-col">
      <header className="portal-header">
        <Link to="/apply" className="portal-brand">
          <span className="portal-brand-mark">CP</span>
          <span>Candidate Portal</span>
        </Link>
        <span className="text-slate-300 hidden sm:inline">·</span>
        <span className="portal-tagline">Apply, track, onboard</span>
        <nav className="ml-auto flex items-center gap-1">
          <NavLink to="/apply" className={({ isActive }) =>
            `portal-nav-link ${isActive ? "active" : ""}`}>Apply</NavLink>
          <NavLink to="/recruiter" className={({ isActive }) =>
            `portal-nav-link ${isActive ? "active" : ""}`}>Recruiter</NavLink>
        </nav>
      </header>
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/apply" replace />} />
          <Route path="/apply" element={<Apply />} />
          <Route path="/portal" element={<Portal />} />
          <Route path="/screen" element={<Screen />} />
          <Route path="/recruiter" element={<Recruiter />} />
          <Route path="/recruiter/c/:id" element={<RecruiterCandidate />} />
        </Routes>
      </main>
      <footer className="text-center text-xs text-slate-400 py-4 border-t border-slate-200 bg-white/60">
        Project Apex · Candidate Portal · Powered by Microsoft Azure
      </footer>
    </div>
  );
}
