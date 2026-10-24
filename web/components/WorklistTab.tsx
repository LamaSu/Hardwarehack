"use client";
// Stocks & worklist: pipetting limits, stock solutions, plan tables, materials and check.
import { useState } from "react";
import { api, download, type PlanResponse } from "@/lib/api";
import { drugColor } from "@/lib/colors";
import { UNITS, type Layout, type PlateFormat } from "@/lib/layout";
import PlanTables from "./PlanTables";

interface Props {
  layout: Layout;
  format: PlateFormat;
  stockDrugs: string[];
  onChange: (layout: Layout) => void;
  plan: PlanResponse | null;
  onPlan: (plan: PlanResponse | null) => void;
  flash: (message: string, tone?: "ok" | "warn" | "bad") => void;
}

const PIPETTING = [
  { key: "well_volume_ul", label: "Final volume / well", fallback: (f: PlateFormat) => f.default_working_volume_ul },
  { key: "min_transfer_ul", label: "Min. transfer", fallback: () => 5 }, // Studio45 pipette minimum
  { key: "intermediate_transfer_ul", label: "Intermediate transfer", fallback: () => 10 },
  { key: "dead_volume_ul", label: "Dead volume", fallback: () => 20 },
] as const;

export default function WorklistTab({ layout, format, stockDrugs, onChange, plan, onPlan, flash }: Props) {
  const [busy, setBusy] = useState(false);

  const setPipetting = (key: string, text: string) => {
    const pipetting = { ...layout.pipetting };
    const value = Number(text.replace(",", "."));
    if (text.trim() === "" || !Number.isFinite(value)) delete pipetting[key]; else pipetting[key] = value;
    onChange({ ...layout, pipetting });
  };
  const stock = (drug: string) => layout.stocks[drug] ?? { concentration: 10, unit: "mM", solvent: "DMSO" };
  const setStock = (drug: string, patch: Partial<ReturnType<typeof stock>>) =>
    onChange({ ...layout, stocks: { ...layout.stocks, [drug]: { ...stock(drug), ...patch } } });

  /** The layout with default stocks filled in for any drug that has none yet. */
  const withStocks = (): Layout => {
    const stocks = { ...layout.stocks };
    for (const drug of stockDrugs) stocks[drug] ??= stock(drug);
    return { ...layout, stocks };
  };

  const update = async () => {
    setBusy(true);
    try {
      const full = withStocks();
      onChange(full);
      const result = await api.plan(full);
      onPlan(result);
      const warnings = result.plan.assay_steps.filter((s) => s.warnings.length).length + result.plan.warnings.length;
      if (!result.check.passed) flash("Simulation check failed, see Materials", "bad");
      else if (warnings) flash(`Plan updated: ${warnings} warning(s)`, "warn");
      else flash(`Plan updated: ${result.plan.transfers.length} transfers`, "ok");
    } catch (error) {
      onPlan(null);
      flash((error as Error).message, "bad");
    } finally {
      setBusy(false);
    }
  };

  const exportCsv = async () => {
    try {
      download(`${layout.name}_transfers.csv`, await api.transfersCsv(withStocks()));
    } catch (error) {
      flash((error as Error).message, "bad");
    }
  };

  const failed = plan?.check.wells.filter((w) => !w.ok).length ?? 0;
  return (
    <div className="flex min-h-0 flex-1 gap-4">
      <div className="flex w-96 shrink-0 flex-col gap-3 overflow-auto">
        <section className="panel">
          <div className="panel-title">Pipetting <small>limits → plan</small></div>
          <div className="grid grid-cols-[1fr_6rem_2rem] items-center gap-2">
            {PIPETTING.map(({ key, label, fallback }) => (
              <label key={key} className="contents">
                <span className="text-muted">{label}</span>
                <input className="field" inputMode="decimal" placeholder={String(fallback(format))}
                       value={layout.pipetting[key] ?? ""} onChange={(e) => setPipetting(key, e.target.value)} />
                <span className="text-muted">µL</span>
              </label>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-title">Stock solutions <small>stock → well</small></div>
          {stockDrugs.length === 0 ? <p className="text-muted">Assign drugs on the plate first.</p> : (
            <div className="grid grid-cols-[1fr_4.5rem_4.5rem_5.5rem] items-center gap-2">
              <span className="text-muted">Drug</span><span className="text-muted">Stock</span><span /><span className="text-muted">Solvent</span>
              {stockDrugs.map((drug) => (
                <div key={drug} className="contents">
                  <span className="flex items-center gap-2 truncate">
                    <span className="inline-block size-2.5 shrink-0 rounded-full" style={{ background: drugColor(layout, drug) }} />{drug}
                  </span>
                  <input className="field" inputMode="decimal" aria-label={`${drug} stock concentration`}
                         value={stock(drug).concentration}
                         onChange={(e) => { const v = Number(e.target.value.replace(",", ".")); if (Number.isFinite(v)) setStock(drug, { concentration: v }); }} />
                  <select className="field" aria-label={`${drug} stock unit`} value={stock(drug).unit} onChange={(e) => setStock(drug, { unit: e.target.value })}>
                    {UNITS.map((u) => <option key={u}>{u}</option>)}
                  </select>
                  <input className="field" aria-label={`${drug} solvent`} value={stock(drug).solvent} onChange={(e) => setStock(drug, { solvent: e.target.value })} />
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="flex gap-2">
          <button className="btn btn-primary flex-1" disabled={busy} onClick={update}>{busy ? "Planning…" : "Update plan"}</button>
          <button className="btn flex-1" onClick={exportCsv}>Export transfers CSV</button>
        </div>

        <section className="panel">
          <div className="panel-title">Materials</div>
          {plan ? (
            <>
              <p className={plan.check.passed ? "mb-2 text-ok" : "mb-2 text-bad"}>
                {plan.check.passed
                  ? `✓ Simulation: all ${plan.check.wells.length} wells reach their target`
                  : `✗ Simulation: ${failed} well(s), ${plan.check.problems.length} transfer problem(s)`}
              </p>
              {plan.check.problems.map((p) => <p key={p} className="text-bad">{p}</p>)}
              {plan.materials.map((line, i) => (
                <p key={line} className={i === plan.materials.length - 1 ? "mt-1 text-muted" : ""}>{line}</p>
              ))}
            </>
          ) : <p className="text-muted">Update the plan to see what to prepare.</p>}
        </section>
      </div>
      <PlanTables plan={plan} />
    </div>
  );
}
