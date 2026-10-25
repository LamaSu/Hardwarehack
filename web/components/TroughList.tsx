"use client";
// The 12 troughs of the reservoir in B1: name, tint and how much is in each, plus what the
// current order will draw from it (8 channels, so 8 x the per-well volume).
import { formatVolume, type Trough } from "@/lib/apothecary";

interface Props {
  troughs: Trough[];
  draws: Record<string, number>;
  selectedColumn: number;
  canAdd: boolean;
  onChange: (trough: Trough) => void;
  onAdd: (trough: number) => void;
}

export default function TroughList({ troughs, draws, selectedColumn, canAdd, onChange, onAdd }: Props) {
  return (
    <section aria-labelledby="troughs-title">
      <h2 id="troughs-title" className="section-title">Reservoir</h2>
      <p className="mb-3 text-sm text-ink-soft">12 troughs in slot B1. Name them, set what they hold, and add them to column {selectedColumn}.</p>
      <ol className="flex flex-col divide-y divide-mithril-soft rounded-lg border border-mithril bg-surface">
        {troughs.map((t) => {
          const draw = draws[String(t.trough)] ?? 0;
          const short = t.volume_ul !== null && draw > t.volume_ul;
          return (
            <li key={t.trough} className="grid grid-cols-[auto_1fr_5.5rem_auto] items-center gap-2 px-3 py-2">
              <label className="relative size-6 cursor-pointer overflow-hidden rounded-full border border-mithril" style={{ background: t.color }}
                     title="Change colour">
                <input type="color" value={t.color} onChange={(e) => onChange({ ...t, color: e.target.value })}
                       className="absolute inset-0 cursor-pointer opacity-0" aria-label={`Colour of trough ${t.trough}`} />
              </label>
              <div className="min-w-0">
                <input className="w-full truncate border-0 bg-transparent p-0 text-sm text-ink outline-none focus:underline"
                       value={t.name} maxLength={40} aria-label={`Name of trough ${t.trough}`}
                       onChange={(e) => onChange({ ...t, name: e.target.value || `Trough ${t.trough}` })} />
                <div className={`text-xs ${short ? "text-alert" : "text-ink-soft"}`}>
                  {draw > 0 ? `Order uses ${formatVolume(draw)}` : t.name === `Trough ${t.trough}` ? "Not named yet" : `Trough ${t.trough}`}
                  {short && ", more than it holds"}
                </div>
              </div>
              <label className="flex items-center gap-1 text-xs text-ink-soft">
                <input className="field px-1.5 py-1 text-right" inputMode="decimal" placeholder="mL"
                       aria-label={`Millilitres in trough ${t.trough}`}
                       value={t.volume_ul === null ? "" : Number((t.volume_ul / 1000).toPrecision(4))}
                       onChange={(e) => {
                         const ml = parseFloat(e.target.value.replace(",", "."));
                         onChange({ ...t, volume_ul: e.target.value.trim() === "" || !Number.isFinite(ml) ? null : Math.min(Math.max(ml, 0), 15) * 1000 });
                       }} />
                mL
              </label>
              <button className="btn btn-quiet text-leaf hover:text-leaf-deep" disabled={!canAdd} onClick={() => onAdd(t.trough)}
                      aria-label={`Add ${t.name} to column ${selectedColumn}`}>Add</button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
