import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
    return (_jsxs("div", { className: "h-screen flex flex-col bg-slate-950 text-slate-100", children: [_jsxs("header", { className: "h-12 border-b border-slate-800 flex items-center px-4 gap-4", children: [_jsx("div", { className: "font-semibold tracking-tight", children: "WPP Control Plane" }), _jsx("div", { className: "text-xs text-slate-400", children: "Finance Controller \u00B7 Ogilvy-US \u00B7 US-CA" }), _jsx("div", { className: "ml-auto text-xs text-slate-400", children: "role: Finance Controller" })] }), _jsxs("div", { className: "flex-1 flex overflow-hidden", children: [_jsx("nav", { className: "w-48 border-r border-slate-800 p-2 space-y-1", children: navItems.map(({ to, label, icon: Icon }) => (_jsxs(NavLink, { to: to, className: ({ isActive }) => `flex items-center gap-2 px-2 py-1.5 rounded text-sm ${isActive ? "bg-slate-800 text-slate-50" : "text-slate-400 hover:bg-slate-900"}`, children: [_jsx(Icon, { size: 14 }), " ", label] }, to))) }), _jsx("main", { className: "flex-1 overflow-auto p-4", children: _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(Navigate, { to: "/fleet", replace: true }) }), _jsx(Route, { path: "/fleet", element: _jsx(FleetDashboard, {}) }), _jsx(Route, { path: "/exceptions", element: _jsx(ExceptionQueue, {}) }), _jsx(Route, { path: "/workflows/:id", element: _jsx(WorkflowDetail, {}) }), _jsx(Route, { path: "/policy", element: _jsx(PolicyAndAutonomy, {}) }), _jsx(Route, { path: "/analytics", element: _jsx(Analytics, {}) }), _jsx(Route, { path: "/evals", element: _jsx(Evaluations, {}) })] }) }), _jsx("aside", { className: "w-80 border-l border-slate-800 overflow-auto", children: _jsx(FleetManagerRail, {}) })] })] }));
}
