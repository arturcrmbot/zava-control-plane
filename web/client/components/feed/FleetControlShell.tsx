// web/client/components/feed/FleetControlShell.tsx
//
// Replaces App.tsx. Top-level layout: Header on top, LeftRail on the left,
// Feed in the middle, conditional Drawer on the right (when /workflows/:id).
// Preserves the existing secondary routes inside <Routes> so the LeftRail's
// "More ▾" links still navigate. Role state is persisted via localStorage;
// switching role re-keys the Feed so it re-mounts with fresh defaults.
import { useMemo } from "react";
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
import Analytics from "@client/routes/Analytics";
import Evaluations from "@client/routes/Evaluations";
import Economics from "@client/routes/Economics";
import PolicyAndAutonomy from "@client/routes/PolicyAndAutonomy";
import HiringManager from "@client/routes/HiringManager";

function ShellBody() {
  const navigate = useNavigate();
  const [roleId, setRoleId] = useLocalStorageState<RoleId>("fleetctl.role", "ops-reviewer");
  const role = useMemo(() => getRolePreset(roleId), [roleId]);
  const [userViews, setUserViews] = useLocalStorageState<SavedView[]>(
    `fleetctl.savedViews.${roleId}`, [],
  );

  const workflows = useWorkflows();

  const unreadItems = useMemo(() => [], []);

  const onOpenDrawer = (workflowId: string) => navigate(`/workflows/${workflowId}`);
  const onJumpTo = (_itemId: string) => { /* v1: no-op */ };
  const onSearch = (workflowId: string) => navigate(`/workflows/${workflowId}`);

  return (
    <ToastProvider>
      <ResolutionProvider>
        <Header
          role={role}
          onRoleChange={setRoleId}
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
              if (v.domains.length > 0) params.set("domains", v.domains.join(","));
              if (v.search) params.set("q", v.search);
              navigate(`/?${params.toString()}`);
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
      </ResolutionProvider>
    </ToastProvider>
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
