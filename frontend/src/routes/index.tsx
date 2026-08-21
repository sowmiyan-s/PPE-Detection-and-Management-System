import { createFileRoute } from "@tanstack/react-router";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, Camera, HardHat, Percent, Users } from "lucide-react";
import { useState, useEffect } from "react";
import { useSessionFetch } from "@/hooks/use-session-fetch";

import { AppShell, PageHeader, StatCard } from "@/components/app-shell";
import { formatTime } from "@/lib/mock-data";

import { getWsUrl } from "@/lib/api-config";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Cerberus AI Control Room — PPE & Height Safety Overview" },
      {
        name: "description",
        content:
          "Live overview of PPE compliance, active safety violations, camera health and worker tracking across all monitored industrial zones.",
      },
      { property: "og:title", content: "Cerberus AI Control Room — PPE & Height Safety Overview" },
      {
        property: "og:description",
        content:
          "Live overview of PPE compliance, active safety violations, camera health and worker tracking across all monitored industrial zones.",
      },
    ],
  }),
  component: Overview,
});

const tooltipStyle = {
  backgroundColor: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: 4,
  fontSize: 12,
  fontFamily: "var(--font-mono)",
};

import { useAppData } from "@/lib/data-context";
import { useRef } from "react";

type HealthData = { status: string; fps: number; zone: string; ws_connections: number; camera_active: boolean; pipeline_active: boolean };
type StatsData = { cameras_online: number; cameras_total: number; active_violations: number; violations_today: number; workers_tracked: number; daily_compliance: number; current_fps: number };
type ReportsData = { total_violations: number; avg_compliance: number; by_zone: { zone_id: string; count: number }[]; daily_trend: { day: string; violations: number; compliance: number }[] };
type TickerItem = { id: string; text: string; level: "critical" | "warn" | "ok"; at: string };

function Overview() {
  const { stats: ctxStats, reports: ctxReports, violations: ctxViolations, refetchAll } = useAppData();
  const { data: health } = useSessionFetch<HealthData | null>("/api/health", null);

  const [liveFps, setLiveFps] = useState<number>(0);
  const [liveWorkers, setLiveWorkers] = useState<number>(0);
  const [liveZone, setLiveZone] = useState<string>("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsUrl = getWsUrl();
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.fps !== undefined) setLiveFps(d.fps);
        if (d.zone) setLiveZone(d.zone);
        if (d.workers) setLiveWorkers(d.workers.length);
      } catch (err) {}
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const stats = ctxStats || null;
  const reports = ctxReports || null;
  const violations = ctxViolations || [];

  const ticker: TickerItem[] = Array.isArray(violations)
    ? violations.slice(0, 8).map((v: any) => ({
        id: v.id,
        text: `${v.workerId || "Worker"} · ${v.type || "violation"} · ${v.zoneId || ""}`,
        level: v.acknowledged ? ("ok" as const) : ("critical" as const),
        at: formatTime(v.timestamp),
      }))
    : [];

  const violationTrend = reports?.daily_trend || [];
  const violationsByZone = (reports?.by_zone || []).map((z: any) => ({
    zone: z.zone_id || "Unknown",
    count: z.count,
  }));

  return (
    <AppShell>
      <PageHeader title="Control Room Overview" />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Cameras online"
          value={stats ? `${stats.cameras_online} / ${stats.cameras_total}` : "—"}
          hint="Active streams"
          tone="success"
          icon={Camera}
        />
        <StatCard
          label="Active violations"
          value={stats?.active_violations ?? 0}
          hint="Unacknowledged"
          tone={stats && stats.active_violations > 0 ? "danger" : "success"}
          icon={AlertTriangle}
        />
        <StatCard
          label="Daily compliance"
          value={stats?.daily_compliance ?? "—"}
          unit="%"
          hint="Based on detected violations"
          tone="success"
          icon={Percent}
        />
        <StatCard
          label="Workers tracked"
          value={stats?.workers_tracked ?? 0}
          hint="Unique tracking IDs today"
          icon={Users}
        />
      </section>

      <section className="mt-3 grid gap-3 lg:grid-cols-3">
        <div className="rounded panel-surface p-4 lg:col-span-2">
          <h2 className="display-title text-sm mb-3">7-day violation trend</h2>
          <div className="h-64">
            {violationTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={violationTrend}>
                  <defs>
                    <linearGradient id="vGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--destructive)" stopOpacity={0.55} />
                      <stop offset="100%" stopColor="var(--destructive)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="day" stroke="var(--muted-foreground)" fontSize={11} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area
                    type="monotone"
                    dataKey="violations"
                    stroke="var(--destructive)"
                    strokeWidth={2}
                    fill="url(#vGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No violation data yet — trends populate as the pipeline runs.
              </div>
            )}
          </div>
        </div>

        <div className="rounded panel-surface p-4">
          <h2 className="display-title text-sm mb-3">Violations by zone</h2>
          <div className="h-64">
            {violationsByZone.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={violationsByZone} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" stroke="var(--muted-foreground)" fontSize={11} />
                  <YAxis
                    type="category"
                    dataKey="zone"
                    stroke="var(--muted-foreground)"
                    fontSize={10}
                    width={96}
                  />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="var(--primary)" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No zone data yet.
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="mt-3 grid gap-3 lg:grid-cols-3">
        <div className="rounded panel-surface p-4 lg:col-span-2">
          <h2 className="display-title text-sm">Live alert ticker</h2>
          <ul className="mt-3 divide-y divide-border">
            {ticker.length === 0 ? (
              <li className="py-4 text-center text-sm text-muted-foreground">
                No recent violation events — the pipeline will populate alerts as workers are detected.
              </li>
            ) : (
              ticker.map((t) => (
                <li key={t.id} className="flex items-center gap-3 py-2.5">
                  <span
                    className={`size-2 shrink-0 rounded-full ${
                      t.level === "critical"
                        ? "bg-destructive scan-pulse"
                        : t.level === "warn"
                          ? "bg-primary"
                          : "bg-success"
                    }`}
                  />
                  <span className="telemetry text-xs text-muted-foreground">{t.at}</span>
                  <span className="text-sm">{t.text}</span>
                </li>
              ))
            )}
          </ul>
        </div>

        <div className="rounded panel-surface p-4">
          <h2 className="display-title text-sm">Pipeline health</h2>
          <dl className="mt-3 space-y-3 text-sm">
            {[
              ["Backend Connection", health?.status === "ok" ? "OK" : "WAITING", health?.status === "ok" ? "success" : "warning"],
              ["Camera Stream", health?.camera_active ? "ACTIVE" : "OFFLINE", health?.camera_active ? "success" : "warning"],
              ["Vision Pipeline", health?.pipeline_active ? "RUNNING" : "STOPPED", health?.pipeline_active ? "success" : "warning"],
              ["Zone Rule Engine", health?.status === "ok" ? "OK" : "WAITING", health?.status === "ok" ? "success" : "warning"],
            ].map(([stage, state, tone]) => (
              <div key={stage} className="flex items-center justify-between gap-2">
                <dt className="text-muted-foreground">{stage}</dt>
                <dd
                  className={`telemetry text-xs ${
                    tone === "success" ? "text-success" : "text-primary"
                  }`}
                >
                  {state}
                </dd>
              </div>
            ))}
          </dl>
          <div className="mt-4 flex flex-col gap-2 rounded border border-border bg-background/40 p-3">
            <div className="flex items-center gap-2">
              <HardHat className="size-4 text-primary" />
              <span className="telemetry text-[11px] text-muted-foreground">
                {health ? `${health.fps.toFixed(1)} FPS · ZONE: ${health.zone}` : "Connecting to backend..."}
              </span>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
