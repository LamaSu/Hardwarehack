// Types and pure helpers for the concoction console. The API is the source of truth for rules;
// these helpers only drive what the screen shows while someone edits.

export const COLUMNS = 12;
export const WELL_CAPACITY_UL = 200;
export const MIN_DRAW_UL = 5;

export interface Trough { trough: number; name: string; color: string; volume_ul: number | null }
export interface Ingredient { trough: number; volume_ul: number }
export interface Recipe { column: number; name: string; ingredients: Ingredient[] }
export interface Brewed { name: string; ingredients: Ingredient[]; brewed: string; run_id: string }
export interface ConsoleState {
  troughs: Trough[];
  tips: { small_next: number; large_next: number; small_left: number; large_left: number };
  columns: Record<string, Brewed>;
  robot: { host: string; mock: boolean };
  calibrated: boolean;
}
export interface PlanResult {
  problems: string[];
  summary: { small_tips: number; large_tips: number; trough_draw_ul: Record<string, number>; column_totals: Record<string, number> };
  simulation: { ok: boolean; steps: number; error: string } | null;
}

export const total = (ingredients: Ingredient[]) => ingredients.reduce((sum, i) => sum + (i.volume_ul || 0), 0);

/** Recipes worth sending: ones with at least one ingredient. */
export const orderable = (drafts: Record<number, Recipe>) =>
  Object.values(drafts).filter((r) => r.ingredients.length > 0).sort((a, b) => a.column - b.column);

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Colour of the mixed liquid: the trough tints averaged by volume. */
export function blend(ingredients: Ingredient[], troughs: Trough[]): string | null {
  const sum = total(ingredients);
  if (sum <= 0) return null;
  const rgb = [0, 0, 0];
  for (const i of ingredients) {
    const tint = troughs.find((t) => t.trough === i.trough)?.color ?? "#999999";
    hexToRgb(tint).forEach((v, k) => (rgb[k] += (v * i.volume_ul) / sum));
  }
  return `#${rgb.map((v) => Math.round(v).toString(16).padStart(2, "0")).join("")}`;
}

/** µL as a short readable string: 1250 -> "1.25 mL", 40 -> "40 µL". */
export function formatVolume(ul: number | null | undefined): string {
  if (ul === null || ul === undefined) return "not set";
  return ul >= 1000 ? `${Number((ul / 1000).toPrecision(3))} mL` : `${Number(ul.toPrecision(3))} µL`;
}
