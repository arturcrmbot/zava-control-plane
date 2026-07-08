// web/shared/roles.ts
//
// Frontend-only role bundles for the Fleet Control feed redesign. Each role
// is a preset of (default filter, visible card types, action availability,
// header chip content, drawer section order, More-menu order). Switching
// role re-applies the bundle to the current feed in place; it does not
// navigate or call the backend.

export type RoleId =
  | "ops-reviewer"
  | "finance-controller"
  | "hiring-manager"
  | "sre"
  | "executive";

export type CardType =
  | "hitl"
  | "exception"
  | "external-wait"
  | "milestone"
  | "policy"
  | "agent-event"
  | "resolved"
  | "workflow";

export type DrawerSection = "decision" | "activity" | "audit" | "reasoning";

export type FilterMode = "needs-you" | "all-activity";

export type TodayChipKind =
  | "needs-you-count"          // System Admin: "Today: N · M crit"
  | "money-saved"              // Finance: "$ saved today: $XXX"
  | "hiring-summary"           // Hiring: "Open roles: N · Candidates today: M"
  | "fleet-health"             // SRE: "Fleet health: green · 14ms p95"
  | "executive-summary";       // Exec: "Throughput · Auto-rate · Cost"

export interface SavedView {
  id: string;                  // stable id, used as key
  label: string;               // sidebar label
  filter: FilterMode;
  domains: string[];           // empty = all
  severity?: "critical" | "high" | "medium" | null;
  mine?: boolean;              // when true, restrict to operator's own actions (resolved cards last 24h)
  search?: string;
}

export interface RolePreset {
  id: RoleId;
  label: string;
  defaultFilter: FilterMode;
  defaultDomains: string[];        // domain prefix filter; empty = all
  visibleCardTypes: CardType[];    // restricts what's renderable
  hideActionButtons: boolean;      // executive read-only mode
  defaultSavedViews: SavedView[];  // seed the left rail top zone
  moreOrder: string[];             // reorder of "More ▾" submenu (route paths)
  todayChip: TodayChipKind;
  drawerSectionOrder: DrawerSection[];
}

const FINANCE_DOMAINS = [
  "expense-claim",
  "ap-invoice",
  "purchase-order",
  "treasury-fx",
  "contract-renewal",
];

export const ROLE_PRESETS: RolePreset[] = [
  {
    id: "ops-reviewer",
    label: "System Admin",
    defaultFilter: "needs-you",
    defaultDomains: [],
    visibleCardTypes: ["hitl", "exception", "external-wait", "milestone", "policy", "agent-event", "resolved", "workflow"],
    hideActionButtons: false,
    defaultSavedViews: [
      { id: "ops-needs-you-critical", label: "Critical · needs you", filter: "needs-you", domains: [], severity: "critical" },
      { id: "ops-all-mine", label: "All my decisions today", filter: "needs-you", domains: [], mine: true },
    ],
    moreOrder: ["/analytics", "/evals", "/economics", "/policy"],
    todayChip: "needs-you-count",
    drawerSectionOrder: ["decision", "reasoning", "activity", "audit"],
  },
  {
    id: "finance-controller",
    label: "Finance Controller",
    defaultFilter: "needs-you",
    defaultDomains: FINANCE_DOMAINS,
    visibleCardTypes: ["hitl", "exception", "external-wait", "policy", "resolved", "workflow"],
    hideActionButtons: false,
    defaultSavedViews: [
      { id: "fin-expense", label: "Expense claims", filter: "needs-you", domains: ["expense-claim"] },
      { id: "fin-ap", label: "AP invoices", filter: "needs-you", domains: ["ap-invoice"] },
      { id: "fin-po", label: "Purchase orders", filter: "needs-you", domains: ["purchase-order"] },
    ],
    moreOrder: ["/economics", "/analytics", "/policy", "/evals"],
    todayChip: "money-saved",
    drawerSectionOrder: ["decision", "reasoning", "activity", "audit"],
  },
  {
    id: "hiring-manager",
    label: "Hiring Manager",
    defaultFilter: "needs-you",
    defaultDomains: ["hiring"],
    visibleCardTypes: ["hitl", "exception", "resolved", "workflow"],
    hideActionButtons: false,
    defaultSavedViews: [
      { id: "hire-all", label: "All open roles", filter: "needs-you", domains: ["hiring"] },
    ],
    moreOrder: ["/analytics", "/evals", "/policy", "/economics"],
    todayChip: "hiring-summary",
    drawerSectionOrder: ["decision", "reasoning", "activity", "audit"],
  },
  {
    id: "sre",
    label: "Agent-Platform Engineer",
    defaultFilter: "all-activity",
    defaultDomains: [],
    visibleCardTypes: ["hitl", "exception", "external-wait", "milestone", "policy", "agent-event", "resolved", "workflow"],
    hideActionButtons: false,
    defaultSavedViews: [
      { id: "sre-errors", label: "Errors only", filter: "all-activity", domains: [] },
      { id: "sre-policy", label: "Policy / autonomy changes", filter: "all-activity", domains: [] },
    ],
    moreOrder: ["/evals", "/policy", "/analytics", "/economics"],
    todayChip: "fleet-health",
    drawerSectionOrder: ["activity", "reasoning", "decision", "audit"],
  },
  {
    id: "executive",
    label: "Executive",
    defaultFilter: "all-activity",
    defaultDomains: [],
    visibleCardTypes: ["milestone", "policy", "resolved", "workflow"],
    hideActionButtons: true,
    defaultSavedViews: [
      { id: "exec-milestones", label: "Today's milestones", filter: "all-activity", domains: [] },
    ],
    moreOrder: ["/economics", "/analytics", "/policy", "/evals"],
    todayChip: "executive-summary",
    drawerSectionOrder: ["audit", "reasoning", "activity", "decision"],
  },
];

const BY_ID: Record<string, RolePreset> = Object.fromEntries(
  ROLE_PRESETS.map((r) => [r.id, r]),
);

export function getRolePreset(id: RoleId | string): RolePreset {
  return BY_ID[id] ?? BY_ID["ops-reviewer"];
}
