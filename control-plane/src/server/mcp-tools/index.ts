import type { StateStore } from "@server/services/stateStore";
import type { EventBus } from "@server/services/eventBus";
import type { AuditLogger } from "@server/services/auditLogger";
import { queryFleetTool } from "./queryFleet";
import { queryTracesTool } from "./queryTraces";
import { composeExceptionTool } from "./composeException";
import { proposeSkillAmpTool } from "./proposeSkillAmp";
import { dryRunPolicyTool } from "./dryRunPolicy";

export function buildFleetManagerTools(store: StateStore, bus: EventBus, audit: AuditLogger) {
  return [
    queryFleetTool(store),
    queryTracesTool(store),
    composeExceptionTool(store, bus, audit),
    proposeSkillAmpTool(store),
    dryRunPolicyTool(store),
  ];
}
