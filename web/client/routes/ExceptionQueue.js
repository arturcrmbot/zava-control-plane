import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
// src/client/routes/ExceptionQueue.tsx
import { useState } from "react";
import { useExceptions } from "../hooks/useExceptions";
import ExceptionItem from "../components/ExceptionItem";
import BulkHitlModal from "../components/BulkHitlModal";
export default function ExceptionQueue() {
    const { items, refresh } = useExceptions();
    const [selected, setSelected] = useState(new Set());
    const [modal, setModal] = useState(false);
    const toggle = (id) => {
        const n = new Set(selected);
        n.has(id) ? n.delete(id) : n.add(id);
        setSelected(n);
    };
    const confirm = async (resolution) => {
        await fetch("/api/exceptions/bulk-resolve", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ exceptionIds: [...selected], resolution, resolvedBy: "finance-controller@wpp" })
        });
        setSelected(new Set());
        setModal(false);
        await refresh();
    };
    return (_jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("div", { className: "text-sm font-semibold", children: "Exception Queue" }), _jsxs("div", { className: "text-xs text-slate-500", children: [items.length, " open"] }), _jsx("div", { className: "ml-auto flex gap-2", children: _jsxs("button", { disabled: selected.size === 0, onClick: () => setModal(true), className: "text-xs px-3 py-1.5 bg-amber-600 rounded hover:bg-amber-500 disabled:opacity-40", children: ["Bulk resolve (", selected.size, ")"] }) })] }), _jsx("div", { className: "space-y-2", children: items.map(e => (_jsx(ExceptionItem, { e: e, selected: selected.has(e.id), onToggle: toggle, onResolved: refresh }, e.id))) }), modal && _jsx(BulkHitlModal, { ids: [...selected], onClose: () => setModal(false), onConfirm: confirm })] }));
}
