export const WAKE_TYPES = new Set([
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.sla.breach_imminent",
    "workflow.policy.violation",
    "fleet.anomaly.detected",
    "fleet.tick"
]);
export function wakesFleetManager(e) {
    return WAKE_TYPES.has(e.type);
}
