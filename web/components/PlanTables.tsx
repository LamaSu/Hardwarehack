"use client";
import { useState } from "react";
import type { PlanResponse } from "@/lib/api";

const ul = (v: number | null | undefined) => (v === null || v === undefined ? "" : Number(v.toPrecision(3)).toString());

export default function PlanTables({ plan }: { plan: PlanResponse | null }) {
  const [view, setView] = useState<"assay" | "intermediate" | "transfers">("assay");
  return (
    <section className="panel flex min-h-0 flex-1 flex-col">
      <div className="panel-title">
        Pipetting plan
        <div className="seg">
          <button aria-pressed={view === "assay"} onClick={() => setView("assay")}>Assay plate</button>
          <button aria-pressed={view === "intermediate"} onClick={() => setView("intermediate")}>Intermediate plate</button>
          <button aria-pressed={view === "transfers"} onClick={() => setView("transfers")}>All transfers</button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded border border-line">
        {!plan ? (
          <p className="p-4 text-muted">Press “Update plan” to compute the pipetting plan.</p>
        ) : view === "assay" ? (
          <table className="grid-table">
            <thead><tr>{["Well", "Role", "Drug", "Final", "Source", "Add µL", "Medium µL", "Solvent %", "Warnings"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>
              {plan.plan.assay_steps.map((s) => (
                <tr key={s.well} className={s.warnings.length ? "warn" : s.role !== "Treatment" ? "muted" : ""}>
                  <td>{s.well}</td><td>{s.role}</td><td>{s.liquid}</td><td>{s.target}</td><td>{s.source}</td>
                  <td>{ul(s.transfer_ul)}</td><td>{ul(s.medium_ul)}</td>
                  <td>{s.solvent_percent === null ? "" : Number(s.solvent_percent.toPrecision(2))}</td><td>{s.warnings.join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : view === "intermediate" ? (
          plan.plan.intermediates.length === 0 ? <p className="p-4 text-muted">No intermediate dilutions needed.</p> : (
            <table className="grid-table">
              <thead><tr>{["Well", "Contents", "From", "Source µL", "Medium µL", "Total µL", "Warnings"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>
                {plan.plan.intermediates.map((i) => (
                  <tr key={i.well} className={i.warnings.length ? "warn" : ""}>
                    <td>{i.well}</td><td>{i.label}</td><td>{i.source}</td><td>{ul(i.source_volume_ul)}</td>
                    <td>{ul(i.medium_volume_ul)}</td><td>{ul(i.total_volume_ul)}</td><td>{i.warnings.join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          <table className="grid-table">
            <thead><tr>{["#", "Phase", "From", "To", "µL", "Liquid"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>
              {plan.plan.transfers.map((t) => (
                <tr key={t.step} className={t.phase === "prepare" ? "muted" : ""}>
                  <td>{t.step}</td><td>{t.phase}</td><td>{t.source_labware} {t.source_well}</td>
                  <td>{t.dest_labware} {t.dest_well}</td><td>{ul(t.volume_ul)}</td><td>{t.liquid}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
