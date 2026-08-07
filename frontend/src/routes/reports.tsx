import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { FileDown, FileText } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AppShell, PageHeader, StatCard } from "@/components/app-shell";

export const Route = createFileRoute("/reports")({
  head: () => ({
    meta: [
      { title: "Reports — EdgeVision Compliance Reporting" },
      {
        name: "description",
        content:
          "Daily, weekly and monthly PPE compliance trends and per-zone violation breakdowns with PDF and CSV export.",
      },
      { property: "og:title", content: "Reports — EdgeVision Compliance Reporting" },
      {
        property: "og:description",
        content: "Compliance trend charts and per-zone violation reporting with PDF/CSV export.",
      },
    ],
  }),
  component: ReportsPage,
});

const tooltipStyle = {
  backgroundColor: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: 4,
  fontSize: 12,
  fontFamily: "var(--font-mono)",
};

type ReportsData = {
  total_violations: number;
  avg_compliance: number;
  false_alerts_per_hour: number;
  violations_per_hour: number;
  by_zone: { zone_id: string; count: number }[];
  daily_trend: { day: string; violations: number; compliance: number }[];
  unique_workers: number;
  reviewed: number;
};

function ReportsPage() {
  const [reports, setReports] = useState<ReportsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/reports")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setReports(data);
      })
      .catch((err) => console.error("Failed to fetch reports", err))
      .finally(() => setLoading(false));
  }, []);

  const dailyTrend = (reports?.daily_trend || []).map((d) => ({
    period: d.day,
    compliance: d.compliance,
    violations: d.violations,
  }));

  const violationsByZone = (reports?.by_zone || []).map((z) => ({
    zone: z.zone_id || "Unknown",
    count: z.count,
  }));

  return (
    <AppShell>
      <PageHeader
        title="Reports"
        subtitle="Aggregated compliance reporting for safety review meetings and regulatory records."
        actions={
          <>
            <button className="display-title inline-flex items-center gap-1.5 rounded border border-border bg-panel px-3 py-1.5 text-[11px]">
              <FileText className="size-3.5" /> Export PDF
            </button>
            <button className="display-title inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-[11px] text-primary-foreground">
              <FileDown className="size-3.5" /> Export CSV
            </button>
          </>
        }
      />

      {loading ? (
        <div className="rounded panel-surface p-12 text-center text-muted-foreground animate-pulse">
          Loading compliance reports...
        </div>
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-3">
            <StatCard
              label="Avg compliance"
              value={reports?.avg_compliance ?? 100}
              unit="%"
              hint="Based on all recorded events"
              tone="success"
            />
            <StatCard
              label="Total violations"
              value={reports?.total_violations ?? 0}
              hint="After temporal validation"
              tone={reports && reports.total_violations > 0 ? "danger" : "success"}
            />
            <StatCard
              label="False alerts / hour"
              value={reports?.false_alerts_per_hour ?? 0}
              hint="Target < 1.0"
              tone={(reports?.false_alerts_per_hour ?? 0) < 1 ? "success" : "warning"}
            />
          </section>

          <section className="mt-3 grid gap-3 lg:grid-cols-2">
            <div className="rounded panel-surface p-4">
              <h2 className="display-title text-sm">Compliance trend</h2>
              <div className="mt-3 h-72">
                {dailyTrend.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={dailyTrend}>
                      <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="period" stroke="var(--muted-foreground)" fontSize={11} />
                      <YAxis domain={[60, 100]} stroke="var(--muted-foreground)" fontSize={11} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Line
                        type="monotone"
                        dataKey="compliance"
                        stroke="var(--success)"
                        strokeWidth={2.5}
                        dot={{ r: 3, fill: "var(--success)" }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    No trend data yet — reports populate as violations are recorded.
                  </div>
                )}
              </div>
            </div>

            <div className="rounded panel-surface p-4">
              <h2 className="display-title text-sm">Violations per zone</h2>
              <div className="mt-3 h-72">
                {violationsByZone.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={violationsByZone}>
                      <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="zone" stroke="var(--muted-foreground)" fontSize={10} />
                      <YAxis stroke="var(--muted-foreground)" fontSize={11} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Bar dataKey="count" fill="var(--destructive)" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    No zone violation data yet.
                  </div>
                )}
              </div>
            </div>
          </section>
        </>
      )}
    </AppShell>
  );
}
