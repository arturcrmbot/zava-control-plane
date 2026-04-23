// src/client/App.tsx
import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import FleetDashboard from "./routes/FleetDashboard";
import ExceptionQueue from "./routes/ExceptionQueue";
import PolicyAndAutonomy from "./routes/PolicyAndAutonomy";
import Analytics from "./routes/Analytics";
import Evaluations from "./routes/Evaluations";
import WorkflowDetail from "./routes/WorkflowDetail";
import FleetManagerRail from "./components/FleetManagerRail";

const nav = [
  { to: "/fleet",       label: "Dashboard" },
  { to: "/exceptions",  label: "Exceptions" },
  { to: "/policy",      label: "Policy" },
  { to: "/analytics",   label: "Analytics" },
  { to: "/evals",       label: "Evaluations" },
  { to: "/agents",      label: "Agents" },
  { to: "/library",     label: "Library" },
  { to: "/economics",   label: "Economics" },
];

function Stub({ title }: { title: string }) {
  return <div className="panel panel-body text-sm text-slate-600">{title} — coming soon.</div>;
}

export default function App() {
  return (
    <>
      <header className="flex items-center gap-6 px-6 h-12 border-b border-slate-200 bg-white">
        <div className="font-semibold text-slate-900">Project Apex</div>
        <span className="text-slate-300">·</span>
        <div className="text-sm text-slate-500">Control Plane</div>
        <div className="ml-auto text-xs text-slate-500">role: Finance Controller</div>
      </header>

      <div className="grid grid-cols-[220px_1fr_360px] h-[calc(100vh-3rem)]">
        <aside className="bg-white border-r border-slate-200 p-3 space-y-1">
          {nav.map(n => (
            <NavLink key={n.to} to={n.to}
                     className={({ isActive }) => `block text-sm px-3 py-1.5 rounded outline-none focus-visible:ring-2 focus-visible:ring-blue-300 ${isActive ?
                       "bg-blue-50 text-blue-700 font-medium" : "text-slate-700 hover:bg-slate-100"}`}>
              {n.label}
            </NavLink>
          ))}
        </aside>

        <main className="p-6 overflow-auto">
          <Routes>
            <Route path="/" element={<Navigate to="/fleet" replace />} />
            <Route path="/fleet" element={<FleetDashboard />} />
            <Route path="/workflows/:id" element={<WorkflowDetail />} />
            <Route path="/exceptions" element={<ExceptionQueue />} />
            <Route path="/policy" element={<PolicyAndAutonomy />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/evals" element={<Evaluations />} />
            <Route path="/agents" element={<Stub title="Agents" />} />
            <Route path="/library" element={<Stub title="Library" />} />
            <Route path="/economics" element={<Stub title="Economics" />} />
          </Routes>
        </main>

        <aside className="border-l border-slate-200 bg-white overflow-auto">
          <FleetManagerRail />
        </aside>
      </div>
    </>
  );
}
