// Plate map colors: hue = drug, lightness = log concentration within the drug's range.
import { concentrationRangeNm, drugs, toNanomolar, type Layout, type WellAssignment } from "./layout";

const HUES = [28, 120, 285, 205, 350, 55, 170, 255, 0, 90];
export const ROLE_COLORS = { vehicle: "#8b9099", untreated: "#4b5361", empty: "#2e333b" };

export function drugHue(layout: Layout, drug: string): number {
  const index = drugs(layout).filter((d) => !isVehicleOnly(layout, d)).indexOf(drug);
  return HUES[(index < 0 ? 0 : index) % HUES.length];
}

function isVehicleOnly(layout: Layout, drug: string): boolean {
  return Object.values(layout.wells).every((a) => a.drug !== drug || a.role === "Vehicle control");
}

export function drugColor(layout: Layout, drug: string, lightness = 60): string {
  return `hsl(${drugHue(layout, drug)} 75% ${lightness}%)`;
}

export interface WellStyle { fill: string; ring: string | null }

export function wellStyle(layout: Layout, a: WellAssignment | undefined): WellStyle {
  if (!a) return { fill: ROLE_COLORS.empty, ring: null };
  if (a.role === "Untreated") return { fill: ROLE_COLORS.untreated, ring: null };
  if (a.role === "Vehicle control") return { fill: ROLE_COLORS.vehicle, ring: null };
  let lightness = 60;
  const range = a.drug ? concentrationRangeNm(layout, a.drug) : null;
  if (range && a.concentration && range[1] > range[0]) {
    const t = (Math.log10(toNanomolar(a.concentration, a.unit)) - Math.log10(range[0])) /
      (Math.log10(range[1]) - Math.log10(range[0]));
    lightness = 28 + 34 * t; // dark = low dose, bright = high dose
  }
  const color = drugColor(layout, a.drug, lightness);
  return a.role === "Positive control" ? { fill: "#15181d", ring: color } : { fill: color, ring: null };
}
