//
// Two-column memory layer view + on-demand demo triggers.
// Columns: Memories (left) · Dream passes (right).
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Sparkles } from "lucide-react";

import MemoriesColumn from "@client/components/memory/MemoriesColumn";
import DreamPassColumn from "@client/components/memory/DreamPassColumn";

const DEFAULT_DOMAINS = ["hiring", "vendor_kyc", "expense_claim"];

export default function Memory() {
  const [domains, setDomains] = useState<string[]>(DEFAULT_DOMAINS);
  const [domain, setDomain] = useState<string>("hiring");
  const [busy, setBusy] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    void fetch("/api/memory/v2/domains")
      .then((response) => {
        if (!response.ok) throw new Error(`memory domains: ${response.status}`);
        return response.json() as Promise<{ domains?: string[] }>;
      })
      .then((body) => {
        if (!active || !body.domains?.length) return;
        setDomains(body.domains);
        setDomain((current) => (
          body.domains!.includes(current) ? current : body.domains![0]
        ));
      })
      .catch(() => {
        // Keep the compatibility selector when the older API is unavailable.
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [menuOpen]);

  async function triggerPass() {
    setBusy(true);
    try {
      await fetch(
        `/api/dream-pass/run?domain=${encodeURIComponent(domain)}&sample=10`,
        { method: "POST" },
      );
    } finally {
      setBusy(false);
    }
  }

  async function dreamStorm() {
    setMenuOpen(false);
    setBusy(true);
    try {
      await fetch(
        `/api/simulator/dream-storm?domains=${domains.join(",")}&runs=3`,
        { method: "POST" },
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 min-w-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-4">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1 dark:text-slate-400 dark:hover:text-slate-100"
          ><ArrowLeft size={14} /> Back to feed</Link>
        </div>
        <header className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Memory</h1>
          <div className="flex items-center gap-2">
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="text-xs border border-slate-300 dark:border-slate-700 dark:bg-slate-800 rounded px-2 py-1"
            >
              {domains.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <button
              type="button"
              disabled={busy}
              onClick={triggerPass}
              className="text-xs px-3 py-1.5 rounded font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60 flex items-center gap-1"
            ><Sparkles size={14} /> Trigger pass</button>
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                aria-label="More actions"
                disabled={busy}
                onClick={() => setMenuOpen((o) => !o)}
                className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white text-base px-2 py-1 rounded disabled:opacity-50 leading-none"
              >⋯</button>
              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 mt-1 w-40 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow z-10"
                >
                  <button
                    type="button"
                    role="menuitem"
                    onClick={dreamStorm}
                    className="block w-full text-left text-xs px-3 py-2 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
                  >Dream storm (all domains)</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <MemoriesColumn domain={domain} />
          <DreamPassColumn domain={domain} />
        </div>
      </div>
    </div>
  );
}
