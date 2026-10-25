"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { orderable, type ConsoleState, type PlanResult, type Recipe, type Trough } from "@/lib/apothecary";
import { api } from "@/lib/api";
import OrderPanel from "./OrderPanel";
import PlateView from "./PlateView";
import RecipeEditor from "./RecipeEditor";
import RobotControl from "./RobotControl";
import TroughList from "./TroughList";
import WizardMark from "./WizardMark";

type Drafts = Record<number, Recipe>;
const ACTIVE = new Set(["idle", "running", "paused", "finishing", "stop-requested", "awaiting-recovery"]);

// Per-viewer conveniences only; the order itself is checked by the API.
const store = {
  get<T>(key: string, fallback: T): T {
    try { const v = localStorage.getItem(key); return v ? (JSON.parse(v) as T) : fallback; } catch { return fallback; }
  },
  set(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ } },
};

export default function Console() {
  // Rendered only in the browser (see ClientConsole), so saved drafts can be read up front.
  const [plate, setPlate] = useState(() => store.get("athelas.plate", "Batch 1"));
  const [state, setState] = useState<ConsoleState | null>(null);
  const [drafts, setDrafts] = useState<Drafts>(() => store.get(`athelas.drafts.${store.get("athelas.plate", "Batch 1")}`, {}));
  const [selected, setSelected] = useState(1);
  const [plan, setPlan] = useState<(PlanResult & { key: string }) | null>(null);
  const [brewing, setBrewing] = useState(false);
  const [justBrewed, setJustBrewed] = useState<number[]>([]);
  const [run, setRun] = useState<{ id: string; status: string; errors: string[] } | null>(null);
  const [message, setMessage] = useState<{ text: string; bad: boolean } | null>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);
  const troughSave = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      setState(await api.state(plate));
    } catch (e) {
      setMessage({ text: (e as Error).message, bad: true });
    }
  }, [plate]);
  useEffect(() => {
    api.state(plate).then((s) => { setState(s); setMessage(null); })
      .catch((e: Error) => setMessage({ text: e.message, bad: true }));
  }, [plate]);

  const recipes = useMemo(() => orderable(drafts).filter((r) => !state?.columns[String(r.column)]), [drafts, state]);

  // Check the order with the API (rules + simulator) shortly after each edit. Each result carries the
  // order it was checked for, so a check of an older version of the order never enables Brew.
  const orderKey = useMemo(() => JSON.stringify({ plate, recipes, tips: state?.tips, troughs: state?.troughs }), [plate, recipes, state]);
  useEffect(() => {
    if (recipes.length === 0) return;
    const timer = setTimeout(() => {
      api.plan(plate, recipes).then((result) => setPlan({ ...result, key: orderKey }))
        .catch((e: Error) => setMessage({ text: e.message, bad: true }));
    }, 500);
    return () => clearTimeout(timer);
  }, [orderKey, plate, recipes]);
  const currentPlan = recipes.length > 0 && plan?.key === orderKey ? plan : null;
  const planning = recipes.length > 0 && currentPlan === null;

  const editDrafts = (next: Drafts) => { setDrafts(next); store.set(`athelas.drafts.${plate}`, next); };
  const recipeFor = (column: number): Recipe => drafts[column] ?? { column, name: "", ingredients: [] };

  const editTrough = (trough: Trough) => {
    if (!state) return;
    const troughs = state.troughs.map((t) => (t.trough === trough.trough ? trough : t));
    setState({ ...state, troughs });
    if (troughSave.current) clearTimeout(troughSave.current);
    troughSave.current = setTimeout(() => {
      api.saveTroughs(troughs).catch((e: Error) => setMessage({ text: e.message, bad: true }));
    }, 500);
  };

  const stopPolling = () => { if (poll.current) clearInterval(poll.current); poll.current = null; };
  useEffect(() => stopPolling, []);
  const follow = (id: string) => {
    stopPolling();
    poll.current = setInterval(async () => {
      try {
        const status = await api.runStatus(id);
        setRun(status);
        if (!ACTIVE.has(status.status)) stopPolling();
      } catch (e) { setMessage({ text: (e as Error).message, bad: true }); stopPolling(); }
    }, 2000);
  };

  const brew = async () => {
    if (!state) return;
    const where = state.robot.mock ? "the mock robot" : `the robot at ${state.robot.host}`;
    const columns = recipes.map((r) => r.column);
    if (!window.confirm(`Brew column${columns.length === 1 ? "" : "s"} ${columns.join(", ")} on ${where}?\n\nCheck the reservoir, tip racks and plate are loaded.`)) return;
    setBrewing(true);
    try {
      const result = await api.brew(plate, recipes);
      const next = { ...drafts };
      columns.forEach((c) => delete next[c]);
      editDrafts(next);
      setJustBrewed(columns);
      setTimeout(() => setJustBrewed([]), 900 + columns.length * 140);
      setRun({ id: result.run_id, status: "running", errors: [] });
      follow(result.run_id);
      setMessage({ text: `Brewing ${columns.length} column${columns.length === 1 ? "" : "s"}: ${result.steps} steps.`, bad: false });
      await load();
    } catch (e) {
      setMessage({ text: (e as Error).message, bad: true });
    } finally {
      setBrewing(false);
    }
  };

  const changePlate = (name: string) => {
    setPlate(name);
    store.set("athelas.plate", name);
    setDrafts(store.get(`athelas.drafts.${name}`, {}));
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-[1400px] flex-col px-4 sm:px-8">
      <header className="flex flex-wrap items-center gap-4 border-b border-mithril py-4">
        <WizardMark size={36} />
        <div className="mr-auto">
          <div className="font-[family-name:var(--font-display)] text-2xl leading-none">Athelas Apothecary</div>
          <div className="text-sm text-ink-soft">Concoctions on demand, mixed by an Opentrons Flex</div>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-soft">
          Plate
          <input className="field w-40" value={plate} maxLength={80} aria-label="Plate name"
                 onChange={(e) => changePlate(e.target.value || "Batch 1")} />
        </label>
        <RobotControl onChange={load} />
      </header>

      {message && (
        <p role="status" className={`mt-4 rounded-md px-3 py-2 text-sm ${message.bad ? "bg-alert-wash text-alert" : "bg-leaf-wash text-leaf-deep"}`}>
          {message.text}
        </p>
      )}

      {!state ? (
        <p className="py-16 text-ink-soft">Loading the console…</p>
      ) : (
        <main className="grid flex-1 gap-8 py-6 lg:grid-cols-[22rem_1fr]">
          <TroughList troughs={state.troughs} draws={currentPlan?.summary.trough_draw_ul ?? {}} selectedColumn={selected}
                      canAdd={!state.columns[String(selected)]}
                      onChange={editTrough}
                      onAdd={(trough) => {
                        const recipe = recipeFor(selected);
                        editDrafts({ ...drafts, [selected]: { ...recipe, ingredients: [...recipe.ingredients, { trough, volume_ul: 10 }] } });
                      }} />
          <div className="flex min-w-0 flex-col gap-6">
            <section aria-labelledby="plate-title">
              <div className="mb-2 flex items-baseline justify-between gap-4">
                <h1 id="plate-title" className="font-[family-name:var(--font-display)] text-3xl">{plate}</h1>
                <span className="text-sm text-ink-soft">Armadillo 96-well PCR plate, slot B3</span>
              </div>
              <PlateView troughs={state.troughs} drafts={drafts} brewed={state.columns} selected={selected}
                         justBrewed={justBrewed} onSelect={setSelected} />
            </section>
            <div className="grid gap-8 xl:grid-cols-[1fr_20rem]">
              <RecipeEditor column={selected} recipe={recipeFor(selected)} brewed={state.columns[String(selected)]}
                            troughs={state.troughs} onChange={(recipe) => editDrafts({ ...drafts, [selected]: recipe })} />
              <OrderPanel recipes={recipes} plan={currentPlan} planning={planning} state={state} brewing={brewing} run={run}
                          onBrew={brew}
                          onRunAction={async (action) => {
                            if (!run) return;
                            try { await api.runAction(run.id, action); follow(run.id); } catch (e) { setMessage({ text: (e as Error).message, bad: true }); }
                          }}
                          onTipsRefilled={async () => {
                            if (!window.confirm("Mark both tip racks (A1 and A2) as full again?")) return;
                            await api.tipsRefilled(); await load();
                          }}
                          onNewPlate={async () => {
                            if (!window.confirm(`Start a fresh plate as "${plate}"? Its brewed columns are forgotten.`)) return;
                            await api.clearPlate(plate); await load();
                          }} />
            </div>
          </div>
        </main>
      )}
    </div>
  );
}
