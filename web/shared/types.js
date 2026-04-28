// control-plane/src/shared/types.ts
export const PHASE_ORDER = [
    "Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"
];
export const EXPENSE_PHASE_ORDER = [
    "Intake", "Classify", "Validate Receipt", "Route", "Notify", "Arbitrate", "Audit"
];
export function nextPhase(p) {
    const i = PHASE_ORDER.indexOf(p);
    if (i === -1 || i === PHASE_ORDER.length - 1)
        return null;
    return PHASE_ORDER[i + 1];
}
