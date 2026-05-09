/**
 * The Org Building (IP3, TASK-015) — cadence clock widget.
 *
 * A small analogue clock face overlaid via drei's <Html> on the
 * building's bottom-right. Three pip-marks ring the rim, one per
 * cadence (morning-sweep, period-close, quarterly-okr), positioned
 * where each cadence's next fire lands on the 12-hour dial. The hands
 * sweep at 1Hz off ``Date.now()``.
 */
import { Html } from "@react-three/drei";
import { useEffect, useState } from "react";

import type { Cadence } from "../../lib/useOrgData";

interface Props {
  cadences: Cadence[];
}

const SIZE = 120;
const CENTER = SIZE / 2;
const RADIUS = SIZE / 2 - 8;

function angleForDate(d: Date): number {
  // 12-hour dial: hour-of-day (mod 12) maps to 0..2π, with 12 at the top.
  const hours = d.getHours() % 12;
  const total = hours * 60 + d.getMinutes();
  // Subtract π/2 so 12 o'clock points up.
  return (total / 720) * Math.PI * 2 - Math.PI / 2;
}

export function CadenceClock({ cadences }: Props) {
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const hourAngle =
    ((now.getHours() % 12) + now.getMinutes() / 60) * (Math.PI * 2) / 12 -
    Math.PI / 2;
  const minAngle =
    (now.getMinutes() + now.getSeconds() / 60) * (Math.PI * 2) / 60 -
    Math.PI / 2;
  const secAngle =
    now.getSeconds() * (Math.PI * 2) / 60 - Math.PI / 2;

  const hourX = CENTER + Math.cos(hourAngle) * RADIUS * 0.5;
  const hourY = CENTER + Math.sin(hourAngle) * RADIUS * 0.5;
  const minX = CENTER + Math.cos(minAngle) * RADIUS * 0.75;
  const minY = CENTER + Math.sin(minAngle) * RADIUS * 0.75;
  const secX = CENTER + Math.cos(secAngle) * RADIUS * 0.85;
  const secY = CENTER + Math.sin(secAngle) * RADIUS * 0.85;

  // Position the widget below the lobby on the building's right side.
  // Pushed out to X=5.0 so it sits clear of the Customer Success
  // floor's facade (was overlapping at X=3.0).
  return (
    <Html
      transform={false}
      position={[5.0, 0.4, 0]}
      style={{
        pointerEvents: "none",
        transform: "translate(-50%, -50%)",
      }}
    >
      <div
        style={{
          width: SIZE,
          height: SIZE + 24,
          color: "#cfd2d6",
          fontFamily: "var(--mono-family, monospace)",
          fontSize: 9,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          textAlign: "center",
          pointerEvents: "auto",
        }}
      >
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS}
            fill="rgba(10,10,12,0.6)"
            stroke="rgba(207,210,214,0.35)"
            strokeWidth={1}
          />
          {cadences.map((cad) => {
            if (!cad.next_run_at) return null;
            const next = new Date(cad.next_run_at);
            const a = angleForDate(next);
            const cx = CENTER + Math.cos(a) * RADIUS;
            const cy = CENTER + Math.sin(a) * RADIUS;
            const tint =
              cad.name.includes("morning")
                ? "#ffd76a"
                : cad.name.includes("period")
                ? "#7faed4"
                : "#c25f9e";
            return (
              <circle
                key={cad.name}
                cx={cx}
                cy={cy}
                r={3.5}
                fill={tint}
                opacity={0.95}
              >
                <title>
                  {cad.name} — next {cad.next_run_at}
                </title>
              </circle>
            );
          })}
          <line
            x1={CENTER}
            y1={CENTER}
            x2={hourX}
            y2={hourY}
            stroke="#f5f5f7"
            strokeWidth={2}
            strokeLinecap="round"
          />
          <line
            x1={CENTER}
            y1={CENTER}
            x2={minX}
            y2={minY}
            stroke="#cfd2d6"
            strokeWidth={1.4}
            strokeLinecap="round"
          />
          <line
            x1={CENTER}
            y1={CENTER}
            x2={secX}
            y2={secY}
            stroke="#e87a5d"
            strokeWidth={0.8}
            strokeLinecap="round"
          />
          <circle cx={CENTER} cy={CENTER} r={2} fill="#f5f5f7" />
        </svg>
        <div style={{ marginTop: 4 }}>
          {now.toTimeString().slice(0, 8)}
        </div>
      </div>
    </Html>
  );
}
