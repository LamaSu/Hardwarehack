// Plate layout model, same JSON shape as PlateLayout.to_dict() in Python.
import { compareWells, parseWell, wellName } from "./wells";

export const ROLES = ["Treatment", "Vehicle control", "Positive control", "Untreated"] as const;
export type Role = (typeof ROLES)[number];
export const UNITS = ["M", "mM", "µM", "nM"] as const;
export type Unit = (typeof UNITS)[number];
const TO_NM: Record<string, number> = { M: 1e9, mM: 1e6, µM: 1e3, nM: 1 };

export interface PlateFormat {
  name: string;
  rows: number;
  columns: number;
  max_volume_ul: number;
  default_working_volume_ul: number;
  opentrons_load_name: string | null;
  well_count: number;
  flex_note: string | null;
}

export interface WellAssignment {
  role: Role;
  drug: string;
  concentration: number | null;
  unit: string;
}

export interface StockSolution {
  concentration: number;
  unit: string;
  solvent: string;
}

export interface Layout {
  version?: number;
  name: string;
  format: string;
  saved?: string;
  wells: Record<string, WellAssignment>;
  stocks: Record<string, StockSolution>;
  pipetting: Record<string, number>;
}

export function emptyLayout(format = "96-well", name = "Untitled plate"): Layout {
  return { version: 1, name, format, wells: {}, stocks: {}, pipetting: {} };
}

export function toNanomolar(value: number, unit: string): number {
  const factor = TO_NM[unit];
  if (factor === undefined) throw new Error(`Unknown unit: ${unit}`);
  return value * factor;
}

export function assign(layout: Layout, wells: Iterable<string>, a: WellAssignment): Layout {
  const next = { ...layout.wells };
  for (const well of wells) next[well] = { ...a };
  return { ...layout, wells: next };
}

export function clearWells(layout: Layout, wells: Iterable<string>): Layout {
  const next = { ...layout.wells };
  for (const well of wells) delete next[well];
  return { ...layout, wells: next };
}

/** Port of PlateLayout.apply_dose_series: each row (or column) is one series, highest dose first. */
export function applyDoseSeries(
  layout: Layout,
  wells: Iterable<string>,
  drug: string,
  top: number,
  unit: string,
  factor: number,
  direction: "row" | "column" = "row",
  role: Role = "Treatment",
): Layout {
  if (!(factor > 1)) throw new Error("Dilution factor must be > 1");
  const groups = new Map<number, [number, string][]>();
  for (const well of wells) {
    const [row, col] = parseWell(well);
    const [key, position] = direction === "row" ? [row, col] : [col, row];
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push([position, well]);
  }
  const next = { ...layout.wells };
  for (const members of groups.values()) {
    members.sort((a, b) => a[0] - b[0]);
    members.forEach(([, well], step) => {
      const concentration = Number((top / factor ** step).toPrecision(4));
      next[well] = { role, drug, concentration, unit };
    });
  }
  return { ...layout, wells: next };
}

/** Distinct drug names in order of first appearance (row-wise). */
export function drugs(layout: Layout): string[] {
  const seen: string[] = [];
  for (const well of Object.keys(layout.wells).sort(compareWells)) {
    const drug = layout.wells[well].drug;
    if (drug && !seen.includes(drug)) seen.push(drug);
  }
  return seen;
}

export function concentrationRangeNm(layout: Layout, drug: string): [number, number] | null {
  const values = Object.values(layout.wells)
    .filter((a) => a.drug === drug && a.concentration)
    .map((a) => toNanomolar(a.concentration!, a.unit));
  return values.length ? [Math.min(...values), Math.max(...values)] : null;
}

/** Wells that would be dropped when switching to a plate with `rows` x `columns`. */
export function wellsOutside(layout: Layout, rows: number, columns: number): string[] {
  return Object.keys(layout.wells).filter((w) => {
    const [r, c] = parseWell(w);
    return r >= rows || c >= columns;
  });
}

export function changeFormat(layout: Layout, format: PlateFormat): Layout {
  const dropped = new Set(wellsOutside(layout, format.rows, format.columns));
  const wells = Object.fromEntries(Object.entries(layout.wells).filter(([w]) => !dropped.has(w)));
  return { ...layout, format: format.name, wells };
}

export function allWells(format: PlateFormat): string[] {
  const wells: string[] = [];
  for (let r = 0; r < format.rows; r++) for (let c = 0; c < format.columns; c++) wells.push(wellName(r, c));
  return wells;
}

export function formatNm(valueNm: number): string {
  const fmt = (v: number) => Number(v.toPrecision(3)).toString();
  if (valueNm >= 1e6) return `${fmt(valueNm / 1e6)} mM`;
  if (valueNm >= 1e3) return `${fmt(valueNm / 1e3)} µM`;
  return `${fmt(valueNm)} nM`;
}

export function layoutCsv(layout: Layout, format: PlateFormat): string {
  const lines = ["well,role,drug,concentration,unit"];
  for (const well of allWells(format)) {
    const a = layout.wells[well];
    const cell = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    lines.push(a ? [well, a.role, cell(a.drug), a.concentration ?? "", a.unit].join(",") : `${well},Empty,,,`);
  }
  return lines.join("\n") + "\n";
}
