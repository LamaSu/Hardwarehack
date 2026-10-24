"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, download, type PlanResponse } from "@/lib/api";
import {
  allWells, applyDoseSeries, assign, changeFormat, clearWells, drugs, emptyLayout, layoutCsv, wellsOutside,
  type Layout, type PlateFormat, type Role,
} from "@/lib/layout";
import EditorPanel from "./EditorPanel";
import Header from "./Header";
import Legend from "./Legend";
import PlateMap from "./PlateMap";
import RobotPanel from "./RobotPanel";
import WorklistTab from "./WorklistTab";

type Tab = "layout" | "worklist" | "robot";
type Tone = "ok" | "warn" | "bad" | "muted";

export default function App() {
  const [formats, setFormats] = useState<PlateFormat[]>([]);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [layout, setLayout] = useState<Layout>(() => emptyLayout());
  const [selection, setSelection] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("layout");
  const [dirty, setDirty] = useState(false);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [message, setMessage] = useState<{ text: string; tone: Tone } | null>(null);
  const [openList, setOpenList] = useState<{ slug: string; name: string }[] | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flash = useCallback((text: string, tone: Tone = "muted") => {
    setMessage({ text, tone });
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setMessage(null), tone === "bad" ? 8000 : 4000);
  }, []);

  useEffect(() => {
    api.formats().then(setFormats).catch((e: Error) => setBackendError(e.message));
  }, []);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const format = formats.find((f) => f.name === layout.format);
  const edit = useCallback((next: Layout, keepPlan = false) => {
    setLayout(next);
    setDirty(true);
    if (!keepPlan) setPlan(null);
  }, []);

  const confirmDiscard = () => !dirty || window.confirm("Discard unsaved changes?");

  const selectAll = useCallback(() => { if (format) setSelection(new Set(allWells(format))); }, [format]);
  const empty = useCallback(() => {
    if (!selection.size) return flash("Select wells first", "warn");
    edit(clearWells(layout, selection));
    flash(`Emptied ${selection.size} well(s)`);
  }, [selection, layout, edit, flash]);

  const save = async () => {
    try {
      const { slug } = await api.saveLayout(layout);
      setDirty(false);
      flash(`Saved as runs/${slug}/layout.json`, "ok");
    } catch (e) {
      flash((e as Error).message, "bad");
    }
  };

  // Delete empties the selection, Ctrl/⌘+A selects all; not while typing in a field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (tab !== "layout" || ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); empty(); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") { e.preventDefault(); selectAll(); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); void save(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const load = (next: Layout) => {
    setLayout({ ...emptyLayout(), ...next });
    setSelection(new Set());
    setPlan(null);
    setDirty(false);
    setOpenList(null);
    flash(`Opened ${next.name}`, "ok");
  };

  const open = async () => {
    if (!confirmDiscard()) return;
    try { setOpenList(await api.layouts()); } catch (e) { flash((e as Error).message, "bad"); }
  };

  const uploadFile = async (file: File) => {
    try {
      const data = JSON.parse(await file.text()) as Layout;
      if (!data.format || !data.wells) throw new Error("not a layout file");
      load(data);
    } catch (e) {
      flash(`Could not open ${file.name}: ${(e as Error).message}`, "bad");
    }
  };

  const switchFormat = (next: PlateFormat) => {
    if (next.name === layout.format) return;
    const dropped = wellsOutside(layout, next.rows, next.columns);
    if (dropped.length && !window.confirm(`${dropped.length} assigned well(s) don't exist on a ${next.name} plate and will be removed. Continue?`)) return;
    edit(changeFormat(layout, next));
    setSelection(new Set());
    if (next.flex_note) flash(next.flex_note, "warn");
  };

  const knownDrugs = useMemo(() => drugs(layout), [layout]);
  const stockDrugs = useMemo(() => knownDrugs.filter((d) =>
    Object.values(layout.wells).some((a) => a.drug === d && (a.role === "Treatment" || a.role === "Positive control"))), [knownDrugs, layout]);
  const assigned = Object.keys(layout.wells).length;
  const hoverText = hover ? `${hover} · ${layout.wells[hover] ? describe(layout.wells[hover]) : "empty"}` : " ";

  if (backendError) {
    return (
      <main className="mx-auto mt-24 max-w-xl panel">
        <h1 className="mb-2 text-bad">Backend not reachable</h1>
        <p className="mb-3 text-muted">{backendError}</p>
        <pre className="rounded bg-field p-3">cd drug-screen-platform{"\n"}uv run python scripts/serve.py</pre>
        <button className="btn mt-4" onClick={() => location.reload()}>Retry</button>
      </main>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <Header
        name={layout.name} formats={formats} format={layout.format} dirty={dirty}
        onName={(name) => edit({ ...layout, name }, true)}
        onFormat={switchFormat}
        onNew={() => { if (confirmDiscard()) { load(emptyLayout(layout.format)); setDirty(false); } }}
        onOpen={open}
        onSave={save}
        onExportCsv={() => format && download(`${layout.name}_layout.csv`, layoutCsv(layout, format))}
      />
      <nav className="seg mx-6 mt-4 w-fit">
        {([["layout", "Plate layout"], ["worklist", "Stocks & worklist"], ["robot", "Robot"]] as const).map(([id, label]) => (
          <button key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>

      <main className="flex min-h-0 flex-1 gap-4 px-6 py-4">
        {!format ? <p className="text-muted">Loading…</p> : tab === "layout" ? (
          <>
            <section className="panel flex min-w-0 flex-1 flex-col overflow-auto">
              <PlateMap layout={layout} format={format} selection={selection} onSelect={setSelection} onHover={setHover} />
              <p className="mt-3 text-text">{hoverText}</p>
              <Legend layout={layout} />
            </section>
            <EditorPanel
              selection={selection}
              knownDrugs={knownDrugs}
              onSelectAll={selectAll}
              onClear={() => setSelection(new Set())}
              onEmpty={empty}
              onError={(m) => flash(m, "warn")}
              onAssign={(role: Role, drug, concentration, unit) => {
                edit(assign(layout, selection, { role, drug, concentration, unit }));
                flash(`Assigned ${selection.size} well(s)`, "ok");
              }}
              onDoseSeries={(role, drug, top, unit, factor, direction) => {
                edit(applyDoseSeries(layout, selection, drug, top, unit, factor, direction, role));
                flash(`Dose series applied to ${selection.size} well(s)`, "ok");
              }}
            />
          </>
        ) : tab === "worklist" ? (
          <WorklistTab layout={layout} format={format} stockDrugs={stockDrugs} onChange={(l) => edit(l, true)}
                       plan={plan} onPlan={setPlan} flash={flash} />
        ) : (
          <RobotPanel key={layout.name} layout={layout} flash={flash} />
        )}
      </main>

      <footer className="flex justify-between border-t border-line px-6 py-2 text-muted">
        <span>{assigned} / {format?.well_count ?? "?"} wells assigned · {stockDrugs.length} drug(s) · {format?.opentrons_load_name ?? "no Flex labware"}</span>
        {message && <span className={{ ok: "text-ok", warn: "text-warn", bad: "text-bad", muted: "text-muted" }[message.tone]}>{message.text}</span>}
      </footer>

      {openList && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/60" onClick={() => setOpenList(null)}>
          <div className="panel w-96" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Open layout">
            <div className="panel-title">Open layout <small>runs/</small></div>
            {openList.length === 0 && <p className="mb-3 text-muted">No saved layouts yet.</p>}
            <ul className="mb-3 flex max-h-72 flex-col gap-1 overflow-auto">
              {openList.map((item) => (
                <li key={item.slug}>
                  <button className="btn w-full text-left" onClick={async () => {
                    try { load(await api.loadLayout(item.slug)); } catch (e) { flash((e as Error).message, "bad"); }
                  }}>{item.name}</button>
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <button className="btn flex-1" onClick={() => fileInput.current?.click()}>From file…</button>
              <button className="btn" onClick={() => setOpenList(null)}>Cancel</button>
            </div>
            <input ref={fileInput} type="file" accept=".json,application/json" hidden
                   onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadFile(f); e.target.value = ""; }} />
          </div>
        </div>
      )}
    </div>
  );
}

function describe(a: { role: string; drug: string; concentration: number | null; unit: string }): string {
  const parts = [a.drug || "—"];
  if (a.concentration !== null) parts.push(`${a.concentration} ${a.unit}`);
  if (a.role !== "Treatment") parts.push(`(${a.role})`);
  return parts.join(" · ");
}
