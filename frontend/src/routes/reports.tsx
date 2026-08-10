import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useMemo } from "react";
import { Download, FileSpreadsheet, Filter, Calendar, ShieldAlert, Check, RefreshCw, X, User } from "lucide-react";
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
      { title: "Safety Reports & Executive Analytics — EdgeVision" },
      {
        name: "description",
        content:
          "Multi-constraint safety reporting, worker compliance metrics, zone analytics, and clean CSV/Excel exports.",
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

interface FilteredViolation {
  id: string;
  timestamp: string;
  workerId: string;
  zoneId: string;
  cameraId: string;
  type: string;
  detected: string[];
  missing: string[];
  confidence: number;
  status: string;
  acknowledged: boolean;
}

function ReportsPage() {
  const { reports: ctxReports, zones: ctxZones, workers: ctxWorkers, violations: ctxViolations } = useAppData();
  
  // Multi-Constraint Filter States
  const [dateRange, setDateRange] = useState<string>("all");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [selectedZone, setSelectedZone] = useState<string>("all");
  const [selectedWorker, setSelectedWorker] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");

  const [filteredEvents, setFilteredEvents] = useState<FilteredViolation[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch filtered data from backend API whenever filter constraints change
  const fetchFilteredData = () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set("date_range", dateRange);
    if (dateRange === "custom") {
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
    }
    params.set("zone_id", selectedZone);
    params.set("worker_id", selectedWorker);
    params.set("status", selectedStatus);

    fetch(`/api/violations?${params.toString()}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setFilteredEvents(data);
        }
      })
      .catch((err) => console.error("Failed to load filtered violations", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchFilteredData();
  }, [dateRange, startDate, endDate, selectedZone, selectedWorker, selectedStatus]);

  // Derived Analytics Metrics from Filtered Records
  const totalViolations = filteredEvents.length;
  const unacknowledgedCount = useMemo(() => filteredEvents.filter((v) => !v.acknowledged).length, [filteredEvents]);
  const reviewedCount = totalViolations - unacknowledgedCount;
  const uniqueWorkersCount = useMemo(() => new Set(filteredEvents.map((v) => v.workerId).filter(Boolean)).size, [filteredEvents]);

  // Calculate Zone Breakdown
  const violationsByZone = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const v of filteredEvents) {
      const zid = v.zoneId || "general_plant";
      counts[zid] = (counts[zid] || 0) + 1;
    }
    return Object.entries(counts).map(([zone, count]) => ({ zone, count }));
  }, [filteredEvents]);

  // Calculate Timeline Trend
  const dailyTrend = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const v of filteredEvents) {
      const day = v.timestamp ? v.timestamp.split(" ")[0] : "Today";
      counts[day] = (counts[day] || 0) + 1;
    }
    return Object.entries(counts)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([period, violations]) => ({
        period,
        violations,
        compliance: Math.max(50, 100 - violations * 3),
      }));
  }, [filteredEvents]);

  // Export Trigger Helpers
  const buildExportParams = () => {
    const params = new URLSearchParams();
    params.set("date_range", dateRange);
    if (dateRange === "custom") {
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
    }
    params.set("zone_id", selectedZone);
    params.set("worker_id", selectedWorker);
    params.set("status", selectedStatus);
    return params.toString();
  };

  const handleExportCSV = () => {
    window.location.href = `/api/export/csv?${buildExportParams()}`;
  };

  const handleExportExcel = () => {
    window.location.href = `/api/export/excel?${buildExportParams()}`;
  };

  return (
    <AppShell>
      <PageHeader
        title="Executive Safety Reports & Analytics"
        subtitle="Multi-constraint compliance analytics, worker violation tracking, and clean report exports."
        actions={[
          <button
            key="csv"
            onClick={handleExportCSV}
            className="display-title inline-flex items-center gap-1.5 rounded border border-border bg-panel px-3 py-1.5 text-xs text-foreground font-medium hover:bg-accent transition-colors shadow-sm"
          >
            <Download className="size-3.5 text-primary" /> Export CSV
          </button>,
          <button
            key="excel"
            onClick={handleExportExcel}
            className="display-title inline-flex items-center gap-1.5 rounded bg-primary px-3.5 py-1.5 text-xs text-primary-foreground font-semibold hover:bg-primary/90 transition-colors shadow"
          >
            <FileSpreadsheet className="size-4" /> Export Excel (.xlsx)
          </button>,
        ]}
      />

      {/* Multi-Constraint Filter Control Center */}
      <section className="mb-4 rounded panel-surface p-4 border border-border shadow-sm">
        <div className="flex items-center justify-between border-b border-border pb-2.5 mb-3">
          <div className="flex items-center gap-2">
            <Filter className="size-4 text-primary" />
            <h3 className="display-title text-sm text-foreground">Report Filter Controls</h3>
          </div>
          <button
            onClick={() => {
              setDateRange("all");
              setStartDate("");
              setEndDate("");
              setSelectedZone("all");
              setSelectedWorker("all");
              setSelectedStatus("all");
            }}
            className="telemetry text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            <RefreshCw className="size-3" /> Reset Filters
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {/* 1. Date Range Constraint */}
          <div>
            <label className="telemetry text-[11px] text-muted-foreground block mb-1">
              1. Date & Time Range
            </label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/80 px-3 py-1.5 text-xs outline-none focus:border-primary"
            >
              <option value="all">All Time History</option>
              <option value="daily">Today (Daily)</option>
              <option value="weekly">Past 7 Days (Weekly)</option>
              <option value="monthly">Past 30 Days (Monthly)</option>
              <option value="custom">Custom Date Range</option>
            </select>
          </div>

          {/* 2. Safety Zone Constraint */}
          <div>
            <label className="telemetry text-[11px] text-muted-foreground block mb-1">
              2. Safety Zone
            </label>
            <select
              value={selectedZone}
              onChange={(e) => setSelectedZone(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/80 px-3 py-1.5 text-xs outline-none focus:border-primary"
            >
              <option value="all">All Safety Zones</option>
              {ctxZones.map((z: any) => (
                <option key={z.id} value={z.id}>
                  {z.name} ({z.id})
                </option>
              ))}
            </select>
          </div>

          {/* 3. Worker Constraint */}
          <div>
            <label className="telemetry text-[11px] text-muted-foreground block mb-1">
              3. Tracked Worker
            </label>
            <select
              value={selectedWorker}
              onChange={(e) => setSelectedWorker(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/80 px-3 py-1.5 text-xs outline-none focus:border-primary"
            >
              <option value="all">All Workers</option>
              {ctxWorkers.map((w: any) => (
                <option key={w.id} value={w.id}>
                  {w.id} ({w.crew || "Worker"})
                </option>
              ))}
            </select>
          </div>

          {/* 4. Review Status Constraint */}
          <div>
            <label className="telemetry text-[11px] text-muted-foreground block mb-1">
              4. Review Status
            </label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/80 px-3 py-1.5 text-xs outline-none focus:border-primary"
            >
              <option value="all">All Statuses</option>
              <option value="unacknowledged">Unacknowledged Only</option>
              <option value="reviewed">Reviewed / Accepted Only</option>
            </select>
          </div>
        </div>

        {/* Custom Date Inputs if Custom Selected */}
        {dateRange === "custom" && (
          <div className="mt-3 grid grid-cols-2 gap-3 p-2.5 rounded bg-background/50 border border-border">
            <div>
              <span className="telemetry text-[10px] text-muted-foreground block mb-1">Start Date</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="telemetry w-full rounded border border-input bg-background px-2.5 py-1 text-xs outline-none focus:border-primary"
              />
            </div>
            <div>
              <span className="telemetry text-[10px] text-muted-foreground block mb-1">End Date</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="telemetry w-full rounded border border-input bg-background px-2.5 py-1 text-xs outline-none focus:border-primary"
              />
            </div>
          </div>
        )}
      </section>

      {/* Summary KPI Section */}
      <section className="grid gap-3 sm:grid-cols-4 mb-4">
        <StatCard
          label="Total Incidents"
          value={totalViolations}
          hint="Matching active filters"
          tone={totalViolations > 0 ? "danger" : "success"}
        />
        <StatCard
          label="Unacknowledged"
          value={unacknowledgedCount}
          hint="Requires safety review"
          tone={unacknowledgedCount > 0 ? "danger" : "success"}
        />
        <StatCard
          label="Reviewed / Accepted"
          value={reviewedCount}
          hint="Acknowledged events"
          tone="success"
        />
        <StatCard
          label="Unique Workers"
          value={uniqueWorkersCount}
          hint="Workers in filtered records"
          tone="warning"
        />
      </section>

      {/* Visual Analytics Section */}
      <section className="grid gap-3 lg:grid-cols-2 mb-4">
        <div className="rounded panel-surface p-4">
          <h2 className="display-title text-sm text-foreground mb-3">Incident Timeline Trend</h2>
          <div className="h-64">
            {dailyTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyTrend}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="period" stroke="var(--muted-foreground)" fontSize={11} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line
                    type="monotone"
                    dataKey="violations"
                    name="Violations"
                    stroke="var(--destructive)"
                    strokeWidth={2.5}
                    dot={{ r: 3, fill: "var(--destructive)" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                No incident data matching the current filter constraints.
              </div>
            )}
          </div>
        </div>

        <div className="rounded panel-surface p-4">
          <h2 className="display-title text-sm text-foreground mb-3">Violations by Safety Zone</h2>
          <div className="h-64">
            {violationsByZone.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={violationsByZone}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="zone" stroke="var(--muted-foreground)" fontSize={10} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" name="Violations" fill="var(--primary)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                No zone violation data matching the current filter constraints.
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Filtered Incident Audit Trail Table (Clean, NO image path dumps!) */}
      <section className="rounded panel-surface border border-border overflow-hidden">
        <div className="p-3 border-b border-border flex items-center justify-between bg-muted/20">
          <h3 className="display-title text-sm text-foreground">
            Filtered Incident Audit Trail ({totalViolations} Records)
          </h3>
          <span className="telemetry text-[11px] text-muted-foreground font-mono">
            Clean Report Format (Zero Image Path Clutter)
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] text-xs">
            <thead>
              <tr className="display-title border-b border-border text-left text-[10px] text-muted-foreground bg-muted/40">
                <th className="px-3 py-2.5">Event ID</th>
                <th className="px-3 py-2.5">Date & Time</th>
                <th className="px-3 py-2.5">Worker ID</th>
                <th className="px-3 py-2.5">Zone</th>
                <th className="px-3 py-2.5">Violated Stuff (Missing PPE)</th>
                <th className="px-3 py-2.5">Detected PPE</th>
                <th className="px-3 py-2.5">Conf %</th>
                <th className="px-3 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-muted-foreground animate-pulse">
                    Filtering safety records...
                  </td>
                </tr>
              ) : filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-muted-foreground">
                    No safety violation events found matching the selected filter constraints.
                  </td>
                </tr>
              ) : (
                filteredEvents.map((v) => (
                  <tr key={v.id} className="hover:bg-accent/40">
                    <td className="telemetry px-3 py-2.5 text-primary font-semibold font-mono">{v.id}</td>
                    <td className="telemetry px-3 py-2.5 text-muted-foreground font-mono">{v.timestamp}</td>
                    <td className="telemetry px-3 py-2.5 font-medium">{v.workerId}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{v.zoneId}</td>
                    <td className="px-3 py-2.5 text-destructive font-medium">
                      {v.missing && v.missing.length > 0 ? v.missing.join(", ") : v.type}
                    </td>
                    <td className="px-3 py-2.5 text-success">
                      {v.detected && v.detected.length > 0 ? v.detected.join(", ") : "None"}
                    </td>
                    <td className="telemetry px-3 py-2.5 font-mono">{(v.confidence * 100).toFixed(0)}%</td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`display-title rounded-sm px-2 py-0.5 text-[9px] ${
                          v.acknowledged
                            ? "bg-success/15 text-success border border-success/30"
                            : "bg-destructive/15 text-destructive border border-destructive/30"
                        }`}
                      >
                        {v.acknowledged ? "Reviewed" : "Unacknowledged"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
