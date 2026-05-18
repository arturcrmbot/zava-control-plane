// web/client/components/feed/cards/ReceiptThumb.tsx
//
// Receipt thumbnail extracted from the legacy reviewer-queue route during
// the Feed of Work redesign so HITLCard / ExceptionCard / ResolvedCard can
// reuse it.
import { useState } from "react";

export default function ReceiptThumb({
  claimId, flavour, size = "md",
}: {
  claimId?: string;
  flavour?: string;
  size?: "sm" | "md";
}) {
  const [errored, setErrored] = useState(false);
  const dim = size === "sm" ? "w-12 h-14" : "w-16 h-20";
  if (!claimId) {
    return (
      <div
        className={`${dim} bg-slate-100 rounded border border-slate-200 flex items-center justify-center text-[9px] text-slate-400 text-center px-1`}
        data-testid="receipt-thumb-placeholder"
      >
        no claim
      </div>
    );
  }
  if (errored || flavour === "missing-receipt") {
    return (
      <div
        className={`${dim} bg-amber-50 border border-dashed border-amber-300 rounded flex items-center justify-center text-[9px] text-amber-700 text-center px-1 leading-tight`}
        data-testid="receipt-thumb-missing"
      >
        receipt<br />missing
      </div>
    );
  }
  return (
    <img
      src={`/api/receipts/${claimId}.png`}
      alt={`receipt ${claimId}`}
      onError={() => setErrored(true)}
      className={`${dim} object-cover bg-white rounded border border-slate-200`}
    />
  );
}
