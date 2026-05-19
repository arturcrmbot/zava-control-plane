// web/client/components/feed/FleetControlShell.tsx
//
// Replaces App.tsx. Top-level layout: Header on top, LeftRail on the left,
// Feed in the middle, conditional Drawer on the right (when /workflows/:id).
// Preserves the existing secondary routes inside <Routes> so the LeftRail's
// "More ▾" links still navigate. Role state is persisted via localStorage;
// switching role re-keys the Feed so it re-mounts with fresh defaults.
import { useEffect, useMemo } from "react";
import { Route, Routes, useNavigate, useParams, Navigate } from "react-router-dom";
import { type RoleId, getRolePreset, type SavedView } from "@shared/roles";
import { useLocalStorageState } from "@client/hooks/useLocalStorageState";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import { ToastProvider } from "./Toast";
import Header from "./Header";
import LeftRail from "./LeftRail";
import Feed from "./Feed";
import Drawer from "./Drawer";
import { useWorkflows } from "@client/hooks/useWorkflows";
import { useFeedItems, type FilterState } from "@client/hooks/useFeedItems";
import Analytics from "@client/routes/Analytics";
import Evaluations from "@client/routes/Evaluations";
import Economics from "@client/routes/Economics";
import PolicyAndAutonomy from "@client/routes/PolicyAndAutonomy";
import HiringManager from "@client/routes/HiringManager";
import Dashboard from "@client/routes/Dashboard";

function ShellBody() {
  const [roleId, setRoleId] = useLocalStorageState<RoleId>("fleetctl.role", "ops-reviewer");
  const role = useMemo(() => getRolePreset(roleId), [roleId]);
  const [userViews, setUserViews] = useLocalStorageState<SavedView[]>(
    `fleetctl.savedViews.${roleId}`, [],
  );

  return (
    <ToastProvider>
      <ResolutionProvider>
        <ShellInner
          role={role}
          onRoleChange={setRoleId}
          userViews={userViews}
          setUserViews={setUserViews}
        />
      </ResolutionProvider>
    </ToastProvider>
  );
}

function ShellInner({
  role, onRoleChange, userViews, setUserViews,
}: {
  role: ReturnType<typeof getRolePreset>;
  onRoleChange: (r: RoleId) => void;
  userViews: SavedView[];
  setUserViews: (updater: (prev: SavedView[]) => SavedView[]) => void;
}) {
  const navigate = useNavigate();
  const workflows = useWorkflows();

  // Compute header notifications + Today chip data using the role's
  // default filter. This is independent of the Feed's filter state (the
  // user may switch to "all-activity" in the feed but the header still
  // reflects the role's "needs you" framing).
  const headerFilter = useMemo<FilterState>(
    () => ({
      mode: role.defaultFilter,
      domains: role.defaultDomains,
      severity: null,
      search: "",
    }),
    [role.defaultFilter, role.defaultDomains],
  );
  const unreadItems = useFeedItems(role, headerFilter);

  const onOpenDrawer = (workflowId: string) => navigate(`/workflows/${workflowId}`);
  const onJumpTo = (itemId: string) => {
    const match = unreadItems.find((i) => i.id === itemId);
    if (match?.workflowId) {
      navigate(`/workflows/${match.workflowId}`);
    }
  };
  const onSearch = (workflowId: string) => navigate(`/workflows/${workflowId}`);

  return (
    <>
      <Header
        role={role}
        onRoleChange={onRoleChange}
        unreadItems={unreadItems}
        onJumpTo={onJumpTo}
        onSearch={onSearch}
        workflows={workflows}
      />
      <div className="flex flex-1 min-h-0">
        <LeftRail
          role={role}
          userViews={userViews}
          onSelectView={(v) => {
            const params = new URLSearchParams();
            if (v.filter !== role.defaultFilter) params.set("filter", v.filter);
            if (v.domains.length > 0) params.set("domains", v.domains.join(","));
            if (v.severity) params.set("severity", v.severity);
            if (v.mine) params.set("mine", "1");
            if (v.search) params.set("q", v.search);
            const qs = params.toString();
            navigate(qs ? `/?${qs}` : "/");
          }}
          onSaveCurrent={() => {
            const label = window.prompt("Name this view?", "My view");
            if (!label) return;
            const sv: SavedView = {
              id: `user-${Date.now()}`,
              label,
              filter: role.defaultFilter,
              domains: role.defaultDomains,
            };
            setUserViews((prev) => [...prev, sv]);
          }}
        />
        <main className="flex-1 min-w-0 flex">
          <Routes>
            <Route path="/" element={<Feed key={role.id} role={role} onOpenDrawer={onOpenDrawer} />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/fleet" element={<Navigate to="/" replace />} />
            <Route path="/exceptions" element={<Navigate to="/?filter=exceptions" replace />} />
            <Route path="/reviewer-queue" element={<Navigate to="/?filter=hitl" replace />} />
            <Route path="/workflows/:id" element={
              <FeedWithDrawer role={role} onOpenDrawer={onOpenDrawer} />
            } />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/evals" element={<Evaluations />} />
            <Route path="/economics" element={<Economics />} />
            <Route path="/policy" element={<PolicyAndAutonomy />} />
            <Route path="/hiring-manager/:workflowId?" element={<HiringManager />} />
          </Routes>
        </main>
      </div>
    </>
  );
}

function FeedWithDrawer({
  role, onOpenDrawer,
}: {
  role: ReturnType<typeof getRolePreset>;
  onOpenDrawer: (workflowId: string) => void;
}) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  // Esc closes the drawer. We don't go through useKeyboardShortcuts here
  // because the Feed below already binds Esc for its own help overlay;
  // listening at this level ensures the drawer-close shortcut runs first
  // and is independent of focused-card state.
  useEffect(() => {
    if (!id) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const t = e.target;
      if (t instanceof HTMLElement) {
        const tag = t.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        if (t.isContentEditable) return;
      }
      navigate("/");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [id, navigate]);
  return (
    <>
      <Feed key={role.id} role={role} onOpenDrawer={onOpenDrawer} />
      {id && (
        <Drawer
          workflowId={id}
          role={role}
          onClose={() => navigate("/")}
        />
      )}
    </>
  );
}

export default function FleetControlShell() {
  return (
    <div className="flex flex-col h-screen">
      <ShellBody />
    </div>
  );
}
