// web/client/components/feed/DrawerAudit.tsx
//
// Third drawer section: collapsed-by-default accordions for the panels the
// reviewer rarely needs but the audit/exec role does. Per spec §4 default
// state is "collapsed".
import { useState } from "react";
import type { DrawerData } from "./Drawer";
import type { ActionLedgerEntry } from "@shared/types";
import EvidencePanel from "@client/features/governance/EvidencePanel";
import EconomicsPanel from "@client/components/apex/EconomicsPanel";
import FleetAssignment from "@client/components/apex/FleetAssignment";
import AuditTrail from "@client/components/apex/AuditTrail";
import SkillAmplificationPanel from "@client/components/SkillAmplificationPanel";

function Accordion({ title, children, defaultOpen = false }: { title: string; children: () => React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      className="rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
    >
      <summary className="cursor-pointer text-xs font-medium text-slate-700 dark:text-slate-200 px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800">{title}</summary>
      <div className="px-3 pb-3">{open ? children() : null}</div>
    </details>
  );
}

export default function DrawerAudit({ data }: { data: DrawerData }) {
  return (
    <section className="space-y-3">
      <h2 className="text-[11px] uppercase tracking-wide font-semibold text-slate-500 dark:text-slate-400">Audit</h2>
      <Accordion title="Evidence">
        {() => <EvidencePanel workflowId={data.workflow.id} />}
      </Accordion>
      <Accordion title="Audit trail">
        {() => (
          <AuditTrail
            ledger={data.workflow.actionLedger as ActionLedgerEntry[]}
            blobUrl={data.auditBlobUrl ?? null}
          />
        )}
      </Accordion>
      <Accordion title="Economics">
        {() => <EconomicsPanel e={data.economics} />}
      </Accordion>
      <Accordion title="Fleet assignment">
        {() => <FleetAssignment spans={data.spans} />}
      </Accordion>
      <Accordion title="Skill amplification">
        {() => <SkillAmplificationPanel items={data.amplifications} />}
      </Accordion>
    </section>
  );
}
