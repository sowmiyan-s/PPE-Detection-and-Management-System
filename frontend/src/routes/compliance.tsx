import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useMemo } from "react";
import {
  Trash2,
  Loader2,
  RefreshCw,
  Eye,
  Ban,
  CheckCircle2,
  ShieldAlert,
  X,
  CheckSquare,
  Square,
  AlertTriangle,
  Camera,
  Layers,
  Sparkles,
  Filter,
} from "lucide-react";

import { AppShell, PageHeader } from "@/components/app-shell";
import { ConfirmModal } from "@/components/confirm-modal";
import { formatTime, zoneLabel, type Worker, type ViolationEvent } from "@/lib/mock-data";
import { useToast } from "@/lib/toast-context";
import { useAppData } from "@/lib/data-context";

export const Route = createFileRoute("/compliance")({
  head: () => ({
    meta: [
      { title: "Worker Compliance & Evidence Proof Management — Cerberus AI" },
      {
        name: "description",
        content:
          "Per-worker PPE compliance scorecards, visual evidence gallery, selective violation deletion, and evidence rejection controls.",
      },
    ],
  }),
  component: CompliancePage,
});

function Ring({ value }: { value: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const tone = value >= 90 ? "var(--success)" : value >= 80 ? "var(--primary)" : "var(--destructive)";
  return (
    <svg viewBox="0 0 130 130" className="size-36">
      <circle cx="65" cy="65" r={r} fill="none" stroke="var(--border)" strokeWidth="12" />
      <circle
        cx="65"
        cy="65"
        r={r}
        fill="none"
        stroke={tone}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={`${(value / 100) * c} ${c}`}
        transform="rotate(-90 65 65)"
      />
      <text
        x="65"
        y="71"
        textAnchor="middle"
        fill="var(--foreground)"
        style={{ font: "600 26px var(--font-mono)" }}
      >
        {value}%
      </text>
    </svg>
  );
}

function CompliancePage() {
  const { showToast } = useToast();
  const { refetchAll } = useAppData();
  const [workerList, setWorkerList] = useState<Worker[]>([]);
  const [violations, setViolations] = useState<ViolationEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  // Selection state for selective violation deletion
  const [selectedViolationIds, setSelectedViolationIds] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState<"ALL" | "FLAGGED" | "REJECTED">("ALL");

  // Deletion and action loaders
  const [deletingWorkerId, setDeletingWorkerId] = useState<string | null>(null);
  const [deletingViolationId, setDeletingViolationId] = useState<string | null>(null);
  const [purgingSelected, setPurgingSelected] = useState(false);
  const [clearingWorkerViolations, setClearingWorkerViolations] = useState(false);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [clearingAll, setClearingAll] = useState(false);

  // Confirmation modals
  const [confirmDeleteWorker, setConfirmDeleteWorker] = useState<string | null>(null);
  const [confirmDeleteSingleViolation, setConfirmDeleteSingleViolation] = useState<string | null>(null);
  const [confirmPurgeSelected, setConfirmPurgeSelected] = useState(false);
  const [confirmClearWorkerViolations, setConfirmClearWorkerViolations] = useState<string | null>(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);

  // Evidence preview modal
  const [previewEvidence, setPreviewEvidence] = useState<ViolationEvent | null>(null);

  const fetchData = () => {
    setLoading(true);
    Promise.allSettled([
      fetch("/api/workers").then((res) => (res.ok ? res.json() : [])),
      fetch("/api/violations?limit=1000").then((res) => (res.ok ? res.json() : [])),
    ]).then(([workersRes, violationsRes]) => {
      if (workersRes.status === "fulfilled" && Array.isArray(workersRes.value)) {
        setWorkerList(workersRes.value);
        if (workersRes.value.length > 0 && !selectedId) {
          setSelectedId(workersRes.value[0].id);
        }
      }
      if (violationsRes.status === "fulfilled" && Array.isArray(violationsRes.value)) {
        setViolations(violationsRes.value);
      }
      setLoading(false);
    });
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Clear selections whenever active worker changes
  useEffect(() => {
    setSelectedViolationIds(new Set());
  }, [selectedId]);

  const selected = workerList.find((w) => w.id === selectedId) || workerList[0];

  // Incidents belonging to selected worker
  const incidents = useMemo(() => {
    if (!selected) return [];
    const wIdLower = (selected.id || "").toLowerCase().trim();
    return violations.filter((v) => {
      const vWorker = (v.workerId || "").toLowerCase().trim();
      return vWorker === wIdLower || (wIdLower.startsWith("worker-") && vWorker.endsWith(wIdLower.replace("worker-", "")));
    });
  }, [selected, violations]);

  // Filtered incidents based on tab (ALL, FLAGGED, REJECTED)
  const displayedIncidents = useMemo(() => {
    if (statusFilter === "FLAGGED") {
      return incidents.filter((i) => (i.status || "").toUpperCase() !== "REJECTED");
    }
    if (statusFilter === "REJECTED") {
      return incidents.filter((i) => (i.status || "").toUpperCase() === "REJECTED");
    }
    return incidents;
  }, [incidents, statusFilter]);

  // Toggle selection for a single violation
  const toggleSelectViolation = (vId: string) => {
    setSelectedViolationIds((prev) => {
      const next = new Set(prev);
      if (next.has(vId)) {
        next.delete(vId);
      } else {
        next.add(vId);
      }
      return next;
    });
  };

  // Select all or deselect all displayed incidents
  const toggleSelectAll = () => {
    if (selectedViolationIds.size === displayedIncidents.length && displayedIncidents.length > 0) {
      setSelectedViolationIds(new Set());
    } else {
      setSelectedViolationIds(new Set(displayedIncidents.map((i) => i.id)));
    }
  };

  // Recalculate and update worker state locally
  const updateWorkerLocalCompliance = (wId: string, removedCount: number) => {
    setWorkerList((prev) =>
      prev.map((w) => {
        if (w.id === wId) {
          const newIncidents = Math.max(0, (w.incidents || incidents.length) - removedCount);
          const newCompliance = Math.min(100, Math.max(50, Math.round(100 - newIncidents * 8)));
          return {
            ...w,
            incidents: newIncidents,
            compliance: newCompliance,
          };
        }
        return w;
      })
    );
  };

  // 1. Delete a single violation
  const handleDeleteSingleViolation = (vId: string) => {
    setDeletingViolationId(vId);
    fetch(`/api/violations/${encodeURIComponent(vId)}`, { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to delete violation");
        showToast(`Violation '${vId}' deleted successfully`);
        setViolations((prev) => prev.filter((v) => v.id !== vId));
        setSelectedViolationIds((prev) => {
          const next = new Set(prev);
          next.delete(vId);
          return next;
        });
        if (selected) {
          updateWorkerLocalCompliance(selected.id, 1);
        }
        refetchAll();
      })
      .catch((err) => {
        console.error("Delete violation error", err);
        showToast("Failed to delete violation record");
      })
      .finally(() => {
        setDeletingViolationId(null);
        setConfirmDeleteSingleViolation(null);
      });
  };

  // 2. Selective batch deletion of multiple picked violations
  const handlePurgeSelectedViolations = () => {
    const idsToPurge = Array.from(selectedViolationIds);
    if (idsToPurge.length === 0) return;

    setPurgingSelected(true);
    fetch("/api/violations/purge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: idsToPurge }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to purge selected violations");
        return res.json();
      })
      .then(() => {
        showToast(`Deleted ${idsToPurge.length} selected violation(s)`);
        setViolations((prev) => prev.filter((v) => !selectedViolationIds.has(v.id)));
        if (selected) {
          updateWorkerLocalCompliance(selected.id, idsToPurge.length);
        }
        setSelectedViolationIds(new Set());
        refetchAll();
      })
      .catch((err) => {
        console.error("Purge violations error", err);
        showToast("Failed to delete selected violations");
      })
      .finally(() => {
        setPurgingSelected(false);
        setConfirmPurgeSelected(false);
      });
  };

  // 3. Clear all violations for this specific worker
  const handleClearWorkerViolations = (wId: string) => {
    setClearingWorkerViolations(true);
    fetch(`/api/workers/${encodeURIComponent(wId)}/violations`, { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to clear worker violations");
        showToast(`All violation reports cleared for ${selected?.name || wId}`);
        setViolations((prev) =>
          prev.filter((v) => {
            const vWorker = (v.workerId || "").toLowerCase().trim();
            const wIdLower = wId.toLowerCase().trim();
            return vWorker !== wIdLower && !vWorker.endsWith(wIdLower.replace("worker-", ""));
          })
        );
        setSelectedViolationIds(new Set());
        setWorkerList((prev) =>
          prev.map((w) => (w.id === wId ? { ...w, incidents: 0, compliance: 100 } : w))
        );
        refetchAll();
      })
      .catch((err) => {
        console.error("Clear worker violations error", err);
        showToast("Failed to clear violations for worker");
      })
      .finally(() => {
        setClearingWorkerViolations(false);
        setConfirmClearWorkerViolations(null);
      });
  };

  // 4. Delete entire worker entry
  const handleDeleteWorker = (wId: string) => {
    setDeletingWorkerId(wId);
    fetch(`/api/workers/${encodeURIComponent(wId)}`, { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to delete worker");
        showToast(`Worker record '${wId}' deleted successfully`);
        setWorkerList((prev) => prev.filter((w) => w.id !== wId));
        setViolations((prev) => prev.filter((v) => v.workerId !== wId));
        if (selectedId === wId) {
          const remaining = workerList.filter((w) => w.id !== wId);
          setSelectedId(remaining.length > 0 ? (remaining[0]?.id ?? "") : "");
        }
        refetchAll();
      })
      .catch((err) => {
        console.error("Delete worker error", err);
        showToast("Failed to delete worker entry");
      })
      .finally(() => {
        setDeletingWorkerId(null);
        setConfirmDeleteWorker(null);
      });
  };

  // 5. Reject evidence record
  const handleRejectEvidence = (vId: string) => {
    setRejectingId(vId);
    fetch(`/api/violations/${encodeURIComponent(vId)}/reject`, { method: "POST" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to reject evidence");
        return res.json();
      })
      .then(() => {
        showToast(`Evidence record '${vId}' marked as REJECTED`);
        setViolations((prev) =>
          prev.map((v) => (v.id === vId ? { ...v, status: "REJECTED" } : v))
        );
        refetchAll();
      })
      .catch((err) => {
        console.error("Reject evidence error", err);
        showToast("Failed to reject evidence record");
      })
      .finally(() => setRejectingId(null));
  };

  // 6. Clear all workers in database
  const handleClearAllWorkers = () => {
    setClearingAll(true);
    fetch("/api/workers", { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to clear worker data");
        showToast("All worker compliance records cleared");
        setWorkerList([]);
        setViolations([]);
        setSelectedId("");
        setSelectedViolationIds(new Set());
        refetchAll();
      })
      .catch((err) => {
        console.error("Clear all workers error", err);
        showToast("Failed to clear worker records");
      })
      .finally(() => {
        setClearingAll(false);
        setConfirmClearAll(false);
      });
  };

  const getSnapshotUrl = (item: ViolationEvent) => {
    if (item.imageBase64) {
      return item.imageBase64.startsWith("data:")
        ? item.imageBase64
        : `data:image/jpeg;base64,${item.imageBase64}`;
    }
    if (item.imagePath) {
      return `/api/evidence/${encodeURIComponent(item.imagePath)}`;
    }
    return null;
  };

  const isAllSelected =
    displayedIncidents.length > 0 && selectedViolationIds.size === displayedIncidents.length;

  return (
    <AppShell>
      <PageHeader
        title="Worker Compliance & Evidence Proof Management"
        subtitle="Individual worker PPE scorecards, visual evidence gallery, and selective violation removal."
        actions={[
          workerList.length > 0 && (
            <button
              key="clear-all-workers"
              onClick={() => setConfirmClearAll(true)}
              disabled={clearingAll}
              className="flex items-center gap-1.5 rounded border border-destructive bg-destructive px-3 py-1.5 text-xs text-destructive-foreground hover:bg-destructive/90 transition-colors cursor-pointer"
            >
              {clearingAll ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />}
              <span>Reset All Workers</span>
            </button>
          ),
          <button
            key="refresh-workers"
            onClick={fetchData}
            className="flex items-center gap-1.5 rounded border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors cursor-pointer"
          >
            <RefreshCw className="size-3.5 text-primary" />
            <span>Refresh</span>
          </button>,
        ].filter(Boolean)}
      />

      {loading ? (
        <div className="rounded panel-surface p-12 text-center text-muted-foreground animate-pulse">
          Loading worker compliance database and evidence proofs...
        </div>
      ) : workerList.length === 0 ? (
        <div className="rounded panel-surface p-12 text-center text-muted-foreground">
          <p className="text-sm font-semibold">No worker tracking records found.</p>
          <p className="text-xs mt-1">Worker scorecards and evidence snapshots will appear in real-time as the YOLO AI pipeline detects personnel.</p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1.1fr_1.3fr]">
          {/* Worker List Table */}
          <div className="overflow-x-auto rounded-lg panel-surface border border-border">
            <div className="border-b border-border bg-muted/30 px-3 py-2.5 flex items-center justify-between">
              <span className="display-title text-xs font-bold text-foreground">Tracked Personnel ({workerList.length})</span>
              <span className="telemetry text-[11px] text-muted-foreground">Select worker to inspect proof</span>
            </div>
            <table className="w-full min-w-[500px] text-sm">
              <thead>
                <tr className="display-title border-b border-border text-left text-[10px] text-muted-foreground bg-muted/40">
                  <th className="px-3 py-2.5">Worker</th>
                  <th className="px-3 py-2.5">Crew</th>
                  <th className="px-3 py-2.5">Primary zone</th>
                  <th className="px-3 py-2.5">Violations</th>
                  <th className="px-3 py-2.5">Compliance</th>
                  <th className="px-3 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {workerList.map((w) => (
                  <tr
                    key={w.id}
                    onClick={() => setSelectedId(w.id)}
                    className={`cursor-pointer hover:bg-accent/40 transition-colors ${
                      w.id === selected?.id ? "bg-accent/60 font-semibold" : ""
                    }`}
                  >
                    <td className="px-3 py-2.5">
                      <div className="font-medium text-foreground">{w.name}</div>
                      <div className="telemetry text-[11px] text-muted-foreground font-mono">{w.id}</div>
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">{w.crew}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{zoneLabel(w.primaryZone)}</td>
                    <td className="telemetry px-3 py-2.5 font-mono">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-bold ${
                        w.incidents > 0 ? "bg-destructive/20 text-destructive border border-destructive/30" : "bg-success/20 text-success"
                      }`}>
                        {w.incidents}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
                          <div
                            className={`h-full rounded-full ${
                              w.compliance >= 90
                                ? "bg-success"
                                : w.compliance >= 80
                                  ? "bg-primary"
                                  : "bg-destructive"
                            }`}
                            style={{ width: `${w.compliance}%` }}
                          />
                        </div>
                        <span className="telemetry text-xs font-mono">{w.compliance}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDeleteWorker(w.id);
                        }}
                        disabled={deletingWorkerId === w.id}
                        title="Delete Worker Profile"
                        className="rounded border border-destructive/30 bg-destructive/10 p-1 text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors cursor-pointer"
                      >
                        {deletingWorkerId === w.id ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Worker Compliance Scorecard & Visual Evidence Gallery */}
          {selected && (
            <aside className="rounded-lg panel-surface p-4 border border-border flex flex-col space-y-4">
              {/* Header Profile */}
              <div>
                <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
                  <div>
                    <h2 className="display-title text-lg font-bold">{selected.name}</h2>
                    <p className="telemetry text-[11px] text-muted-foreground font-mono">
                      {selected.id} · {selected.crew} · Shift: {selected.shift}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {incidents.length > 0 && (
                      <button
                        onClick={() => setConfirmClearWorkerViolations(selected.id)}
                        disabled={clearingWorkerViolations}
                        className="flex items-center gap-1 rounded border border-warning/40 bg-warning/10 px-2 py-1 text-xs text-warning hover:bg-warning hover:text-warning-foreground transition-colors cursor-pointer"
                        title="Remove all violation reports for this worker"
                      >
                        {clearingWorkerViolations ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                        <span>Clear All Violations</span>
                      </button>
                    )}
                    <button
                      onClick={() => setConfirmDeleteWorker(selected.id)}
                      disabled={deletingWorkerId === selected.id}
                      className="flex items-center gap-1 rounded border border-destructive/30 bg-destructive/10 px-2 py-1 text-xs text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors cursor-pointer"
                      title="Delete worker record completely"
                    >
                      <Trash2 className="size-3" />
                      <span>Delete Worker</span>
                    </button>
                  </div>
                </div>

                {/* Ring & Quick Stats */}
                <div className="mt-3 grid grid-cols-[auto_1fr] items-center gap-4">
                  <div className="grid place-items-center">
                    <Ring value={selected.compliance} />
                  </div>
                  <dl className="telemetry grid grid-cols-2 gap-2 text-xs">
                    {[
                      ["Assigned Zone", zoneLabel(selected.primaryZone)],
                      ["Hours Tracked", `${selected.hoursTracked} h`],
                      ["Total Violations", String(incidents.length)],
                      ["Selected to Remove", String(selectedViolationIds.size)],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded border border-border bg-background/50 p-2">
                        <dt className="text-muted-foreground text-[10px] uppercase tracking-wider">{k}</dt>
                        <dd className="mt-0.5 text-foreground font-semibold font-mono text-sm">{v}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </div>

              {/* Evidence Management Bar & Selective Controls */}
              <div className="border-t border-border pt-3">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
                  <div className="flex items-center gap-2">
                    <h3 className="display-title text-xs font-bold text-foreground flex items-center gap-1.5">
                      <Camera className="size-4 text-primary" />
                      <span>Evidence Proof Gallery ({displayedIncidents.length})</span>
                    </h3>
                    <div className="flex items-center gap-1 rounded border border-border bg-background/60 p-0.5 text-[10px]">
                      {(["ALL", "FLAGGED", "REJECTED"] as const).map((tab) => (
                        <button
                          key={tab}
                          onClick={() => setStatusFilter(tab)}
                          className={`rounded px-1.5 py-0.5 transition-colors cursor-pointer ${
                            statusFilter === tab
                              ? "bg-primary text-primary-foreground font-bold"
                              : "text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {tab}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Selective Batch Actions */}
                  <div className="flex items-center gap-2">
                    {displayedIncidents.length > 0 && (
                      <button
                        onClick={toggleSelectAll}
                        className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                      >
                        {isAllSelected ? <CheckSquare className="size-3.5 text-primary" /> : <Square className="size-3.5" />}
                        <span>{isAllSelected ? "Deselect All" : "Select All"}</span>
                      </button>
                    )}

                    {selectedViolationIds.size > 0 && (
                      <button
                        onClick={() => setConfirmPurgeSelected(true)}
                        disabled={purgingSelected}
                        className="flex items-center gap-1 rounded border border-destructive bg-destructive px-2.5 py-1 text-xs font-bold text-destructive-foreground hover:bg-destructive/90 transition-colors cursor-pointer shadow-sm animate-pulse"
                      >
                        {purgingSelected ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                        <span>Delete Selected ({selectedViolationIds.size})</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Evidence Proof Cards Grid / List */}
                <div className="mt-2 space-y-2.5 max-h-96 overflow-y-auto pr-1">
                  {displayedIncidents.length === 0 ? (
                    <div className="text-xs text-muted-foreground py-8 text-center rounded border border-dashed border-border bg-background/30">
                      <ShieldAlert className="size-6 text-muted-foreground/50 mx-auto mb-1" />
                      <p>No violation evidence recorded for this worker under '{statusFilter}'.</p>
                    </div>
                  ) : (
                    displayedIncidents.map((i) => {
                      const isSelected = selectedViolationIds.has(i.id);
                      const imgUrl = getSnapshotUrl(i);
                      const isRejected = (i.status || "").toUpperCase() === "REJECTED";

                      return (
                        <div
                          key={i.id}
                          onClick={() => toggleSelectViolation(i.id)}
                          className={`group relative rounded-lg border p-3 transition-all cursor-pointer ${
                            isSelected
                              ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                              : "border-border bg-background/60 hover:bg-accent/40"
                          }`}
                        >
                          <div className="grid grid-cols-[auto_1fr] gap-3 items-start">
                            {/* Checkbox & Thumbnail */}
                            <div className="flex flex-col items-center gap-2">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleSelectViolation(i.id);
                                }}
                                className="text-muted-foreground hover:text-primary transition-colors cursor-pointer"
                              >
                                {isSelected ? (
                                  <CheckSquare className="size-4 text-primary" />
                                ) : (
                                  <Square className="size-4 text-muted-foreground" />
                                )}
                              </button>

                              {/* Snapshot Thumbnail Preview */}
                              <div
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setPreviewEvidence(i);
                                }}
                                className="relative size-16 overflow-hidden rounded border border-border bg-black/80 flex items-center justify-center cursor-zoom-in group/thumb"
                                title="Click to enlarge snapshot proof"
                              >
                                {imgUrl ? (
                                  <>
                                    <img
                                      src={imgUrl}
                                      alt={`Proof ${i.id}`}
                                      className="size-full object-cover group-hover/thumb:scale-110 transition-transform duration-300"
                                    />
                                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/thumb:opacity-100 flex items-center justify-center transition-opacity">
                                      <Eye className="size-4 text-white drop-shadow" />
                                    </div>
                                  </>
                                ) : (
                                  <Camera className="size-6 text-muted-foreground/40" />
                                )}
                              </div>
                            </div>

                            {/* Violation Details & Proof Metadata */}
                            <div className="space-y-1.5 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="text-xs font-bold text-destructive flex items-center gap-1">
                                    <AlertTriangle className="size-3.5" />
                                    {i.type}
                                  </span>
                                  {i.confidence > 0 && (
                                    <span className="telemetry rounded bg-muted px-1.5 py-0.2 text-[10px] font-mono text-muted-foreground">
                                      {Math.round(i.confidence * 100)}% conf
                                    </span>
                                  )}
                                </div>
                                <span
                                  className={`rounded px-1.5 py-0.5 text-[9px] font-mono font-bold ${
                                    isRejected
                                      ? "bg-muted text-muted-foreground border border-border"
                                      : "bg-destructive/15 text-destructive border border-destructive/30"
                                  }`}
                                >
                                  {isRejected ? "REJECTED" : "FLAGGED"}
                                </span>
                              </div>

                              <div className="telemetry text-[11px] text-muted-foreground font-mono flex items-center justify-between gap-2">
                                <span>{i.id} · {zoneLabel(i.zoneId)} ({i.cameraId || "CAM-01"})</span>
                                <span>{formatTime(i.timestamp)}</span>
                              </div>

                              {/* Missing and Detected PPE Badges */}
                              <div className="flex flex-wrap gap-1 pt-0.5">
                                {i.missing && i.missing.length > 0 && (
                                  i.missing.map((m, idx) => (
                                    <span
                                      key={idx}
                                      className="rounded bg-destructive/10 text-destructive border border-destructive/25 px-1.5 py-0.5 text-[9px] font-mono font-medium"
                                    >
                                      Missing: {m}
                                    </span>
                                  ))
                                )}
                                {i.detected && i.detected.length > 0 && (
                                  i.detected.map((d, idx) => (
                                    <span
                                      key={idx}
                                      className="rounded bg-success/10 text-success border border-success/25 px-1.5 py-0.5 text-[9px] font-mono font-medium"
                                    >
                                      Detected: {d}
                                    </span>
                                  ))
                                )}
                              </div>

                              {/* Action Buttons */}
                              <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/40">
                                {imgUrl && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setPreviewEvidence(i);
                                    }}
                                    className="inline-flex items-center gap-1 rounded border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary hover:bg-primary hover:text-primary-foreground transition-colors cursor-pointer"
                                  >
                                    <Eye className="size-3" /> Inspect Proof
                                  </button>
                                )}

                                {!isRejected && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleRejectEvidence(i.id);
                                    }}
                                    disabled={rejectingId === i.id}
                                    className="inline-flex items-center gap-1 rounded border border-warning/40 bg-warning/10 px-2 py-0.5 text-[10px] font-semibold text-warning hover:bg-warning hover:text-warning-foreground transition-colors cursor-pointer"
                                  >
                                    {rejectingId === i.id ? <Loader2 className="size-3 animate-spin" /> : <Ban className="size-3" />}
                                    Reject
                                  </button>
                                )}

                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setConfirmDeleteSingleViolation(i.id);
                                  }}
                                  disabled={deletingViolationId === i.id}
                                  title="Delete this violation report"
                                  className="inline-flex items-center gap-1 rounded border border-destructive/40 bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors cursor-pointer"
                                >
                                  {deletingViolationId === i.id ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                                  Delete
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </aside>
          )}
        </div>
      )}

      {/* Snapshot Preview Modal */}
      {previewEvidence && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-2xl rounded-lg border border-border panel-surface shadow-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <h3 className="display-title text-base font-bold flex items-center gap-2">
                  <ShieldAlert className="size-4 text-destructive" />
                  Evidence Proof Analysis — Event {previewEvidence.id}
                </h3>
                <p className="telemetry text-xs text-muted-foreground font-mono mt-0.5">
                  Worker: {previewEvidence.workerId} · Zone: {zoneLabel(previewEvidence.zoneId)} · Camera: {previewEvidence.cameraId || "CAM-01"}
                </p>
              </div>
              <button
                onClick={() => setPreviewEvidence(null)}
                className="rounded p-1 text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* High-Res Snapshot Image */}
            <div className="aspect-video w-full overflow-hidden rounded-lg border border-border bg-black/90 flex items-center justify-center relative">
              {getSnapshotUrl(previewEvidence) ? (
                <img
                  src={getSnapshotUrl(previewEvidence)!}
                  alt={`Full Snapshot ${previewEvidence.id}`}
                  className="max-h-full max-w-full object-contain"
                />
              ) : (
                <div className="text-center text-muted-foreground text-xs">
                  <Camera className="size-8 mx-auto mb-1 opacity-40" />
                  No high-resolution snapshot captured for this event
                </div>
              )}
            </div>

            {/* Metadata Summary & Actions */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
              <div className="flex flex-wrap gap-1.5 text-xs font-mono">
                <span className="rounded bg-destructive/15 text-destructive border border-destructive/30 px-2 py-0.5 font-bold">
                  {previewEvidence.type}
                </span>
                <span className="rounded bg-muted text-foreground px-2 py-0.5">
                  {formatTime(previewEvidence.timestamp)}
                </span>
                {previewEvidence.confidence > 0 && (
                  <span className="rounded bg-primary/15 text-primary border border-primary/30 px-2 py-0.5">
                    Confidence: {(previewEvidence.confidence * 100).toFixed(1)}%
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const id = previewEvidence.id;
                    setPreviewEvidence(null);
                    setConfirmDeleteSingleViolation(id);
                  }}
                  className="flex items-center gap-1 rounded border border-destructive bg-destructive px-3 py-1.5 text-xs font-bold text-destructive-foreground hover:bg-destructive/90 transition-colors cursor-pointer"
                >
                  <Trash2 className="size-3.5" />
                  Delete Violation
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modals */}
      <ConfirmModal
        isOpen={!!confirmDeleteWorker}
        title={`Delete Worker: ${confirmDeleteWorker || ""}`}
        message={`Are you sure you want to delete worker '${confirmDeleteWorker}' and purge all associated compliance records from the database?`}
        confirmText="Delete Worker"
        cancelText="Cancel"
        variant="danger"
        isLoading={deletingWorkerId !== null}
        onConfirm={() => confirmDeleteWorker && handleDeleteWorker(confirmDeleteWorker)}
        onCancel={() => setConfirmDeleteWorker(null)}
      />

      <ConfirmModal
        isOpen={!!confirmDeleteSingleViolation}
        title={`Delete Violation Event: ${confirmDeleteSingleViolation || ""}`}
        message="Are you sure you want to permanently delete this violation proof record from the database?"
        confirmText="Delete Record"
        cancelText="Cancel"
        variant="danger"
        isLoading={deletingViolationId !== null}
        onConfirm={() => confirmDeleteSingleViolation && handleDeleteSingleViolation(confirmDeleteSingleViolation)}
        onCancel={() => setConfirmDeleteSingleViolation(null)}
      />

      <ConfirmModal
        isOpen={confirmPurgeSelected}
        title={`Delete ${selectedViolationIds.size} Selected Violations`}
        message={`Are you sure you want to purge ${selectedViolationIds.size} selected violation records for this worker? Compliance will be recalculated automatically.`}
        confirmText="Purge Selected"
        cancelText="Cancel"
        variant="danger"
        isLoading={purgingSelected}
        onConfirm={handlePurgeSelectedViolations}
        onCancel={() => setConfirmPurgeSelected(false)}
      />

      <ConfirmModal
        isOpen={!!confirmClearWorkerViolations}
        title={`Clear All Violations for ${selected?.name || confirmClearWorkerViolations || ""}`}
        message="Are you sure you want to clear all violation reports for this worker? Worker profile will be retained with 100% compliance."
        confirmText="Clear All Violations"
        cancelText="Cancel"
        variant="danger"
        isLoading={clearingWorkerViolations}
        onConfirm={() => confirmClearWorkerViolations && handleClearWorkerViolations(confirmClearWorkerViolations)}
        onCancel={() => setConfirmClearWorkerViolations(null)}
      />

      <ConfirmModal
        isOpen={confirmClearAll}
        title="Reset All Worker Compliance Entries"
        message="Are you sure you want to reset and clear all worker compliance records in the system?"
        confirmText="Reset All Data"
        cancelText="Cancel"
        variant="danger"
        isLoading={clearingAll}
        onConfirm={handleClearAllWorkers}
        onCancel={() => setConfirmClearAll(false)}
      />
    </AppShell>
  );
}
