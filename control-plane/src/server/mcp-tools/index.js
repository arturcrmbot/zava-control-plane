import { queryFleetTool } from "./queryFleet";
import { queryTracesTool } from "./queryTraces";
import { composeExceptionTool } from "./composeException";
import { proposeSkillAmpTool } from "./proposeSkillAmp";
import { dryRunPolicyTool } from "./dryRunPolicy";
export function buildFleetManagerTools(store, bus, audit) {
    return [
        queryFleetTool(store),
        queryTracesTool(store),
        composeExceptionTool(store, bus, audit),
        proposeSkillAmpTool(store),
        dryRunPolicyTool(store),
    ];
}
