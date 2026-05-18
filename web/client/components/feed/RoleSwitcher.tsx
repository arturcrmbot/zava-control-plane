// web/client/components/feed/RoleSwitcher.tsx
//
// Dropdown that swaps the active RolePreset. Persistence lives in
// FleetControlShell via useLocalStorageState — this component only fires
// onChange.
import { useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";
import { ROLE_PRESETS, type RoleId, getRolePreset } from "@shared/roles";

export default function RoleSwitcher({
  current, onChange,
}: {
  current: RoleId;
  onChange: (next: RoleId) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const label = getRolePreset(current).label;

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-xs px-3 py-1.5 rounded font-medium bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50 flex items-center gap-1"
      >
        role: <span className="font-semibold">{label}</span>
        <ChevronDown size={12} />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg min-w-[200px] py-1 z-50">
          {ROLE_PRESETS.map((r) => (
            <button
              key={r.id}
              role="menuitem"
              type="button"
              onClick={() => { onChange(r.id); setOpen(false); }}
              className={`w-full text-left text-xs px-3 py-1.5 hover:bg-slate-50 ${r.id === current ? "font-semibold text-blue-700" : "text-slate-700"}`}
            >{r.label}</button>
          ))}
        </div>
      )}
    </div>
  );
}
