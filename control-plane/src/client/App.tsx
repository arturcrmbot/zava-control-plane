// src/client/App.tsx
import { NavLink, Routes, Route, Navigate } from "react-router-dom";
import { LayoutDashboard, AlertTriangle, Shield, BarChart3, FlaskConical } from "lucide-react";
import FleetDashboard from "./routes/FleetDashboard";
import ExceptionQueue from "./routes/ExceptionQueue";
import WorkflowDetail from "./routes/WorkflowDetail";
import PolicyAndAutonomy from "./routes/PolicyAndAutonomy";
import Analytics from "./routes/Analytics";
import Evaluations from "./routes/Evaluations";
import FleetManagerRail from "./components/FleetManagerRail";

const navItems = [
  { to: "/fleet", label: "Fleet", icon: LayoutDashboard },
  { to: "/exceptions", label: "Exceptions", icon: AlertTriangle },
  { to: "/policy", label: "Policy", icon: Shield },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/evals", label: "Evaluations", icon: FlaskConical },
];

export default function App() {
  return (
    <div className="h-screen flex flex-col bg-slate-950 text-slate-100">
      <header className="h-12 border-b border-slate-800 flex items-center px-4 gap-4">
        <div className="font-semibold tracking-tight">WPP Control Plane</div>
        <div className="text-xs text-slate-400">Finance Controller · Ogilvy-US · US-CA</div>
        <div className="ml-auto text-xs text-slate-400">role: Finance Controller</div>
      </header>
      <div className="flex-1 flex overflow-hidden">
        <nav className="w-48 border-r border-slate-800 p-2 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2 px-2 py-1.5 rounded text-sm ${
                  isActive ? "bg-slate-800 text-slate-50" : "text-slate-400 hover:bg-slate-900"
                }`
              }
            >
              <Icon size={14} /> {label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 overflow-auto p-4">
          <Routes>
            <Route path="/" element={<Navigate to="/fleet" replace />} />
            <Route path="/fleet" element={<FleetDashboard />} />
            <Route path="/exceptions" element={<ExceptionQueue />} />
            <Route path="/workflows/:id" element={<WorkflowDetail />} />
            <Route path="/policy" element={<PolicyAndAutonomy />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/evals" element={<Evaluations />} />
          </Routes>
        </main>
        <aside className="w-80 border-l border-slate-800 overflow-auto">
          <FleetManagerRail />
        </aside>
      </div>
    </div>
  );
}
