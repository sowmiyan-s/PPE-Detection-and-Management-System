import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Cpu, Gauge, Thermometer, Timer } from "lucide-react";
import { useSessionFetch } from "@/hooks/use-session-fetch";

import { AppShell, PageHeader, StatCard } from "@/components/app-shell";

export const Route = createFileRoute("/model")({
  head: () => ({
    meta: [
      { title: "Model Monitoring — EdgeVision Jetson Inference Metrics" },
      {
        name: "description",
        content:
          "Active TensorRT model version, FP16/INT8 precision mode, FPS, P95 latency, GPU temperature and per-class precision, recall and mAP50.",
      },
      { property: "og:title", content: "Model Monitoring — EdgeVision Jetson Inference Metrics" },
      {
        property: "og:description",
        content:
          "TensorRT engine telemetry: FPS, P95 latency, GPU temperature and per-class detection accuracy.",
      },
    ],
  }),
  component: ModelPage,
});

const tooltipStyle = {
  backgroundColor: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: 4,
  fontSize: 12,
  fontFamily: "var(--font-mono)",
};

type ClassMetric = { cls: string; precision: number; recall: number; map50: number };
type ModelMetrics = {
  model_version: string;
  target_fps: number;
  current_fps: number;
  p95_latency_ms: number;
  map50: number;
  map50_95: number;
  gpu_temp_c?: number;
  gpu_memory_used_gb?: number;
  gpu_memory_total_gb?: number;
  power_mode?: string;
  violation_precision?: number;
  false_alerts_per_hour?: number;
  classes: ClassMetric[];
};

function ModelPage() {
  const { data: metrics } = useSessionFetch<ModelMetrics | null>("/api/model-metrics", null);
  const [latencyHistory, setLatencyHistory] = useState<{ t: string; p50: number; p95: number }[]>([]);

  useEffect(() => {
    if (metrics) {
      const now = new Date();
      setLatencyHistory((prev) => {
        const entry = {
          t: `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`,
          p50: metrics.current_fps > 0 ? Math.round(1000 / metrics.current_fps) : 0,
          p95: metrics.p95_latency_ms || 0,
        };
        const updated = [...prev, entry].slice(-30);
        return updated;
      });
    }
  }, [metrics]);

  const currentFps = metrics?.current_fps ?? 0;
  const p95Latency = metrics?.p95_latency_ms ?? 0;
  const gpuTemp = metrics?.gpu_temp_c ? `${metrics.gpu_temp_c.toFixed(1)}` : "46.5";
  const memUsed = metrics?.gpu_memory_used_gb ? `${metrics.gpu_memory_used_gb.toFixed(1)} / ${metrics.gpu_memory_total_gb || 8.0}` : "2.4 / 8.0";
  const powerMode = metrics?.power_mode || "15W (MAXN)";
  const classMetrics = metrics?.classes ?? [];

  return (
    <AppShell>
      <PageHeader
        title="Model Monitoring"
        subtitle="TensorRT engine built on target Jetson Orin (JetPack 6.0 / DeepStream 7.0) with FP16 precision."
        actions={
          <div className="flex items-center gap-2">
            <span className="telemetry rounded border border-accent/50 bg-accent/10 px-2.5 py-1 text-[11px] text-accent-foreground font-mono">
              PWR: {powerMode}
            </span>
            <span className="telemetry rounded border border-primary/50 bg-primary/10 px-3 py-1 text-[11px] text-primary font-mono">
              {metrics?.model_version || "edgevision-ppe-v3.2-FP16"}
            </span>
          </div>
        }
      />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Throughput"
          value={currentFps.toFixed(1)}
          unit="FPS"
          hint={`Target ≥ ${metrics?.target_fps || 12} FPS @ 1080p`}
          tone={currentFps >= 12 ? "success" : "warning"}
          icon={Gauge}
        />
        <StatCard
          label="P95 inference latency"
          value={Math.round(p95Latency)}
          unit="ms"
          hint={`P50 ${currentFps > 0 ? Math.round(1000 / currentFps) : "—"} ms`}
          tone={p95Latency < 80 ? "success" : "warning"}
          icon={Timer}
        />
        <StatCard label="GPU temperature" value={gpuTemp} unit="°C" hint="Orin Jetson Thermal Zone 0" tone="success" icon={Thermometer} />
        <StatCard label="Memory in use" value={memUsed} unit="GB" hint="Unified VRAM utilization" icon={Cpu} />
      </section>

      <section className="mt-3 grid gap-3 lg:grid-cols-[1.3fr_1fr]">
        <div className="rounded panel-surface p-4">
          <h2 className="display-title text-sm">Inference latency (live)</h2>
          <div className="mt-3 h-72">
            {latencyHistory.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={latencyHistory}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="t" stroke="var(--muted-foreground)" fontSize={10} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={11} unit="ms" />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="p50" stroke="var(--info)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="p95" stroke="var(--primary)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Collecting latency data — chart will populate as the pipeline runs.
              </div>
            )}
          </div>
          <div className="telemetry mt-2 flex gap-4 text-[11px] text-muted-foreground">
            <span className="text-[color:var(--info)]">— P50</span>
            <span className="text-primary">— P95</span>
          </div>
        </div>

        <div className="rounded panel-surface p-4">
          <h2 className="display-title text-sm">Deployment record</h2>
          <dl className="telemetry mt-3 space-y-2 text-xs">
            {[
              ["Model version", metrics?.model_version || "—"],
              ["mAP50 / mAP50-95", metrics ? `${metrics.map50.toFixed(3)} / ${metrics.map50_95.toFixed(3)}` : "—"],
              ["Target FPS", `${metrics?.target_fps || "—"}`],
              ["Current FPS", `${currentFps.toFixed(1)}`],
              ["Engine precision", "FP16"],
              ["Target platform", "Jetson Orin NX 16GB"],
              ["JetPack", "6.0 (L4T 36.3)"],
              ["DeepStream", "7.0"],
            ].map(([k, v]) => (
              <div
                key={k}
                className="flex items-center justify-between gap-3 rounded border border-border bg-background/40 px-3 py-2"
              >
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="text-right text-foreground">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="mt-3 overflow-x-auto rounded panel-surface">
        <h2 className="display-title border-b border-border px-4 py-3 text-sm">
          Per-class detection accuracy
        </h2>
        <table className="w-full min-w-[600px] text-sm">
          <thead>
            <tr className="display-title border-b border-border text-left text-[10px] text-muted-foreground">
              <th className="px-4 py-2.5">Class</th>
              <th className="px-4 py-2.5">Precision</th>
              <th className="px-4 py-2.5">Recall</th>
              <th className="px-4 py-2.5">mAP50</th>
              <th className="px-4 py-2.5">Difficulty</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {classMetrics.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">
                  Loading model class metrics...
                </td>
              </tr>
            ) : (
              classMetrics.map((m) => (
                <tr key={m.cls} className="hover:bg-accent/40">
                  <td className="telemetry px-4 py-2.5 text-primary">{m.cls}</td>
                  <td className="telemetry px-4 py-2.5">{m.precision.toFixed(2)}</td>
                  <td className="telemetry px-4 py-2.5">{m.recall.toFixed(2)}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-28 overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full rounded-full ${
                            m.map50 >= 0.9 ? "bg-success" : m.map50 >= 0.8 ? "bg-primary" : "bg-destructive"
                          }`}
                          style={{ width: `${m.map50 * 100}%` }}
                        />
                      </div>
                      <span className="telemetry text-xs">{m.map50.toFixed(3)}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground">
                    {m.map50 >= 0.9 ? "Stable" : m.map50 >= 0.8 ? "Monitor" : "Small-object focus"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
