"use client";
import type { PlateFormat } from "@/lib/layout";

interface Props {
  name: string;
  formats: PlateFormat[];
  format: string;
  dirty: boolean;
  onName: (name: string) => void;
  onFormat: (format: PlateFormat) => void;
  onNew: () => void;
  onOpen: () => void;
  onSave: () => void;
  onExportCsv: () => void;
}

export default function Header(p: Props) {
  return (
    <header className="flex flex-col gap-4 px-6 pt-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-text">Drug Screen Designer{p.dirty && <span className="text-muted"> •</span>}</h1>
          <p className="text-muted">plate layout → worklist → Opentrons Flex</p>
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={p.onNew}>New</button>
          <button className="btn" onClick={p.onOpen}>Open…</button>
          <button className="btn" onClick={p.onSave}>Save</button>
          <button className="btn" onClick={p.onExportCsv}>Export layout CSV</button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-6">
        <label className="flex items-center gap-3">
          <span className="text-muted">Plate name</span>
          <input className="field w-64" value={p.name} onChange={(e) => p.onName(e.target.value)} />
        </label>
        <div className="flex items-center gap-3">
          <span className="text-muted">Format</span>
          <div className="seg">
            {p.formats.map((f) => (
              <button key={f.name} aria-pressed={f.name === p.format} onClick={() => p.onFormat(f)} title={f.flex_note ?? f.opentrons_load_name ?? ""}>
                {f.well_count}
              </button>
            ))}
          </div>
          <span className="text-muted">wells</span>
        </div>
      </div>
    </header>
  );
}
