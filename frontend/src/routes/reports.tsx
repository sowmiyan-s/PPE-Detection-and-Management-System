import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useMemo } from "react";
import { Download, FileSpreadsheet, Filter, Calendar, ShieldAlert, Check, RefreshCw, X, User, Loader2, Trash2, Eye, ExternalLink } from "lucide-react";
import { AppShell, PageHeader, StatCard } from "@/components/app-shell";
import { ConfirmModal } from "@/components/confirm-modal";
import { formatTime, zoneLabel } from "@/lib/mock-data";
import { useAppData } from "@/lib/data-context";
import { useToast } from "@/lib/toast-context";

export const Route = createFileRoute("/reports")({
  head: () => ({
    meta: [
      { title: "Safety Reports & Executive Analytics — Cerberus AI" },
      {
        name: "description",
        content:
          "Multi-constraint safety reporting, worker compliance metrics, zone analytics, evidence snapshots, and clean CSV/Excel exports.",
      },
    ],
  }),
  component: ReportsPage,
});

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
  imagePath?: string;
  imageBase64?: string;
}

function ReportsPage() {
  const { reports: ctxReports, zones: ctxZones, workers: ctxWorkers, violations: ctxViolations, refetchAll } = useAppData();
  const { showToast } = useToast();
  const [exportingCsv, setExportingCsv] = useState(false);
  const [exportingExcel, setExportingExcel] = useState(false);
  
  // Multi-Constraint Filter States
  const [dateRange, setDateRange] = useState<string>("all");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [selectedZone, setSelectedZone] = useState<string>("all");
  const [selectedWorker, setSelectedWorker] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");

  // Selection & Proof Modal States
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [purging, setPurging] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmPurgeBulk, setConfirmPurgeBulk] = useState(false);
  const [confirmDeleteSingle, setConfirmDeleteSingle] = useState<string | null>(null);
  const [proofModal, setProofModal] = useState<FilteredViolation | null>(null);

  const workerOptions = useMemo(() => {
    const map = new Map<string, string>();
    ctxWorkers.forEach((w: any) => {
      map.set(w.id, `${w.id} (${w.crew || w.name || "Worker"})`);
    });
    ctxViolations.forEach((v: any) => {
      if (v.workerId && !map.has(v.workerId)) {
        map.set(v.workerId, v.workerId);
      }
    });
    return Array.from(map.entries()).map(([id, label]) => ({ id, label }));
  }, [ctxWorkers, ctxViolations]);

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
          setSelectedIds([]);
        }
      })
      .catch((err) => console.error("Failed to load filtered violations", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchFilteredData();
  }, [dateRange, startDate, endDate, selectedZone, selectedWorker, selectedStatus]);

  // Bulk Selection Handlers
  const toggleSelectAll = () => {
    if (selectedIds.length === filteredEvents.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredEvents.map((v) => v.id));
    }
  };

  const toggleSelectRow = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  };

  // Single Record Deletion
  const handleDeleteSingle = (id: string) => {
    setDeletingId(id);
    fetch(`/api/violations/${encodeURIComponent(id)}`, { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to delete violation record");
        setFilteredEvents((prev) => prev.filter((v) => v.id !== id));
        setSelectedIds((prev) => prev.filter((item) => item !== id));
        showToast(`Violation record ${id} purged successfully`);
        refetchAll();
      })
      .catch((err) => {
        console.error("Delete violation error", err);
        showToast("Failed to purge violation record");
      })
      .finally(() => {
        setDeletingId(null);
        setConfirmDeleteSingle(null);
      });
  };

  // Bulk Record Purging
  const handlePurgeSelected = () => {
    if (selectedIds.length === 0) return;
    setPurging(true);
    fetch("/api/violations/purge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: selectedIds }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to purge selected records");
        return res.json();
      })
      .then(() => {
        showToast(`Successfully purged ${selectedIds.length} selected violation records`);
        setSelectedIds([]);
        fetchFilteredData();
        refetchAll();
      })
      .catch((err) => {
        console.error("Purge error", err);
        showToast("Failed to purge selected records");
      })
      .finally(() => {
        setPurging(false);
        setConfirmPurgeBulk(false);
      });
  };

  // Derived Analytics Metrics from Filtered Records
  const totalViolations = filteredEvents.length;
  const unacknowledgedCount = useMemo(() => filteredEvents.filter((v) => !v.acknowledged).length, [filteredEvents]);
  const reviewedCount = totalViolations - unacknowledgedCount;
  const uniqueWorkersCount = useMemo(() => new Set(filteredEvents.map((v) => v.workerId).filter(Boolean)).size, [filteredEvents]);

  const violationsByZone = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const v of filteredEvents) {
      const zid = v.zoneId || "General Plant Floor";
      counts[zid] = (counts[zid] || 0) + 1;
    }
    return Object.entries(counts).map(([zone, count]) => ({ zone, count }));
  }, [filteredEvents]);

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

  const handleExportCsv = () => {
    setExportingCsv(true);
    const query = buildExportParams();
    window.location.href = `/api/reports/export/csv?${query}`;
    setTimeout(() => setExportingCsv(false), 2000);
  };

  const handleExportExcel = () => {
    setExportingExcel(true);
    const query = buildExportParams();
    window.location.href = `/api/reports/export/excel?${query}`;
    setTimeout(() => setExportingExcel(false), 2000);
  };

  return (
    <AppShell>
      <PageHeader
        title="Safety Audit Reports & Proof of Evidence"
        actions={[
          selectedIds.length > 0 && (
            <button
              key="purge-selected"
              onClick={() => setConfirmPurgeBulk(true)}
              disabled={purging}
              className="flex items-center gap-1.5 rounded border border-destructive bg-destructive px-3 py-1.5 text-xs text-destructive-foreground hover:bg-destructive/90 transition-colors cursor-pointer"
            >
              {purging ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />}
              <span>Purge Selected ({selectedIds.length})</span>
            </button>
          ),
          <button
            key="export-csv"
            disabled={exportingCsv}
            onClick={handleExportCsv}
            className="flex items-center gap-1.5 rounded border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
          >
            {exportingCsv ? <Loader2 className="size-3.5 animate-spin" /> : <Download className="size-3.5 text-primary" />}
            <span>{exportingCsv ? "Exporting..." : "Export CSV"}</span>
          </button>,
          <button
            key="export-excel"
            disabled={exportingExcel}
            onClick={handleExportExcel}
            className="flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm disabled:opacity-50"
          >
            {exportingExcel ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
            <span>{exportingExcel ? "Generating..." : "Export Excel Report"}</span>
          </button>,
        ].filter(Boolean)}
      />

      {/* Multi-Constraint Filter Controls */}
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
            className="telemetry text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 cursor-pointer"
          >
            <RefreshCw className="size-3" /> Reset Filters
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="telemetry text-[11px] text-muted-foreground block mb-1 font-semibold">1. Time Range</label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/80 px-3 py-1.5 text-xs outline-none focus:border-primary cursor-pointer"
            >
              <option value="all">All Time History</option>
              <option value="hours">Last 24 Hours</option>
              <option value="daily">Today</option>
              <option value="weekly">Past 7 Days</option>
              <option value="monthly">Past 30 Days</option>
              <option value="custom">Custom Date Range</option>
            </select>
          </div>

          <div>
            <label className="telemetry text-[11px] text-muted-foreground block mb-1 font-semibold">2. Safety Zone</label>
            <select
              value={selectedZone}
              onChange={(e) => setSelectedZone(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/80 px-3 py-1.5 text-xs outline-none focus:border-primary cursor-pointer"
            >
              <option value="all">All Safety Zones</option>
              {ctxZones.map((z: any) => (
                <option key={z.id} value={z.id}>
                  {z.name} ({z.id})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="telemetry text-[11px] text-muted-foreground block mb-1 font-semibold">3. Tracked Worker</label>
            <select
              value={selectedWorker}
              onChange={(e) => setSelectedWorker(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/80 px-3 py-1.5 text-xs outline-none focus:border-primary cursor-pointer"
            >
              <option value="all">All Tracked Workers ({workerOptions.length})</option>
              {workerOptions.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="telemetry text-[11px] text-muted-foreground block mb-1 font-semibold">4. Review Status</label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="telemetry w-full rounded border border-input bg-background/80 px-3 py-1.5 text-xs outline-none focus:border-primary cursor-pointer"
            >
              <option value="all">All Statuses</option>
              <option value="unacknowledged">Unacknowledged Only</option>
              <option value="reviewed">Reviewed / Accepted Only</option>
            </select>
          </div>
        </div>
      </section>

      {/* Overview Stat Cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-4">
        <StatCard label="Filtered Incidents" value={totalViolations} hint={`${unacknowledgedCount} unacknowledged`} icon={ShieldAlert} tone="danger" />
        <StatCard label="Unique Workers" value={uniqueWorkersCount} hint="Workers tracked in range" icon={User} tone="warning" />
        <StatCard label="Reviewed Events" value={reviewedCount} hint={`${totalViolations > 0 ? ((reviewedCount / totalViolations) * 100).toFixed(0) : 100}% reviewed`} icon={Check} tone="success" />
        <StatCard label="Active Zones" value={violationsByZone.length} hint="Zones with incidents" icon={Calendar} tone="default" />
      </div>

      {/* Audit Trail Table with Proof of Evidence & Purge */}
      <section className="rounded panel-surface border border-border overflow-hidden">
        <div className="p-3 border-b border-border flex flex-wrap items-center justify-between gap-2 bg-muted/20">
          <div className="flex items-center gap-2">
            <h3 className="display-title text-sm text-foreground">
              Incident Audit Trail ({totalViolations} Records)
            </h3>
          </div>
          <span className="telemetry text-[11px] text-muted-foreground font-mono">
            Timestamps rendered in IST (GMT+0530)
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-xs">
            <thead>
              <tr className="display-title border-b border-border text-left text-[10px] text-muted-foreground bg-muted/40">
                <th className="px-3 py-2.5 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={filteredEvents.length > 0 && selectedIds.length === filteredEvents.length}
                    onChange={toggleSelectAll}
                    className="rounded border-border text-primary focus:ring-0 cursor-pointer"
                  />
                </th>
                <th className="px-3 py-2.5">Event ID</th>
                <th className="px-3 py-2.5">Evidence</th>
                <th className="px-3 py-2.5">Date & Time (IST)</th>
                <th className="px-3 py-2.5">Worker ID</th>
                <th className="px-3 py-2.5">Zone</th>
                <th className="px-3 py-2.5">Missing PPE</th>
                <th className="px-3 py-2.5">Conf %</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td colSpan={10} className="px-3 py-8 text-center text-muted-foreground animate-pulse">
                    Filtering safety records...
                  </td>
                </tr>
              ) : filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-3 py-8 text-center text-muted-foreground">
                    No safety violation events found matching the selected filter constraints.
                  </td>
                </tr>
              ) : (
                filteredEvents.map((v) => (
                  <tr key={v.id} className={`hover:bg-accent/40 ${selectedIds.includes(v.id) ? "bg-primary/5" : ""}`}>
                    <td className="px-3 py-2.5 text-center">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(v.id)}
                        onChange={() => toggleSelectRow(v.id)}
                        className="rounded border-border text-primary focus:ring-0 cursor-pointer"
                      />
                    </td>
                    <td className="telemetry px-3 py-2.5 text-primary font-semibold font-mono">{v.id}</td>
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => setProofModal(v)}
                        className="inline-flex items-center gap-1 rounded border border-primary/40 bg-primary/10 px-2 py-1 text-[11px] font-semibold text-primary hover:bg-primary hover:text-primary-foreground transition-colors cursor-pointer"
                      >
                        <Eye className="size-3" /> View Proof
                      </button>
                    </td>
                    <td className="telemetry px-3 py-2.5 text-muted-foreground font-mono">{formatTime(v.timestamp)}</td>
                    <td className="telemetry px-3 py-2.5 font-medium">{v.workerId}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{zoneLabel(v.zoneId)}</td>
                    <td className="px-3 py-2.5 text-destructive font-medium">
                      {v.missing && v.missing.length > 0 ? v.missing.join(", ") : v.type}
                    </td>
                    <td className="telemetry px-3 py-2.5 font-mono">{(v.confidence * 100).toFixed(0)}%</td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`display-title rounded-sm px-2 py-0.5 text-[9px] ${
                          v.status === "REJECTED"
                            ? "bg-muted text-muted-foreground border border-border"
                            : v.acknowledged
                            ? "bg-success/15 text-success border border-success/30"
                            : "bg-destructive/15 text-destructive border border-destructive/30"
                        }`}
                      >
                        {v.status === "REJECTED" ? "REJECTED" : v.acknowledged ? "Reviewed" : "Unacknowledged"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <button
                        onClick={() => setConfirmDeleteSingle(v.id)}
                        disabled={deletingId === v.id}
                        title="Purge Record"
                        className="rounded border border-destructive/30 bg-destructive/10 p-1 text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors cursor-pointer"
                      >
                        {deletingId === v.id ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Proof of Evidence Snapshot Modal */}
      {proofModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl rounded-lg border border-border panel-surface shadow-2xl p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-2.5">
              <div>
                <h3 className="display-title text-base font-bold text-foreground">
                  Proof of Evidence — Event {proofModal.id}
                </h3>
                <p className="telemetry text-xs text-muted-foreground">
                  Recorded Frame Snapshot • Worker: <span className="text-primary font-semibold">{proofModal.workerId}</span>
                </p>
              </div>
              <button
                onClick={() => setProofModal(null)}
                className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-accent cursor-pointer"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="aspect-video w-full overflow-hidden rounded border border-border bg-black/60 flex items-center justify-center">
              {proofModal.imageBase64 ? (
                <img
                  src={proofModal.imageBase64.startsWith("data:") ? proofModal.imageBase64 : `data:image/jpeg;base64,${proofModal.imageBase64}`}
                  alt={`Evidence Snapshot for ${proofModal.id}`}
                  className="max-h-full max-w-full object-contain"
                />
              ) : proofModal.imagePath ? (
                <img
                  src={`/api/evidence/${encodeURIComponent(proofModal.imagePath)}`}
                  alt={`Evidence Snapshot for ${proofModal.id}`}
                  className="max-h-full max-w-full object-contain"
                />
              ) : (
                <div className="text-center p-8 text-muted-foreground">
                  <ShieldAlert className="size-10 mx-auto text-muted-foreground/50 mb-2" />
                  <p className="text-sm">No visual frame snapshot saved for this event.</p>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs border-t border-border pt-3">
              <div>
                <span className="text-muted-foreground block">Safety Zone:</span>
                <span className="font-semibold text-foreground">{zoneLabel(proofModal.zoneId)}</span>
              </div>
              <div>
                <span className="text-muted-foreground block">Missing PPE:</span>
                <span className="font-semibold text-destructive font-mono">
                  {proofModal.missing?.length ? proofModal.missing.join(", ") : proofModal.type}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground block">Timestamp:</span>
                <span className="font-mono text-foreground">{formatTime(proofModal.timestamp)}</span>
              </div>
              <div>
                <span className="text-muted-foreground block">Model Confidence:</span>
                <span className="font-mono font-semibold text-primary">{(proofModal.confidence * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modals */}
      <ConfirmModal
        isOpen={confirmPurgeBulk}
        title={`Purge ${selectedIds.length} Violation Records`}
        message={`Are you sure you want to permanently delete ${selectedIds.length} selected violation evidence records?`}
        confirmText="Purge Selected Records"
        cancelText="Cancel"
        variant="danger"
        isLoading={purging}
        onConfirm={handlePurgeSelected}
        onCancel={() => setConfirmPurgeBulk(false)}
      />

      <ConfirmModal
        isOpen={!!confirmDeleteSingle}
        title={`Delete Violation Record: ${confirmDeleteSingle || ""}`}
        message={`Are you sure you want to permanently purge violation record '${confirmDeleteSingle}'?`}
        confirmText="Purge Record"
        cancelText="Cancel"
        variant="danger"
        isLoading={deletingId !== null}
        onConfirm={() => confirmDeleteSingle && handleDeleteSingle(confirmDeleteSingle)}
        onCancel={() => setConfirmDeleteSingle(null)}
      />
    </AppShell>
  );
}
