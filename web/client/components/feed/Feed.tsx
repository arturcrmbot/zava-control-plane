// web/client/components/feed/Feed.tsx
//
// The Feed is the operator's home. It owns the active filter state, the
// inbound-buffer state, and select-mode for bulk actions. Items come from
// useFeedItems (which takes the role + filter). The role-default filter
// can be overridden by URL param `?filter=hitl|exceptions|needs-you|all`
// (used by the 301 redirects from /reviewer-queue and /exceptions).
//
// Filter persistence: the active filter state survives reload via a
// per-role localStorage key (fleetctl.filter.<roleId>). Explicit URL
// overrides (`?filter=…`, `?domains=…`, `?q=…`) take precedence on first
// mount and replace the stored value, so deep links and saved-view
// navigation still work.
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RolePreset } from "@shared/roles";
import { useFeedItems, type FilterState } from "@client/hooks/useFeedItems";
import { useNewItemsBuffer } from "@client/hooks/useNewItemsBuffer";
import { useLocalStorageState } from "@client/hooks/useLocalStorageState";
import { useKeyboardShortcuts } from "@client/hooks/useKeyboardShortcuts";
import FilterBar from "./FilterBar";
import NewItemsPill from "./NewItemsPill";
import CardList from "./CardList";
import EmptyFeed from "./EmptyFeed";
import BulkActionBar from "./BulkActionBar";
import ShortcutHelp from "./ShortcutHelp";

const KNOWN_DOMAINS = [
  "expense-claim", "hiring", "invoice-p2p", "travel-preapproval", "vendor-kyc",
  "employee-onboarding", "it-access-request", "contract-renewal", "perf-review",
  "ap-invoice", "purchase-order", "contract-review", "privacy-dpia", "treasury-fx",
  "creative-campaign",
];

function filterFromUrl(rawMode: string | null): Partial<FilterState> | null {
  if (rawMode === "hitl") return { mode: "needs-you" };
  if (rawMode === "exceptions") return { mode: "needs-you" };
  if (rawMode === "needs-you") return { mode: "needs-you" };
  if (rawMode === "all") return { mode: "all-activity" };
  return null;
}

export default function Feed({
  role, onOpenDrawer,
}: {
  role: RolePreset;
  onOpenDrawer: (workflowId: string) => void;
}) {
  const [params, setParams] = useSearchParams();

  // Per-role default & URL overrides → starting filter; subsequent edits are
  // persisted under fleetctl.filter.<roleId>.
  const storageKey = `fleetctl.filter.${role.id}`;
  const initialUrl = filterFromUrl(params.get("filter"));
  const urlDomains = params.get("domains");
  const urlSearch = params.get("q");
  const urlSeverity = params.get("severity") as FilterState["severity"];
  const urlMine = params.get("mine") === "1";
  const [persisted, setPersisted] = useLocalStorageState<FilterState | null>(storageKey, null);

  const [filter, setFilterRaw] = useState<FilterState>(() => {
    // Explicit URL params win over persisted state. If no URL params, hydrate
    // from localStorage. Otherwise fall back to role defaults.
    if (initialUrl || urlDomains || urlSearch || urlSeverity || urlMine) {
      return {
        mode: initialUrl?.mode ?? role.defaultFilter,
        domains: urlDomains ? urlDomains.split(",").filter(Boolean) : role.defaultDomains,
        severity: urlSeverity ?? null,
        search: urlSearch ?? "",
        mine: urlMine,
      };
    }
    if (persisted) return persisted;
    return {
      mode: role.defaultFilter,
      domains: role.defaultDomains,
      severity: null,
      search: "",
      mine: false,
    };
  });

  // Re-sync filter when URL params change *after* mount (e.g. saved-view click
  // navigates and updates the query string — the existing Feed instance must
  // pick up the new filter values rather than ignore them).
  const lastSyncedRef = useRef<string>("");
  useEffect(() => {
    const sig = `${params.get("filter") ?? ""}|${params.get("domains") ?? ""}|${params.get("severity") ?? ""}|${params.get("q") ?? ""}|${params.get("mine") ?? ""}`;
    if (sig === lastSyncedRef.current) return;
    lastSyncedRef.current = sig;
    const urlFromUrl = filterFromUrl(params.get("filter"));
    const dom = params.get("domains");
    const next: FilterState = {
      mode: urlFromUrl?.mode ?? role.defaultFilter,
      domains: dom ? dom.split(",").filter(Boolean) : role.defaultDomains,
      severity: (params.get("severity") as FilterState["severity"]) ?? null,
      search: params.get("q") ?? "",
      mine: params.get("mine") === "1",
    };
    setFilterRaw(next);
    setPersisted(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  // Wrap setFilter so every change persists + reflects to URL params (so
  // refresh and external links both round-trip).
  const setFilter = (next: FilterState) => {
    setFilterRaw(next);
    setPersisted(next);
    const nextParams = new URLSearchParams(params);
    if (next.mode !== role.defaultFilter) nextParams.set("filter", next.mode);
    else nextParams.delete("filter");
    if (next.domains.length > 0) nextParams.set("domains", next.domains.join(","));
    else nextParams.delete("domains");
    if (next.severity) nextParams.set("severity", next.severity);
    else nextParams.delete("severity");
    if (next.search) nextParams.set("q", next.search);
    else nextParams.delete("q");
    if (next.mine) nextParams.set("mine", "1");
    else nextParams.delete("mine");
    // Mirror back into the ref so the URL-sync effect doesn't bounce.
    lastSyncedRef.current = `${nextParams.get("filter") ?? ""}|${nextParams.get("domains") ?? ""}|${nextParams.get("severity") ?? ""}|${nextParams.get("q") ?? ""}|${nextParams.get("mine") ?? ""}`;
    setParams(nextParams, { replace: true });
  };

  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const toggleSelect = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const clearSelection = () => setSelected(new Set());

  const availableDomains = useMemo(
    () => (role.defaultDomains.length > 0 ? role.defaultDomains : KNOWN_DOMAINS),
    [role.defaultDomains],
  );

  // Facebook-style auto-insert: when scrolled to the top of the feed, new
  // items appear in place. Once the operator has scrolled down to look at
  // older items, new arrivals queue behind the "↑ N new" pill so the
  // reading position doesn't jump under them.
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [scrollTopPx, setScrollTopPx] = useState(0);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    let rafId: number | null = null;
    const onScroll = () => {
      if (rafId != null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        setScrollTopPx(el.scrollTop);
      });
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      el.removeEventListener("scroll", onScroll);
      if (rafId != null) cancelAnimationFrame(rafId);
    };
  }, []);

  const items = useFeedItems(role, filter);
  const buffer = useNewItemsBuffer(items, {
    autoInsertWhenAtTop: true,
    scrollTopPx,
    topThresholdPx: 80,
  });

  // Keyboard navigation: j/k cycle a "focused" index into buffer.visible
  // (rendered via a faint ring on the focused card). Enter opens. The
  // focus value lives in state so we can scroll the focused card into
  // view smoothly.
  const [focusIdx, setFocusIdx] = useState(0);
  const [helpOpen, setHelpOpen] = useState(false);
  useEffect(() => {
    // Keep focus in bounds when items shrink.
    if (focusIdx >= buffer.visible.length) {
      setFocusIdx(Math.max(0, buffer.visible.length - 1));
    }
  }, [buffer.visible.length, focusIdx]);

  const scrollFocusedIntoView = (idx: number) => {
    // Defer to next frame so DOM has the new focus class applied.
    requestAnimationFrame(() => {
      const el = scrollRef.current?.querySelector<HTMLElement>(`[data-feed-idx="${idx}"]`);
      el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  };

  useKeyboardShortcuts({
    onNext: () => {
      setFocusIdx((i) => {
        const next = Math.min(buffer.visible.length - 1, i + 1);
        scrollFocusedIntoView(next);
        return next;
      });
    },
    onPrev: () => {
      setFocusIdx((i) => {
        const next = Math.max(0, i - 1);
        scrollFocusedIntoView(next);
        return next;
      });
    },
    onOpen: () => {
      const item = buffer.visible[focusIdx];
      if (item?.workflowId) onOpenDrawer(item.workflowId);
    },
    onFocusSearch: () => {
      // Header search has placeholder "Search workflows…" — find by that.
      const el = document.querySelector<HTMLInputElement>('input[placeholder^="Search workflows"]');
      el?.focus();
    },
    onToggleHelp: () => setHelpOpen((v) => !v),
    onClose: () => setHelpOpen(false),
  });

  return (
    <div ref={scrollRef} className="px-6 pb-4 flex-1 min-w-0 overflow-y-auto bg-slate-50 dark:bg-slate-950">
      <div className="sticky top-0 z-20 -mx-6 px-6 pt-4 pb-2 bg-slate-50 dark:bg-slate-950">
        <FilterBar
          filter={filter}
          onChange={setFilter}
          selectMode={selectMode}
          onSelectModeChange={(v) => { setSelectMode(v); if (!v) clearSelection(); }}
          availableDomains={availableDomains}
        />
      </div>
      <NewItemsPill count={buffer.pendingCount} onPullIn={buffer.pullIn} />
      {buffer.visible.length === 0 ? (
        <EmptyFeed
          hasItems={items.length > 0}
          onClearFilters={() => setFilter({
            mode: role.defaultFilter,
            domains: role.defaultDomains,
            severity: null,
            search: "",
            mine: false,
          })}
        />
      ) : (
        <CardList
          items={buffer.visible}
          hideActions={role.hideActionButtons}
          onOpenDrawer={onOpenDrawer}
          selectMode={selectMode && !role.hideActionButtons}
          selected={selected}
          onToggleSelect={toggleSelect}
          focusedIndex={focusIdx}
        />
      )}
      {helpOpen && <ShortcutHelp onClose={() => setHelpOpen(false)} />}
      {selectMode && !role.hideActionButtons && (
        <BulkActionBar
          selectedIds={[...selected]}
          onCleared={clearSelection}
        />
      )}
    </div>
  );
}
