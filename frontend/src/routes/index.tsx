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

import { AppShell, PageHeader, StatCard } from "@/components/app-shell";
import { formatTime } from "@/lib/mock-data";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "EdgeVision Control Room — PPE & Height Safety Overview" },
      {
        name: "description",
        content:
          "Live overview of PPE compliance, active safety violations, camera health and worker tracking across all monitored industrial zones.",
      },
      { property: "og:title", content: "EdgeVision Control Room — PPE & Height Safety Overview" },
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

type HealthData = { status: string; fps: number; zone: string; ws_connections: number; camera_active: boolean; pipeline_active: boolean };
type StatsData = { cameras_online: number; cameras_total: number; active_violations: number; violations_today: number; workers_tracked: number; daily_compliance: number; current_fps: number };
type ReportsData = { total_violations: number; avg_compliance: number; by_zone: { zone_id: string; count: number }[]; daily_trend: { day: string; violations: number; compliance: number }[] };
type TickerItem = { id: string; text: string; level: "critical" | "warn" | "ok"; at: string };

function Overview() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [reports, setReports] = useState<ReportsData | null>(null);
  const [ticker, setTicker] = useState<TickerItem[]>([]);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [healthRes, statsRes, reportsRes, violationsRes] = await Promise.allSettled([
          fetch("/api/health"),
          fetch("/api/stats"),
          fetch("/api/reports"),
          fetch("/api/violations"),
        ]);

        if (healthRes.status === "fulfilled" && healthRes.value.ok) {
          setHealth(await healthRes.value.json());
        }
        if (statsRes.status === "fulfilled" && statsRes.value.ok) {
          setStats(await statsRes.value.json());
        }
        if (reportsRes.status === "fulfilled" && reportsRes.value.ok) {
          setReports(await reportsRes.value.json());
        }
        if (violationsRes.status === "fulfilled" && violationsRes.value.ok) {
          const violations = await violationsRes.value.json();
          if (Array.isArray(violations)) {
            setTicker(
              violations.slice(0, 8).map((v: any) => ({
                id: v.id,
                text: `${v.workerId || "Worker"} · ${v.type || "violation"} · ${v.zoneId || ""}`,
                level: v.acknowledged ? ("ok" as const) : ("critical" as const),
                at: formatTime(v.timestamp),
              }))
            );
          }
        }
      } catch (err) {
        console.error("Dashboard fetch failed", err);
      }
    };
    fetchAll();
    const int = setInterval(fetchAll, 5000);
    return () => clearInterval(int);
  }, []);

  const violationTrend = reports?.daily_trend || [];
  const violationsByZone = (reports?.by_zone || []).map((z) => ({
    zone: z.zone_id || "Unknown",
    count: z.count,
  }));

  return (
    <AppShell>
      <div className="flex items-start justify-between">
        <PageHeader
          title="Control Room Overview"
          subtitle="Edge inference pipeline status, compliance posture and live alert feed for all monitored zones."
        />
        <button
          onClick={async () => {
            try {
              const res = await fetch('/api/test/seed', { method: 'POST' });
              if (res.ok) alert('Test data seeded successfully!');
              else alert('Failed to seed data. Did you restart the backend?');
            } catch (e) {
              alert('Error calling seed API. Ensure backend is running.');
            }
          }}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 mt-2"
        >
          Add Sample Data
        </button>
      </div>

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
          <h2 className="display-title text-sm">7-day violation trend</h2>
          <p className="mb-3 text-xs text-muted-foreground">
            Confirmed violations after temporal validation (8/10 frame rule).
          </p>
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
          <h2 className="display-title text-sm">Violations by zone</h2>
          <p className="mb-3 text-xs text-muted-foreground">Aggregated from database.</p>
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
