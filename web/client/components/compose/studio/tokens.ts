import type { ComponentType } from "react";
import { Database, Sparkles, Wrench, UserRound, ShieldCheck } from "lucide-react";
import type { Component, StepKind } from "./types";

// Per component-type palette. Cool hues (blue/violet) intentionally collapse to
// amber in dark mode via the repo's Tailwind remap (web/client/styles.css);
// emerald/rose/amber are semantic and survive. This matches the approved mock.
export type Palette = {
  label: string;
  icon: ComponentType<{ size?: number | string; className?: string }>;
  text: string;
  bg: string;
  borderL: string;
  softBg: string;
};

const ENTITY: Palette = {
  label: "Entity", icon: Database,
  text: "text-emerald-600 dark:text-emerald-400",
  bg: "bg-emerald-50 dark:bg-emerald-950/30",
  softBg: "bg-emerald-50/60 dark:bg-emerald-950/20",
  borderL: "border-l-emerald-500",
};
const SKILL: Palette = {
  label: "Skill", icon: Sparkles,
  text: "text-violet-600 dark:text-violet-400",
  bg: "bg-violet-50 dark:bg-violet-950/30",
  softBg: "bg-violet-50/60 dark:bg-violet-950/20",
  borderL: "border-l-violet-500",
};
const TOOL: Palette = {
  label: "Tool", icon: Wrench,
  text: "text-blue-600 dark:text-blue-400",
  bg: "bg-blue-50 dark:bg-blue-950/30",
  softBg: "bg-blue-50/60 dark:bg-blue-950/20",
  borderL: "border-l-blue-500",
};
const PERSONA: Palette = {
  label: "Persona", icon: UserRound,
  text: "text-amber-600 dark:text-amber-400",
  bg: "bg-amber-50 dark:bg-amber-950/30",
  softBg: "bg-amber-50/60 dark:bg-amber-950/20",
  borderL: "border-l-amber-500",
};
const AUTHORITY: Palette = {
  label: "Authority · AGT", icon: ShieldCheck,
  text: "text-rose-600 dark:text-rose-400",
  bg: "bg-rose-50 dark:bg-rose-950/30",
  softBg: "bg-rose-50/60 dark:bg-rose-950/20",
  borderL: "border-l-rose-500",
};

export function paletteFor(type: Component["type"]): Palette {
  switch (type) {
    case "entity": return ENTITY;
    case "skill": return SKILL;
    case "tool": return TOOL;
    case "persona": return PERSONA;
    case "authority": return AUTHORITY;
  }
}

// Step chip palette by kind (surface flow, before you drill in).
export function stepPalette(kind: StepKind): Palette {
  if (kind === "hitl") return PERSONA;
  if (kind === "agent") return SKILL;
  return TOOL; // deterministic
}

export function laneLabel(kind: StepKind): string {
  if (kind === "hitl") return "human sign-off";
  if (kind === "agent") return "analysis";
  return "automatic";
}
