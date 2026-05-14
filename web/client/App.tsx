// src/client/App.tsx
import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import FleetDashboard from "./routes/FleetDashboard";
import ExceptionQueue from "./routes/ExceptionQueue";
import ReviewerQueue from "./routes/ReviewerQueue";
import PolicyAndAutonomy from "./routes/PolicyAndAutonomy";
import Analytics from "./routes/Analytics";
import Evaluations from "./routes/Evaluations";
import Economics from "./routes/Economics";
import WorkflowDetail from "./routes/WorkflowDetail";
import HiringManager from "./routes/HiringManager";
import FleetManagerRail from "./components/FleetManagerRail";

const nav = [
  { to: "/fleet",          label: "Dashboard" },
  { to: "/exceptions",     label: "Exceptions" },
  { to: "/reviewer-queue", label: "Reviewer queue" },
  { to: "/policy",         label: "Policy" },
  { to: "/analytics",      label: "Analytics" },
  { to: "/evals",          label: "Evaluations" },
  { to: "/economics",      label: "Economics" },
];

// Constellation lives in the separate blueprint app — opening it inside the
// dashboard's grid layout squashes it into a tiny middle column. Render it
// as a plain external link so it goes full-screen in its own tab.
// `?from=fleet` tells the constellation page to render a "← back to fleet"
// link that returns to the operator console, instead of the editorial blueprint.
const VITE_PORTS = new Set(["5273", "5274", "5275"]);
function constellationUrl(): string {
  const fromEnv = (import.meta.env.VITE_BLUEPRINT_URL as string | undefined)?.trim();
  if (fromEnv) return `${fromEnv.replace(/\/$/, "")}/?view=constellation&from=fleet`;
  if (typeof window !== "undefined" && VITE_PORTS.has(window.location.port)) {
    return `${window.location.protocol}//${window.location.hostname}:5275/?view=constellation&from=fleet`;
  }
  return "/?view=constellation&from=fleet";
}

export default function App() {
  return (
    <>
      <header className="flex items-center gap-6 px-6 h-12 border-b border-slate-200 bg-white">
        <div className="font-semibold text-slate-900">Project Apex</div>
        <span className="text-slate-300">·</span>
        <div className="text-sm text-slate-500">Control Plane</div>
        <div className="ml-auto text-xs text-slate-500">role: Agent Administrator</div>
      </header>

      <div className="grid grid-cols-[200px_1fr_300px] h-[calc(100vh-3rem)]">
        <aside className="bg-white border-r border-slate-200 p-3 space-y-1">
          {nav.map(n => (
            <NavLink key={n.to} to={n.to}
                     className={({ isActive }) => `block text-sm px-3 py-1.5 rounded outline-none focus-visible:ring-2 focus-visible:ring-blue-300 ${isActive ?
                       "bg-blue-50 text-blue-700 font-medium" : "text-slate-700 hover:bg-slate-100"}`}>
              {n.label}
            </NavLink>
          ))}
          <a
            href={constellationUrl()}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-sm px-3 py-1.5 rounded outline-none focus-visible:ring-2 focus-visible:ring-blue-300 text-slate-700 hover:bg-slate-100"
          >
            Constellation ↗
          </a>
        </aside>

        <main className="p-6 overflow-y-auto overflow-x-hidden min-w-0">
          <Routes>
            <Route path="/" element={<Navigate to="/fleet" replace />} />
            <Route path="/fleet" element={<FleetDashboard />} />
            <Route path="/workflows/:id" element={<WorkflowDetail />} />
            <Route path="/exceptions" element={<ExceptionQueue />} />
            <Route path="/reviewer-queue" element={<ReviewerQueue />} />
            <Route path="/policy" element={<PolicyAndAutonomy />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/evals" element={<Evaluations />} />
            <Route path="/economics" element={<Economics />} />
            {/* POC2 surfaces */}
            <Route path="/hiring-manager/:workflowId?" element={<HiringManager />} />
          </Routes>
        </main>

        <aside className="border-l border-slate-200 bg-white overflow-auto">
          <FleetManagerRail />
        </aside>
      </div>
    </>
  );
}
