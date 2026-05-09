/**
 * The Org Building (IP4, TASK-026) — bottom-strip layer toggles.
 *
 * Floating panel anchored bottom-centre. Checkboxes for each animation
 * layer; state lifted from useLayerToggles (localStorage-backed).
 *
 * The cosmic-lens toggle already lives in ConstellationPage and is not
 * duplicated here per the task brief.
 */
import type { LayerFlags } from "../../lib/layerToggles";

interface Props {
  layers: LayerFlags;
  setLayer: (k: keyof LayerFlags, v: boolean) => void;
}

const ROWS: { key: keyof LayerFlags; label: string }[] = [
  { key: "activityHeat", label: "Activity heat" },
  { key: "entityFlows", label: "Entity flows" },
  { key: "decisionSparks", label: "Decision sparks" },
  { key: "ambientFlashes", label: "Ambient flashes" },
  { key: "cadencePulses", label: "Cadence pulses" },
  { key: "crossFunctionBeams", label: "Cross-fn beams" },
];

export function LayerToggles({ layers, setLayer }: Props) {
  return (
    <div
      className="org-building__layer-toggles"
      style={{
        position: "absolute",
        bottom: 16,
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        flexWrap: "wrap",
        gap: 10,
        padding: "8px 14px",
        background: "rgba(10,10,12,0.7)",
        border: "1px solid rgba(207,210,214,0.25)",
        borderRadius: 14,
        color: "#cfd2d6",
        fontFamily: "var(--mono-family, monospace)",
        fontSize: 11,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        zIndex: 7,
        maxWidth: "min(720px, calc(100% - 32px))",
        justifyContent: "center",
      }}
    >
      {ROWS.map((row) => (
        <label
          key={row.key}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            cursor: "pointer",
            opacity: layers[row.key] ? 1 : 0.55,
          }}
        >
          <input
            type="checkbox"
            checked={layers[row.key]}
            onChange={(e) => setLayer(row.key, e.target.checked)}
            style={{ accentColor: "#7faed4" }}
          />
          {row.label}
        </label>
      ))}
    </div>
  );
}
