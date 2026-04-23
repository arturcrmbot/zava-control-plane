import { jsxs as _jsxs, jsx as _jsx, Fragment as _Fragment } from "react/jsx-runtime";
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
    { to: "/fleet", label: "Dashboard" },
    { to: "/exceptions", label: "Exceptions" },
    { to: "/policy", label: "Policy" },
    { to: "/analytics", label: "Analytics" },
    { to: "/evals", label: "Evaluations" },
    { to: "/agents", label: "Agents" },
    { to: "/library", label: "Library" },
    { to: "/economics", label: "Economics" },
];
function Stub({ title }) {
    return _jsxs("div", { className: "panel panel-body text-sm text-slate-600", children: [title, " \u2014 coming soon."] });
}
export default function App() {
    return (_jsxs(_Fragment, { children: [_jsxs("header", { className: "flex items-center gap-6 px-6 h-12 border-b border-slate-200 bg-white", children: [_jsx("div", { className: "font-semibold text-slate-900", children: "Project Apex" }), _jsx("span", { className: "text-slate-300", children: "\u00B7" }), _jsx("div", { className: "text-sm text-slate-500", children: "Control Plane" }), _jsx("div", { className: "ml-auto text-xs text-slate-500", children: "role: Finance Controller" })] }), _jsxs("div", { className: "grid grid-cols-[220px_1fr_360px] h-[calc(100vh-3rem)]", children: [_jsx("aside", { className: "bg-white border-r border-slate-200 p-3 space-y-1", children: nav.map(n => (_jsx(NavLink, { to: n.to, className: ({ isActive }) => `block text-sm px-3 py-1.5 rounded outline-none focus-visible:ring-2 focus-visible:ring-blue-300 ${isActive ?
                                "bg-blue-50 text-blue-700 font-medium" : "text-slate-700 hover:bg-slate-100"}`, children: n.label }, n.to))) }), _jsx("main", { className: "p-6 overflow-auto", children: _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(Navigate, { to: "/fleet", replace: true }) }), _jsx(Route, { path: "/fleet", element: _jsx(FleetDashboard, {}) }), _jsx(Route, { path: "/workflows/:id", element: _jsx(WorkflowDetail, {}) }), _jsx(Route, { path: "/exceptions", element: _jsx(ExceptionQueue, {}) }), _jsx(Route, { path: "/policy", element: _jsx(PolicyAndAutonomy, {}) }), _jsx(Route, { path: "/analytics", element: _jsx(Analytics, {}) }), _jsx(Route, { path: "/evals", element: _jsx(Evaluations, {}) }), _jsx(Route, { path: "/agents", element: _jsx(Stub, { title: "Agents" }) }), _jsx(Route, { path: "/library", element: _jsx(Stub, { title: "Library" }) }), _jsx(Route, { path: "/economics", element: _jsx(Stub, { title: "Economics" }) })] }) }), _jsx("aside", { className: "border-l border-slate-200 bg-white overflow-auto", children: _jsx(FleetManagerRail, {}) })] })] }));
}
