"use client";
// Robot tab: connection, protocol generation (with simulation), before/after camera, run control.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, fileUrl, type ProtocolResponse, type RobotConfig, type RunStatus } from "@/lib/api";
import type { Layout } from "@/lib/layout";

interface Props {
  layout: Layout;
  flash: (message: string, tone?: "ok" | "warn" | "bad") => void;
}

const ACTIVE = new Set(["idle", "running", "paused", "finishing", "stop-requested", "awaiting-recovery"]);
type Tag = "before" | "after";

export default function RobotPanel({ layout, flash }: Props) {
  const [config, setConfig] = useState<RobotConfig>({ host: "", port: 31950, mock: false });
  const [health, setHealth] = useState<{ ok: boolean; text: string } | null>(null);
  const [protocol, setProtocol] = useState<ProtocolResponse | null>(null);
  const [images, setImages] = useState<Record<Tag, string | null>>({ before: null, after: null });
  const [run, setRun] = useState<RunStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showSource, setShowSource] = useState(false);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const h = await api.health();
      setHealth({ ok: true, text: `${h.name ?? "robot"} · ${h.robot_model ?? ""} · software ${h.api_version ?? "?"}` });
    } catch (error) {
      setHealth({ ok: false, text: (error as Error).message });
    }
  }, []);

  useEffect(() => {
    api.robotConfig().then((c) => { setConfig(c); if (c.host || c.mock) void checkHealth(); }).catch(() => {});
  }, [checkHealth]);

  // Show snapshots and the last run already on disk for this plate.
  useEffect(() => {
    api.runFiles(layout.name).then((info) => {
      const stamp = Date.now();
      setImages({
        before: info.files.includes("before.jpg") ? fileUrl(info.slug, "before.jpg", stamp) : null,
        after: info.files.includes("after.jpg") ? fileUrl(info.slug, "after.jpg", stamp) : null,
      });
      setRun(info.run.run_id ? { id: info.run.run_id, status: info.run.status ?? "unknown", errors: [] } : null);
    }).catch(() => setImages({ before: null, after: null }));
  }, [layout.name]);

  const stopPolling = () => { if (poll.current) clearInterval(poll.current); poll.current = null; };
  useEffect(() => stopPolling, []);

  const follow = (runId: string) => {
    stopPolling();
    poll.current = setInterval(async () => {
      try {
        const status = await api.runStatus(runId, layout.name);
        setRun(status);
        if (!ACTIVE.has(status.status)) {
          stopPolling();
          flash(`Run ${status.status}`, status.status === "succeeded" ? "ok" : "bad");
        }
      } catch (error) {
        flash((error as Error).message, "bad");
      }
    }, 2000);
  };

  const step = async (name: string, action: () => Promise<void>) => {
    setBusy(name);
    try { await action(); } catch (error) { flash((error as Error).message, "bad"); } finally { setBusy(null); }
  };

  const saveConfig = () => step("config", async () => {
    setConfig(await api.setRobotConfig(config));
    await checkHealth();
  });

  const generate = () => step("protocol", async () => {
    const result = await api.protocol(layout);
    setProtocol(result);
    flash(result.simulation.ok ? `Protocol simulated: ${result.simulation.steps} steps` : "Simulation failed", result.simulation.ok ? "ok" : "bad");
  });

  const snapshot = (tag: Tag) => step(tag, async () => {
    const { url } = await api.snapshot(layout.name, tag);
    setImages((prev) => ({ ...prev, [tag]: `/api${url}` }));
  });

  const start = () => step("run", async () => {
    const where = config.mock ? "the mock robot" : `${config.host}:${config.port}`;
    if (!window.confirm(`Start "${layout.name}" on ${where}?\n\nCheck the deck, tips and stock tubes match the protocol first.`)) return;
    const { run_id } = await api.startRun(layout.name);
    setRun({ id: run_id, status: "running", errors: [] });
    follow(run_id);
  });

  const control = (action: "play" | "pause" | "stop") => step(action, async () => {
    if (!run) return;
    await api.runAction(run.id, action);
    follow(run.id);
  });

  const connected = health?.ok ?? false;
  const runActive = run ? ACTIVE.has(run.status) : false;
  return (
    <div className="flex min-h-0 flex-1 gap-4">
      <div className="flex w-96 shrink-0 flex-col gap-3 overflow-auto">
        <section className="panel">
          <div className="panel-title">Robot <small>Opentrons Flex</small></div>
          <div className="grid grid-cols-[4rem_1fr] items-center gap-2">
            <label htmlFor="host" className="text-muted">Host</label>
            <input id="host" className="field" placeholder="192.168.0.42" value={config.host} disabled={config.mock}
                   onChange={(e) => setConfig({ ...config, host: e.target.value.trim() })} />
            <label htmlFor="port" className="text-muted">Port</label>
            <input id="port" className="field" inputMode="numeric" value={config.port} disabled={config.mock}
                   onChange={(e) => setConfig({ ...config, port: Number(e.target.value) || 31950 })} />
          </div>
          <label className="mt-3 flex items-center gap-2 text-muted">
            <input type="checkbox" checked={config.mock} onChange={(e) => setConfig({ ...config, mock: e.target.checked })} />
            Mock robot (rehearsal, no hardware)
          </label>
          <button className="btn mt-3 w-full" disabled={busy !== null} onClick={saveConfig}>Connect</button>
          {health && (
            <p className={`mt-3 flex items-start gap-2 ${health.ok ? "text-ok" : "text-bad"}`}>
              <span className={`mt-1 inline-block size-2 shrink-0 rounded-full ${health.ok ? "bg-ok" : "bg-bad"}`} />
              {health.text}
            </p>
          )}
        </section>

        <section className="panel">
          <div className="panel-title">Run <small>{layout.name}</small></div>
          <ol className="flex flex-col gap-2">
            <li><button className="btn w-full" disabled={busy !== null} onClick={generate}>1. Generate &amp; simulate protocol</button></li>
            <li><button className="btn w-full" disabled={!connected || busy !== null} onClick={() => snapshot("before")}>2. Snapshot before</button></li>
            <li><button className="btn btn-primary w-full" disabled={!connected || !protocol?.simulation.ok || runActive || busy !== null} onClick={start}>3. Run on robot</button></li>
            <li><button className="btn w-full" disabled={!connected || busy !== null} onClick={() => snapshot("after")}>4. Snapshot after</button></li>
          </ol>
          {run && (
            <div className="mt-3 flex items-center justify-between gap-2">
              <span>Run <span className="text-muted">{run.id.slice(0, 8)}</span>: <span className={run.status === "succeeded" ? "text-ok" : run.status === "failed" ? "text-bad" : "text-warn"}>{run.status}</span></span>
              {runActive && (
                <span className="flex gap-2">
                  {run.status === "paused"
                    ? <button className="btn" onClick={() => control("play")}>Resume</button>
                    : <button className="btn" onClick={() => control("pause")}>Pause</button>}
                  <button className="btn text-bad" onClick={() => control("stop")}>Stop</button>
                </span>
              )}
            </div>
          )}
          {run?.errors.map((e) => <p key={e} className="mt-1 text-bad">{e}</p>)}
          {!connected && <p className="mt-3 text-muted">Connect to a robot (or the mock) to use the camera and run.</p>}
        </section>

        {protocol && (
          <section className="panel">
            <div className="panel-title">Protocol
              <button className="text-accent" onClick={() => setShowSource(!showSource)}>{showSource ? "hide source" : "show source"}</button>
            </div>
            <p className={protocol.simulation.ok ? "text-ok" : "text-bad"}>
              {protocol.simulation.ok ? `✓ Opentrons simulator: ${protocol.simulation.steps} steps` : `✗ ${protocol.simulation.error}`}
            </p>
            <p className="mt-3 text-muted">Load the stock rack:</p>
            {Object.keys(protocol.tubes).length === 0 && <p className="text-muted">No stock tubes needed.</p>}
            {Object.entries(protocol.tubes).map(([liquid, tube]) => <p key={liquid}>{tube}: {liquid}</p>)}
          </section>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          {(["before", "after"] as const).map((tag) => (
            <figure key={tag} className="panel">
              <figcaption className="panel-title capitalize">{tag}</figcaption>
              {images[tag]
                // eslint-disable-next-line @next/next/no-img-element -- snapshots are served by the local API
                ? <img src={images[tag]!} alt={`Deck ${tag} the run`} className="aspect-video w-full rounded bg-field object-contain" />
                : <div className="flex aspect-video items-center justify-center rounded bg-field text-muted">No snapshot yet</div>}
            </figure>
          ))}
        </div>
        {protocol && showSource && (
          <pre className="panel min-h-0 flex-1 overflow-auto text-xs leading-relaxed">{protocol.protocol}</pre>
        )}
      </div>
    </div>
  );
}
