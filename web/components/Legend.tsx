"use client";
import { drugColor, ROLE_COLORS } from "@/lib/colors";
import { concentrationRangeNm, drugs, formatNm, type Layout } from "@/lib/layout";

export default function Legend({ layout }: { layout: Layout }) {
  const entries = drugs(layout).filter((d) =>
    Object.values(layout.wells).some((a) => a.drug === d && (a.role === "Treatment" || a.role === "Positive control")));
  const count = (drug: string) => Object.values(layout.wells).filter((a) => a.drug === drug).length;
  const isPositiveOnly = (drug: string) => Object.values(layout.wells).every((a) => a.drug !== drug || a.role === "Positive control");
  const dot = (color: string, ring = false) => (
    <span className="inline-block size-3 rounded-full" style={ring ? { border: `3px solid ${color}` } : { background: color }} />
  );
  return (
    <div className="mt-3 flex flex-col gap-2 text-muted">
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        {entries.length === 0 && <span>No drugs assigned yet.</span>}
        {entries.map((d) => {
          const range = concentrationRangeNm(layout, d);
          return (
            <span key={d} className="flex items-center gap-2">
              {dot(drugColor(layout, d), isPositiveOnly(d))}
              <span className="text-text">{d}</span> ({count(d)})
              {range && <span>{range[0] === range[1] ? formatNm(range[0]) : `${formatNm(range[0])} – ${formatNm(range[1])}`}</span>}
            </span>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span className="flex items-center gap-2">{dot(ROLE_COLORS.vehicle)} Vehicle control</span>
        <span className="flex items-center gap-2">{dot(ROLE_COLORS.untreated)} Untreated</span>
        <span className="flex items-center gap-2">{dot("#c9ccd1", true)} Positive control</span>
        <span className="flex items-center gap-2">{dot(ROLE_COLORS.empty)} Empty</span>
      </div>
    </div>
  );
}
