// Typed wrappers for the Python API (proxied at /api by next.config.ts).
import type { Layout, PlateFormat } from "./layout";

export interface AssayStep {
  well: string; role: string; liquid: string; target: string; source: string;
  transfer_ul: number | null; medium_ul: number | null; solvent_percent: number | null; warnings: string[];
}
export interface IntermediateWell {
  well: string; label: string; source: string; source_volume_ul: number; medium_volume_ul: number;
  total_volume_ul: number; warnings: string[];
}
export interface Transfer {
  step: number; phase: string; source_labware: string; source_well: string;
  dest_labware: string; dest_well: string; volume_ul: number; liquid: string;
}
export interface PlanResponse {
  plan: { assay_steps: AssayStep[]; intermediates: IntermediateWell[]; transfers: Transfer[]; warnings: string[] };
  check: { passed: boolean; problems: string[]; wells: { well: string; ok: boolean; problem: string }[] };
  materials: string[];
  volume_ul: number;
}
export interface ProtocolResponse {
  slug: string; protocol: string; tubes: Record<string, string>;
  simulation: { ok: boolean; steps: number; error: string };
}
export interface RobotConfig { host: string; port: number; mock: boolean }
export interface RunStatus { id: string; status: string; errors: string[] }
export interface RunFiles { slug: string; files: string[]; run: { run_id?: string; status?: string } }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
    });
  } catch {
    throw new Error("Can't reach the backend on 127.0.0.1:8000. Start it with: uv run python scripts/serve.py");
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail) // FastAPI validation errors
          ? body.detail.map((d: { loc?: string[]; msg?: string }) => `${d.loc?.at(-1) ?? "input"}: ${d.msg}`).join("; ")
          : JSON.stringify(body.detail ?? body);
    } catch {
      if (response.status >= 500) detail = "Backend not reachable (is scripts/serve.py running?)";
    }
    throw new Error(detail);
  }
  return response.headers.get("content-type")?.includes("json") ? response.json() : (response.text() as Promise<T>);
}

const json = (body: unknown) => JSON.stringify(body);
const plate = (name: string) => encodeURIComponent(name);

export const api = {
  formats: () => call<PlateFormat[]>("/formats"),
  layouts: () => call<{ slug: string; name: string }[]>("/layouts"),
  loadLayout: (slug: string) => call<Layout>(`/layouts/${plate(slug)}`),
  saveLayout: (layout: Layout) => call<{ slug: string }>(`/layouts/${plate(layout.name)}`, { method: "PUT", body: json(layout) }),
  runFiles: (name: string) => call<RunFiles>(`/layouts/${plate(name)}/run`),
  plan: (layout: Layout) => call<PlanResponse>("/plan", { method: "POST", body: json({ layout }) }),
  transfersCsv: (layout: Layout) => call<string>("/plan/transfers.csv", { method: "POST", body: json({ layout }) }),
  protocol: (layout: Layout) => call<ProtocolResponse>("/protocol", { method: "POST", body: json({ layout }) }),
  robotConfig: () => call<RobotConfig>("/robot/config"),
  setRobotConfig: (config: RobotConfig) => call<RobotConfig>("/robot/config", { method: "PUT", body: json(config) }),
  health: () => call<{ name?: string; robot_model?: string; api_version?: string }>("/robot/health"),
  snapshot: (name: string, tag: "before" | "after") =>
    call<{ url: string }>("/robot/snapshot", { method: "POST", body: json({ plate: name, tag }) }),
  startRun: (name: string) => call<{ run_id: string }>("/robot/runs", { method: "POST", body: json({ plate: name }) }),
  runStatus: (runId: string, name: string) => call<RunStatus>(`/robot/runs/${runId}?plate=${plate(name)}`),
  runAction: (runId: string, action: "play" | "pause" | "stop") => call<unknown>(`/robot/runs/${runId}/${action}`, { method: "POST" }),
};

export function fileUrl(slug: string, filename: string, version?: number | string): string {
  return `/api/files/${plate(slug)}/${filename}${version ? `?v=${version}` : ""}`;
}

export function download(filename: string, text: string, type = "text/csv"): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}
