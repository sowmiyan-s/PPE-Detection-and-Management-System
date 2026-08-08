import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { FileDown, FileSpreadsheet, X, Filter, Calendar, Camera as CameraIcon } from "lucide-react";
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
import { useAppData } from "@/lib/data-context";

export const Route = createFileRoute("/reports")({
  head: () => ({
    meta: [
      { title: "Reports — EdgeVision Compliance Reporting" },
      {
        name: "description",
        content:
          "Daily, weekly and monthly PPE compliance trends and per-zone violation breakdowns with PDF and Excel export.",
      },
      { property: "og:title", content: "Reports — EdgeVision Compliance Reporting" },
      {
        property: "og:description",
        content: "Compliance trend charts and per-zone violation reporting with Excel export.",
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

function ReportsPage() {
  const { reports: ctxReports, cameras: ctxCameras, zones: ctxZones, loading: ctxLoading } = useAppData();
  const [reports, setReports] = useState<any>(ctxReports);
  const [loading, setLoading] = useState(!ctxReports);

  // Excel Export Modal state
  const [showExportModal, setShowExportModal] = useState(false);
  const [selectedCameras, setSelectedCameras] = useState<string[]>(["all"]);
  const [dateRange, setDateRange] = useState<string>("all");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [selectedZone, setSelectedZone] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");

  useEffect(() => {
    if (ctxReports) {
      setReports(ctxReports);
      setLoading(false);
    } else {
      fetch("/api/reports")
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) setReports(data);
        })
        .catch((err) => console.error("Failed to fetch reports", err))
        .finally(() => setLoading(false));
    }
  }, [ctxReports]);

  const dailyTrend = (reports?.daily_trend || []).map((d: any) => ({
    period: d.day,
    compliance: d.compliance,
    violations: d.violations,
  }));

  const violationsByZone = (reports?.by_zone || []).map((z: any) => ({
    zone: z.zone_id || "Unknown",
    count: z.count,
  }));

  const handleCameraToggle = (camId: string) => {
    if (camId === "all") {
      setSelectedCameras(["all"]);
      return;
    }

    setSelectedCameras((prev) => {
      const filtered = prev.filter((c) => c !== "all");
      if (filtered.includes(camId)) {
        const next = filtered.filter((c) => c !== camId);
        return next.length === 0 ? ["all"] : next;
      } else {
        return [...filtered, camId];
      }
    });
  };

  const handleDownloadExcel = () => {
    const params = new URLSearchParams();
    params.set("cameras", selectedCameras.join(","));
    params.set("date_range", dateRange);
    if (dateRange === "custom") {
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
    }
    params.set("zone_id", selectedZone);
    params.set("status", selectedStatus);

    window.location.href = `/api/export/excel?${params.toString()}`;
    setShowExportModal(false);
  };

  return (
    <AppShell>
      <PageHeader
        title="Reports & Analytics Export"
        subtitle="Aggregated compliance reporting for safety review meetings and regulatory records."
        actions={
          <button
            onClick={() => setShowExportModal(true)}
            className="display-title inline-flex items-center gap-1.5 rounded bg-primary px-3.5 py-2 text-xs text-primary-foreground font-semibold hover:bg-primary/90 transition-colors shadow"
          >
            <FileSpreadsheet className="size-4" /> Export Data to Excel (.xlsx)
          </button>
        }
      />

      {/* Multi-Filter Excel Export Modal */}
      {showExportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="relative max-w-xl w-full bg-panel rounded-lg border border-border overflow-hidden shadow-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="size-5 text-primary" />
                <h3 className="font-semibold text-base display-title text-foreground">Export Safety Data to Excel</h3>
              </div>
              <button
                onClick={() => setShowExportModal(false)}
                className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              {/* 1. Camera Filter */}
              <div>
                <label className="font-semibold display-title text-muted-foreground block mb-1.5">
                  1. Camera Selection (Single / Multi-Camera)
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => handleCameraToggle("all")}
                    className={`px-2.5 py-1 rounded text-xs border font-medium transition-colors ${
                      selectedCameras.includes("all")
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-background border-border text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    All Cameras
                  </button>
                  {ctxCameras.map((c: any) => {
                    const isChecked = selectedCameras.includes(c.id);
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => handleCameraToggle(c.id)}
                        className={`px-2.5 py-1 rounded text-xs border font-medium transition-colors ${
                          isChecked
                            ? "bg-primary text-primary-foreground border-primary"
                            : "bg-background border-border text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {c.name} ({c.id})
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 2. Date Range Filter */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold display-title text-muted-foreground block mb-1">
                    2. Date Range
                  </label>
                  <select
                    value={dateRange}
                    onChange={(e) => setDateRange(e.target.value)}
                    className="w-full bg-background border border-border rounded px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                  >
                    <option value="all">All Time History</option>
                    <option value="daily">Today (Daily)</option>
                    <option value="weekly">Past 7 Days (Weekly)</option>
                    <option value="monthly">Past 30 Days (Monthly)</option>
                    <option value="custom">Custom Date Range</option>
                  </select>
                </div>

                <div>
                  <label className="font-semibold display-title text-muted-foreground block mb-1">
                    3. Safety Zone
                  </label>
                  <select
                    value={selectedZone}
                    onChange={(e) => setSelectedZone(e.target.value)}
                    className="w-full bg-background border border-border rounded px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                  >
                    <option value="all">All Safety Zones</option>
                    {ctxZones.map((z: any) => (
                      <option key={z.id} value={z.id}>
                        {z.name} ({z.id})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Custom Date Pickers */}
              {dateRange === "custom" && (
                <div className="grid grid-cols-2 gap-3 p-3 rounded bg-background/50 border border-border">
                  <div>
                    <span className="text-[10px] text-muted-foreground block mb-1">Start Date</span>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full bg-background border border-border rounded px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-primary"
                    />
                  </div>
                  <div>
                    <span className="text-[10px] text-muted-foreground block mb-1">End Date</span>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full bg-background border border-border rounded px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-primary"
                    />
                  </div>
                </div>
              )}

              {/* 4. Review Status Filter */}
              <div>
                <label className="font-semibold display-title text-muted-foreground block mb-1">
                  4. Review Status
                </label>
                <div className="flex gap-2">
                  {(
                    [
                      ["all", "All Events"],
                      ["unacknowledged", "Unacknowledged Only"],
                      ["reviewed", "Acknowledged / Accepted Only"],
                    ] as [string, string][]
                  ).map(([val, lbl]) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => setSelectedStatus(val)}
                      className={`flex-1 py-1.5 px-2 rounded text-xs border font-medium text-center transition-colors ${
                        selectedStatus === val
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-background border-border text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {lbl}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => setShowExportModal(false)}
                className="px-4 py-2 rounded text-xs font-medium border border-border text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDownloadExcel}
                className="flex items-center gap-1.5 px-4 py-2 rounded bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors shadow"
              >
                <FileSpreadsheet className="size-4" /> Download Excel (.xlsx)
              </button>
            </div>
          </div>
        </div>
      )}

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

