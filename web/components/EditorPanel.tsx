"use client";
// Right-hand panel of the plate editor: selection summary, assign wells, dose series.
import { useState } from "react";
import { ROLES, UNITS, type Role } from "@/lib/layout";
import { compareWells } from "@/lib/wells";

interface Props {
  selection: Set<string>;
  knownDrugs: string[];
  onSelectAll: () => void;
  onClear: () => void;
  onAssign: (role: Role, drug: string, concentration: number | null, unit: string) => void;
  onEmpty: () => void;
  onDoseSeries: (role: Role, drug: string, top: number, unit: string, factor: number, direction: "row" | "column") => void;
  onError: (message: string) => void;
}

export default function EditorPanel(props: Props) {
  const { selection, knownDrugs } = props;
  const [role, setRole] = useState<Role>("Treatment");
  const [drug, setDrug] = useState("");
  const [conc, setConc] = useState("1");
  const [unit, setUnit] = useState("µM");
  const [top, setTop] = useState("10");
  const [topUnit, setTopUnit] = useState("µM");
  const [factor, setFactor] = useState("3");
  const [direction, setDirection] = useState<"row" | "column">("row");

  const sorted = [...selection].sort(compareWells);
  const needsDrug = role === "Treatment" || role === "Positive control" || role === "Vehicle control";
  const number = (text: string) => (text.trim() === "" ? NaN : Number(text.replace(",", ".")));

  const assign = () => {
    if (!selection.size) return props.onError("Select wells first");
    if (role === "Untreated") return props.onAssign(role, "", null, unit);
    if (!drug.trim()) return props.onError(role === "Vehicle control" ? "Enter the solvent, e.g. DMSO" : "Enter a drug name");
    if (role === "Vehicle control") return props.onAssign(role, drug.trim(), null, unit);
    const value = number(conc);
    if (!(value > 0)) return props.onError("Final concentration must be a positive number");
    props.onAssign(role, drug.trim(), value, unit);
  };

  const series = () => {
    if (!selection.size) return props.onError("Select wells first");
    if (!drug.trim()) return props.onError("Enter a drug name");
    const topValue = number(top);
    const factorValue = number(factor);
    if (!(topValue > 0)) return props.onError("Top concentration must be a positive number");
    if (!(factorValue > 1)) return props.onError("Dilution factor must be greater than 1");
    props.onDoseSeries(role === "Untreated" || role === "Vehicle control" ? "Treatment" : role, drug.trim(), topValue, topUnit, factorValue, direction);
  };

  return (
    <div className="flex w-80 shrink-0 flex-col gap-3">
      <section className="panel">
        <div className="panel-title">Selection</div>
        <div className="mb-3 min-h-10 text-muted">
          {selection.size ? (
            <>
              <div className="text-text">{selection.size} well{selection.size === 1 ? "" : "s"} selected</div>
              <div className="truncate">{sorted.slice(0, 6).join(", ")}{sorted.length > 6 ? " …" : ""}</div>
            </>
          ) : "Click or drag on the plate. Shift or Ctrl/⌘ adds."}
        </div>
        <div className="flex gap-2">
          <button className="btn flex-1" onClick={props.onSelectAll}>Select all</button>
          <button className="btn flex-1" onClick={props.onClear}>Clear</button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">Assign wells <small>drug → wells</small></div>
        <div className="grid grid-cols-[6rem_1fr] items-center gap-2">
          <label htmlFor="role" className="text-muted">Role</label>
          <select id="role" className="field" value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => <option key={r}>{r}</option>)}
          </select>
          <label htmlFor="drug" className="text-muted">{role === "Vehicle control" ? "Solvent" : "Drug"}</label>
          <input id="drug" className="field" list="drug-names" value={drug} disabled={!needsDrug}
                 placeholder={role === "Vehicle control" ? "DMSO" : "e.g. Erastin"} onChange={(e) => setDrug(e.target.value)} />
          <datalist id="drug-names">{knownDrugs.map((d) => <option key={d} value={d} />)}</datalist>
          <label htmlFor="conc" className="text-muted">Final conc.</label>
          <div className="flex gap-2">
            <input id="conc" className="field w-full" value={conc} disabled={role === "Untreated" || role === "Vehicle control"}
                   inputMode="decimal" onChange={(e) => setConc(e.target.value)} />
            <select className="field" value={unit} onChange={(e) => setUnit(e.target.value)} aria-label="Unit">
              {UNITS.map((u) => <option key={u}>{u}</option>)}
            </select>
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <button className="btn btn-primary flex-1" onClick={assign}>Assign to selection</button>
          <button className="btn" onClick={props.onEmpty} title="Delete key">Empty wells</button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">Dose series <small>top → serial</small></div>
        <p className="mb-3 text-muted">Uses the drug and role above. Each row (or column) of the selection becomes one series.</p>
        <div className="grid grid-cols-[6rem_1fr] items-center gap-2">
          <label htmlFor="top" className="text-muted">Top conc.</label>
          <div className="flex gap-2">
            <input id="top" className="field w-full" value={top} inputMode="decimal" onChange={(e) => setTop(e.target.value)} />
            <select className="field" value={topUnit} onChange={(e) => setTopUnit(e.target.value)} aria-label="Top unit">
              {UNITS.map((u) => <option key={u}>{u}</option>)}
            </select>
          </div>
          <label htmlFor="factor" className="text-muted">Dilution factor</label>
          <input id="factor" className="field" value={factor} inputMode="decimal" onChange={(e) => setFactor(e.target.value)} />
        </div>
        <div className="seg mt-3">
          <button className="flex-1" aria-pressed={direction === "row"} onClick={() => setDirection("row")}>Along rows</button>
          <button className="flex-1" aria-pressed={direction === "column"} onClick={() => setDirection("column")}>Down columns</button>
        </div>
        <button className="btn btn-primary mt-3 w-full" onClick={series}>Apply series to selection</button>
      </section>
    </div>
  );
}
