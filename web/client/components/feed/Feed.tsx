//
// The Feed is the operator's home. It owns the active filter state, the
// inbound-buffer state, and select-mode for bulk actions. Items come from
// useFeedItems (which takes the role + filter). The role-default filter
// can be overridden by URL param `?filter=hitl|exceptions|needs-you|all`
// (used by the 301 redirects from /reviewer-queue and /exceptions).
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RolePreset } from "@shared/roles";
import { useFeedItems, type FilterState } from "@client/hooks/useFeedItems";
import { useNewItemsBuffer } from "@client/hooks/useNewItemsBuffer";
import FilterBar from "./FilterBar";
import NewItemsPill from "./NewItemsPill";
import CardList from "./CardList";
import BulkActionBar from "./BulkActionBar";

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
  const [params] = useSearchParams();
  const initialUrl = filterFromUrl(params.get("filter"));

  const [filter, setFilter] = useState<FilterState>(() => ({
    mode: initialUrl?.mode ?? role.defaultFilter,
    domains: role.defaultDomains,
    severity: null,
    search: "",
  }));

  useEffect(() => {
    setFilter((f) => ({
      ...f,
      mode: role.defaultFilter,
      domains: role.defaultDomains,
    }));
  }, [role.id, role.defaultFilter, role.defaultDomains]);

  const items = useFeedItems(role, filter);
  const buffer = useNewItemsBuffer(items);

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

  return (
    <div className="px-6 py-4 flex-1 min-w-0 overflow-y-auto">
      <FilterBar
        filter={filter}
        onChange={setFilter}
        selectMode={selectMode}
        onSelectModeChange={(v) => { setSelectMode(v); if (!v) clearSelection(); }}
        availableDomains={availableDomains}
      />
      <NewItemsPill count={buffer.pendingCount} onPullIn={buffer.pullIn} />
      <CardList
        items={buffer.visible}
        hideActions={role.hideActionButtons}
        onOpenDrawer={onOpenDrawer}
        selectMode={selectMode && !role.hideActionButtons}
        selected={selected}
        onToggleSelect={toggleSelect}
      />
      {selectMode && !role.hideActionButtons && (
        <BulkActionBar
          selectedIds={[...selected]}
          onCleared={clearSelection}
        />
      )}
    </div>
  );
}
