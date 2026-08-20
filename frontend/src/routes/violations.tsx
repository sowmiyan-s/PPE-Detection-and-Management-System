import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { Check, ShieldAlert, Image as ImageIcon, Trash2, History as HistoryIcon, AlertTriangle, X, Eye, XCircle, CheckCircle2, Loader2, Filter, Search, RotateCcw } from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { ConfirmModal } from "@/components/confirm-modal";
import { ppeLabel, formatTime, zoneLabel, getEvidenceUrl, type ViolationEvent } from "@/lib/mock-data";
import { useSessionFetch, invalidateSessionCache } from "@/hooks/use-session-fetch";
import { useAppData } from "@/lib/data-context";
import { useToast } from "@/lib/toast-context";

export const Route = createFileRoute("/violations")({
  head: () => ({
    meta: [
      { title: "Manual Safety Violation Review & Triage — Cerberus AI" },
      {
        name: "description",
        content:
          "Manually verify, confirm real violations, or decline false alerts. Only confirmed violations feed executive safety analytics.",
      },
    ],
  }),
  component: ViolationsPage,
});

type ExtendedViolationEvent = ViolationEvent & {
  imageBase64?: string;
  videoPath?: string;
  status?: string;
  declined?: boolean;
};

function Evidence({
  imagePath,
  imageBase64,
  videoPath,
  missing,
  onOpenPreview,
}: {
  imagePath?: string | undefined;
  imageBase64?: string | undefined;
  videoPath?: string | undefined;
  missing: string[];
  onOpenPreview: () => void;
}) {
  const [videoError, setVideoError] = useState(false);
  const imgSrc = imageBase64 || imagePath;

  if (imgSrc) {
    return (
      <div
        onClick={onOpenPreview}
        className="relative aspect-video w-48 shrink-0 overflow-hidden rounded border border-destructive/50 bg-black shadow-inner cursor-pointer group"
      >
        <img
          src={getEvidenceUrl(imgSrc)}
          alt="Proof Evidence Snapshot"
          onError={(e) => {
            if (imagePath && e.currentTarget.src !== imagePath) {
              e.currentTarget.src = imagePath;
            } else if (imageBase64 && e.currentTarget.src !== imageBase64) {
              e.currentTarget.src = imageBase64;
            }
          }}
          className="size-full object-cover transition-transform group-hover:scale-105"
        />
        {videoPath && !videoError && (
          <video
            src={videoPath}
            poster={imgSrc}
            preload="metadata"
            onError={() => setVideoError(true)}
            className="size-full object-cover absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity"
          />
        )}
        <span className="telemetry absolute bottom-1 left-1 rounded-sm bg-destructive/90 px-1 py-0.5 text-[9px] text-destructive-foreground font-mono font-bold tracking-wider">
          {videoPath && !videoError ? "PROOF + CLIP" : "PROOF EVIDENCE"}
        </span>
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white">
          <Eye className="size-5" />
        </div>
      </div>
    );
  }

  if (videoPath && !videoError) {
    return (
      <div
        onClick={onOpenPreview}
        className="relative aspect-video w-48 shrink-0 overflow-hidden rounded border border-destructive/50 bg-black shadow-inner cursor-pointer group"
      >
        <video
          src={videoPath}
          controls
          preload="metadata"
          onError={() => setVideoError(true)}
          className="size-full object-cover"
        />
        <span className="telemetry absolute top-1 left-1 rounded-sm bg-primary/90 px-1 py-0.5 text-[9px] text-primary-foreground font-mono font-bold tracking-wider">
          MP4 CLIP
        </span>
      </div>
    );
  }

  return (
    <div className="relative aspect-video w-40 shrink-0 overflow-hidden rounded border border-destructive/50 bg-black flex flex-col items-center justify-center text-muted-foreground p-2">
      <ImageIcon className="size-6 text-destructive/80 mb-1" />
      <span className="telemetry text-[10px] text-destructive font-mono">
        -{missing.length} PPE MISSING
      </span>
    </div>
  );
}

function ViolationsPage() {
  const { violations: ctxViolations, zones: ctxZones, loading: ctxLoading, refetchViolations } = useAppData();
  const { showToast } = useToast();
  const [loadingActionId, setLoadingActionId] = useState<string | null>(null);
  const { data: fetchList, loading: fetchLoading, refetch: manualRefetch, mutate } = useSessionFetch<ExtendedViolationEvent[]>("/api/violations", []);
  const { data: zoneData } = useSessionFetch<any>("/api/zones", { db_zones: [] });

  const violationList: ExtendedViolationEvent[] = ctxViolations.length > 0 ? ctxViolations : fetchList;
  const availableZones = ctxZones.length > 0 ? ctxZones : (zoneData?.db_zones || []);
  const loading = ctxLoading && fetchLoading && violationList.length === 0;

  const [triageTab, setTriageTab] = useState<"unacknowledged" | "accepted" | "declined" | "all">("unacknowledged");
  const [previewMedia, setPreviewMedia] = useState<{ src: string; imgSrc?: string; isVideo: boolean; title: string } | null>(null);

  const [filterZone, setFilterZone] = useState<string>("all");
  const [filterPpe, setFilterPpe] = useState<string>("all");
  const [filterScore, setFilterScore] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showConfirmBulkDelete, setShowConfirmBulkDelete] = useState(false);
  const [bulkDeleteTargetIds, setBulkDeleteTargetIds] = useState<string[]>([]);
  const [bulkDeleteTitle, setBulkDeleteTitle] = useState("");
  const [bulkDeleteMessage, setBulkDeleteMessage] = useState("");
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  const availablePpeTypes = useMemo(() => {
    const set = new Set<string>();
    violationList.forEach((v) => {
      if (Array.isArray(v.missing)) {
        v.missing.forEach((m) => {
          if (m) set.add(m.trim());
        });
      }
    });
    return Array.from(set);
  }, [violationList]);

  const unacknowledgedList = violationList.filter((v) => !v.acknowledged && !v.declined && v.status !== "accepted" && v.status !== "declined");
  const acceptedList = violationList.filter((v) => v.acknowledged || v.status === "accepted" || v.status === "reviewed");
  const declinedList = violationList.filter((v) => v.declined || v.status === "declined");

  const baseViolations =
    triageTab === "unacknowledged"
      ? unacknowledgedList
      : triageTab === "accepted"
        ? acceptedList
        : triageTab === "declined"
          ? declinedList
          : violationList;

  // Filter by Zone, PPE, Confidence Score, and Worker ID
  const displayedViolations = baseViolations.filter((v) => {
    if (filterZone !== "all" && v.zoneId !== filterZone && (v as any).zone_id !== filterZone) {
      return false;
    }
    if (filterPpe !== "all") {
      const missingList = (v.missing || []).map((m) => m.toLowerCase());
      if (!missingList.includes(filterPpe.toLowerCase())) return false;
    }
    if (filterScore !== "all") {
      const conf = v.confidence || 0.0;
      if (filterScore === "0.9" && conf < 0.9) return false;
      if (filterScore === "0.8" && conf < 0.8) return false;
      if (filterScore === "0.7" && conf < 0.7) return false;
      if (filterScore === "<0.7" && conf >= 0.7) return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchWorker = (v.workerId || "").toLowerCase().includes(q);
      const matchId = (v.id || "").toLowerCase().includes(q);
      const matchType = (v.type || "").toLowerCase().includes(q);
      if (!matchWorker && !matchId && !matchType) return false;
    }
    return true;
  });

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllDisplayed = () => {
    const displayedIdList = displayedViolations.map((v) => v.id);
    const allSelected = displayedIdList.every((id) => selectedIds.has(id));
    if (allSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        displayedIdList.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        displayedIdList.forEach((id) => next.add(id));
        return next;
      });
    }
  };

  const promptDeleteSelected = () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setBulkDeleteTargetIds(ids);
    setBulkDeleteTitle(`Delete ${ids.length} Selected Violation Events`);
    setBulkDeleteMessage(`Are you sure you want to permanently delete the ${ids.length} selected violation evidence records from the database?`);
    setShowConfirmBulkDelete(true);
  };

  const promptDeleteFiltered = () => {
    const ids = displayedViolations.map((v) => v.id);
    if (ids.length === 0) return;
    setBulkDeleteTargetIds(ids);
    setBulkDeleteTitle(`Delete All ${ids.length} Filtered Violation Events`);
    setBulkDeleteMessage(`Are you sure you want to permanently delete all ${ids.length} currently filtered violation records from the database?`);
    setShowConfirmBulkDelete(true);
  };

  const executeBulkDelete = () => {
    if (bulkDeleteTargetIds.length === 0) return;
    setIsBulkDeleting(true);
    const targetSet = new Set(bulkDeleteTargetIds);
    mutate(violationList.filter((v) => !targetSet.has(v.id)));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      bulkDeleteTargetIds.forEach((id) => next.delete(id));
      return next;
    });

    fetch("/api/violations/purge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: bulkDeleteTargetIds }),
    })
      .then(() => {
        invalidateSessionCache("/api/violations");
        refetchViolations();
        manualRefetch(true);
        showToast(`Successfully purged ${bulkDeleteTargetIds.length} filtered violation record(s)`);
      })
      .catch((err) => {
        console.error("Bulk purge failed", err);
        showToast("Failed to purge selected violation records");
      })
      .finally(() => {
        setIsBulkDeleting(false);
        setShowConfirmBulkDelete(false);
        setBulkDeleteTargetIds([]);
      });
  };

  const handleUpdateStatus = (id: string, newStatus: "accepted" | "declined") => {
    setLoadingActionId(id);
    mutate(
      violationList.map((v) =>
        v.id === id
          ? {
            ...v,
            status: newStatus,
            acknowledged: newStatus === "accepted",
            declined: newStatus === "declined",
          }
          : v
      )
    );

    fetch(`/api/violations/${id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    })
      .then(() => {
        invalidateSessionCache("/api/violations");
        refetchViolations();
        manualRefetch(true);
        showToast(newStatus === "accepted" ? "Violation confirmed successfully" : "Alert declined successfully");
      })
      .catch((err) => {
        console.error("Status update failed", err);
        showToast("Failed to update violation status");
      })
      .finally(() => setLoadingActionId(null));
  };

  const handleDelete = (id: string) => {
    setLoadingActionId(id);
    mutate(violationList.filter((v) => v.id !== id));
    fetch(`/api/violations/${id}`, { method: "DELETE" })
      .then(() => {
        invalidateSessionCache("/api/violations");
        refetchViolations();
        manualRefetch(true);
        showToast("Violation event deleted successfully");
      })
      .catch((err) => {
        console.error("Delete failed", err);
        showToast("Failed to delete violation event");
      })
      .finally(() => setLoadingActionId(null));
  };

  const [showConfirmClearAll, setShowConfirmClearAll] = useState(false);
  const [isClearingAll, setIsClearingAll] = useState(false);

  const executeClearAll = () => {
    setIsClearingAll(true);
    mutate([]);
    fetch("/api/violations", { method: "DELETE" })
      .then(() => {
        invalidateSessionCache("/api/violations");
        refetchViolations();
        manualRefetch(true);
        showToast("All violation records cleared from database");
      })
      .catch((err) => {
        console.error("Clear all failed", err);
        showToast("Failed to clear violation records");
      })
      .finally(() => {
        setIsClearingAll(false);
        setShowConfirmClearAll(false);
      });
  };


  return (
    <AppShell>
      <PageHeader
        title="Manual Violation Verification & Triage"
        subtitle="Manually confirm real safety breaches or decline false alerts. Only operator-confirmed violations are used for executive safety analytics."
        actions={[
          <div key="triage-tabs" className="flex items-center gap-1 rounded border border-border bg-panel p-1">
            <button
              onClick={() => setTriageTab("unacknowledged")}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${triageTab === "unacknowledged"
                ? "bg-warning text-warning-foreground font-semibold"
                : "text-muted-foreground hover:text-foreground"
                }`}
            >
              <AlertTriangle className="size-3.5" /> Pending Review ({unacknowledgedList.length})
            </button>
            <button
              onClick={() => setTriageTab("accepted")}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${triageTab === "accepted"
                ? "bg-success text-success-foreground font-semibold"
                : "text-muted-foreground hover:text-foreground"
                }`}
            >
              <CheckCircle2 className="size-3.5" /> Confirmed Real ({acceptedList.length})
            </button>
            <button
              onClick={() => setTriageTab("declined")}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${triageTab === "declined"
                ? "bg-destructive/80 text-destructive-foreground font-semibold"
                : "text-muted-foreground hover:text-foreground"
                }`}
            >
              <XCircle className="size-3.5" /> False Alerts ({declinedList.length})
            </button>
            <button
              onClick={() => setTriageTab("all")}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${triageTab === "all"
                ? "bg-primary text-primary-foreground font-semibold"
                : "text-muted-foreground hover:text-foreground"
                }`}
            >
              <HistoryIcon className="size-3.5" /> All Audit Log ({violationList.length})
            </button>
          </div>,
          selectedIds.size > 0 && (
            <button
              key="delete-selected"
              onClick={promptDeleteSelected}
              className="flex items-center gap-1.5 rounded border border-destructive bg-destructive px-3 py-1.5 text-xs text-destructive-foreground hover:bg-destructive/90 transition-colors font-semibold cursor-pointer shadow"
            >
              <Trash2 className="size-3.5" /> Delete Selected ({selectedIds.size})
            </button>
          ),
          displayedViolations.length > 0 && (
            <button
              key="delete-filtered"
              onClick={promptDeleteFiltered}
              className="flex items-center gap-1.5 rounded border border-destructive/40 bg-destructive/15 px-3 py-1.5 text-xs text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors font-medium cursor-pointer"
            >
              <Filter className="size-3.5" /> Delete Filtered ({displayedViolations.length})
            </button>
          ),
          violationList.length > 0 && (
            <button
              key="clear-all"
              onClick={() => setShowConfirmClearAll(true)}
              className="flex items-center gap-1.5 rounded border border-border bg-accent/40 px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors font-medium cursor-pointer"
            >
              <Trash2 className="size-3.5" /> Purge All ({violationList.length})
            </button>
          ),
        ]}

      />

      {/* Media Evidence Lightbox Modal */}
      {previewMedia && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="relative max-w-4xl w-full bg-panel rounded-lg border border-border overflow-hidden shadow-2xl p-4">
            <div className="flex items-center justify-between border-b border-border pb-3 mb-3">
              <h3 className="font-semibold text-sm display-title text-foreground">{previewMedia.title}</h3>
              <button
                onClick={() => setPreviewMedia(null)}
                className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
              >
                <X className="size-5" />
              </button>
            </div>
            <div className="relative aspect-video bg-black flex items-center justify-center rounded overflow-hidden">
              {previewMedia.isVideo && previewMedia.src ? (
                <video
                  src={getEvidenceUrl(previewMedia.src)}
                  poster={getEvidenceUrl(previewMedia.imgSrc)}
                  controls
                  autoPlay
                  className="size-full object-contain"
                />
              ) : (
                <img src={getEvidenceUrl(previewMedia.src)} alt="Evidence Large Snapshot" className="size-full object-contain" />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Multi-Parameter Filter Controls Bar */}
      <div className="mb-4 rounded panel-surface p-3 border border-border shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5 flex-1 min-w-[280px]">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[180px]">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search Worker ID / Event..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="telemetry w-full rounded border border-input bg-background/60 pl-8 pr-3 py-1.5 text-xs outline-none focus:border-primary"
              />
            </div>

            {/* Filter by Zone */}
            <div className="flex items-center gap-1.5">
              <span className="telemetry text-[11px] text-muted-foreground whitespace-nowrap">Zone:</span>
              <select
                value={filterZone}
                onChange={(e) => setFilterZone(e.target.value)}
                className="telemetry rounded border border-input bg-background/60 px-2.5 py-1.5 text-xs outline-none focus:border-primary cursor-pointer"
              >
                <option value="all">All Zones</option>
                {availableZones.map((z: any) => (
                  <option key={z.id} value={z.id}>
                    {z.name || z.id}
                  </option>
                ))}
              </select>
            </div>

            {/* Filter by PPE */}
            <div className="flex items-center gap-1.5">
              <span className="telemetry text-[11px] text-muted-foreground whitespace-nowrap">PPE:</span>
              <select
                value={filterPpe}
                onChange={(e) => setFilterPpe(e.target.value)}
                className="telemetry rounded border border-input bg-background/60 px-2.5 py-1.5 text-xs outline-none focus:border-primary cursor-pointer"
              >
                <option value="all">All Missing PPE ({availablePpeTypes.length})</option>
                {availablePpeTypes.map((ppeKey: string) => (
                  <option key={ppeKey} value={ppeKey}>
                    {ppeLabel(ppeKey)}
                  </option>
                ))}
              </select>
            </div>

            {/* Filter by Score / Confidence */}
            <div className="flex items-center gap-1.5">
              <span className="telemetry text-[11px] text-muted-foreground whitespace-nowrap">Score:</span>
              <select
                value={filterScore}
                onChange={(e) => setFilterScore(e.target.value)}
                className="telemetry rounded border border-input bg-background/60 px-2.5 py-1.5 text-xs outline-none focus:border-primary cursor-pointer"
              >
                <option value="all">All Confidence Scores</option>
                <option value="0.9">High Confidence (≥ 90%)</option>
                <option value="0.8">Good Confidence (≥ 80%)</option>
                <option value="0.7">Moderate Confidence (≥ 70%)</option>
                <option value="<0.7">Low Confidence (&lt; 70%)</option>
              </select>
            </div>
          </div>

          {/* Active Filter Info & Reset Button */}
          <div className="flex flex-wrap items-center gap-2">
            {displayedViolations.length > 0 && (
              <label className="telemetry inline-flex items-center gap-1.5 rounded border border-border bg-accent/20 px-2 py-1 text-xs text-foreground cursor-pointer hover:bg-accent/40 transition-colors">
                <input
                  type="checkbox"
                  checked={displayedViolations.length > 0 && displayedViolations.every((v) => selectedIds.has(v.id))}
                  onChange={toggleSelectAllDisplayed}
                  className="rounded border-input text-primary focus:ring-primary size-3.5 cursor-pointer"
                />
                <span>Select All ({displayedViolations.length})</span>
              </label>
            )}
            <span className="telemetry text-xs text-muted-foreground font-mono">
              Showing <span className="text-foreground font-bold">{displayedViolations.length}</span> of {baseViolations.length}
            </span>
            {(filterZone !== "all" || filterPpe !== "all" || filterScore !== "all" || searchQuery.trim()) && (
              <button
                onClick={() => {
                  setFilterZone("all");
                  setFilterPpe("all");
                  setFilterScore("all");
                  setSearchQuery("");
                }}
                className="telemetry inline-flex items-center gap-1 rounded border border-border bg-accent/30 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <RotateCcw className="size-3" /> Reset Filters
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {loading ? (
          <div className="rounded border border-border panel-surface p-12 text-center text-muted-foreground">
            <div className="animate-pulse text-sm">Loading safety violation records...</div>
          </div>
        ) : displayedViolations.length === 0 ? (
          <div className="rounded border border-border panel-surface p-12 text-center text-muted-foreground">
            <ShieldAlert className="size-10 text-success mx-auto mb-2 opacity-80" />
            <h3 className="display-title text-base text-foreground">
              {triageTab === "unacknowledged"
                ? "No Pending Violations to Triage"
                : triageTab === "accepted"
                  ? "No Confirmed Real Violations Recorded"
                  : triageTab === "declined"
                    ? "No False Alerts Flagged"
                    : "No Violation Evidence Recorded"}
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              {triageTab === "unacknowledged"
                ? "All AI-detected safety events have been reviewed by operators."
                : "All events are up to date."}
            </p>
          </div>
        ) : (
          displayedViolations.map((v) => {
            const isConfirmedReal = v.acknowledged || v.status === "accepted" || v.status === "reviewed";
            const isDeclinedFalse = v.declined || v.status === "declined";
            const isSelected = selectedIds.has(v.id);
            const imgSrc = v.imageBase64 || v.imagePath;

            return (
              <article
                key={v.id}
                className={`relative overflow-hidden rounded transition-all ${isSelected
                  ? "ring-2 ring-primary border border-primary/50"
                  : isConfirmedReal
                  ? "panel-surface border border-success/40"
                  : isDeclinedFalse
                    ? "panel-surface opacity-75 border border-muted"
                    : "alert-surface border border-destructive/50"
                  }`}
              >
                <div
                  className={`absolute inset-y-0 left-0 w-1.5 ${isConfirmedReal ? "bg-success" : isDeclinedFalse ? "bg-muted-foreground/40" : "bg-destructive"
                    }`}
                />
                <div className="flex flex-col gap-4 pl-4 pr-4 py-4 lg:flex-row lg:items-center">
                  <div className="flex items-center gap-2.5 shrink-0">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(v.id)}
                      className="rounded border-input text-primary focus:ring-primary size-4 cursor-pointer"
                      title="Select for bulk deletion"
                    />
                    <Evidence
                      imagePath={v.imagePath}
                      imageBase64={v.imageBase64}
                      videoPath={v.videoPath}
                      missing={v.missing}
                      onOpenPreview={() => {
                        setPreviewMedia({
                          src: imgSrc || v.videoPath || "",
                          imgSrc: imgSrc || "",
                          isVideo: !imgSrc && Boolean(v.videoPath),
                          title: `Proof Evidence Review — ${v.id}`,
                        });
                      }}
                    />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <ShieldAlert className={`size-4 ${isConfirmedReal ? "text-success" : isDeclinedFalse ? "text-muted-foreground" : "text-destructive"}`} />
                      <h2 className="display-title text-base">{v.type}</h2>
                      <span className="telemetry rounded-sm bg-background/60 px-1.5 py-0.5 text-[10px] text-muted-foreground font-mono">
                        {v.id}
                      </span>

                      {/* Status Badges */}
                      {isConfirmedReal ? (
                        <span className="rounded bg-success/20 px-2 py-0.5 text-[10px] text-success font-semibold border border-success/30 flex items-center gap-1">
                          <CheckCircle2 className="size-3" /> Confirmed Real Violation
                        </span>
                      ) : isDeclinedFalse ? (
                        <span className="rounded bg-muted/60 px-2 py-0.5 text-[10px] text-muted-foreground font-medium border border-border flex items-center gap-1">
                          <XCircle className="size-3" /> Declined (False Alert)
                        </span>
                      ) : (
                        <span className="rounded bg-warning/20 px-2 py-0.5 text-[10px] text-warning font-semibold border border-warning/30 flex items-center gap-1">
                          <AlertTriangle className="size-3" /> Pending Review
                        </span>
                      )}
                    </div>

                    <div className="telemetry mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
                      <span>WORKER: {v.workerId}</span>
                      <span>ZONE: {zoneLabel(v.zoneId, availableZones)}</span>
                      <span>CAMERA: {v.cameraId}</span>
                      <span>TIMESTAMP: {formatTime(v.timestamp)}</span>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {v.detected?.map((d) => (
                        <span
                          key={d}
                          className="rounded-sm border border-success/40 bg-success/10 px-2 py-0.5 text-[11px] text-success"
                        >
                          {ppeLabel(d)}
                        </span>
                      ))}
                      {v.missing?.map((m) => (
                        <span
                          key={m}
                          className="rounded-sm border border-destructive/50 bg-destructive/15 px-2 py-0.5 text-[11px] text-destructive font-medium"
                        >
                          Missing: {ppeLabel(m)}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Manual Triage Action Controls */}
                  <div className="flex shrink-0 flex-col items-stretch gap-2 lg:w-48">
                    <div className="rounded border border-border bg-background/40 px-3 py-1.5 text-center">
                      <div className="display-title text-[10px] text-muted-foreground">AI Confidence</div>
                      <div className="telemetry text-lg text-foreground font-mono font-bold">
                        {(v.confidence * 100).toFixed(0)}%
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-1.5">
                      {/* Confirm Real Violation Button */}
                      <button
                        onClick={() => handleUpdateStatus(v.id, "accepted")}
                        disabled={loadingActionId === v.id}
                        className={`display-title inline-flex items-center justify-center gap-1 rounded px-2.5 py-1.5 text-[10px] font-semibold transition-colors cursor-pointer disabled:opacity-50 ${isConfirmedReal
                          ? "bg-success text-success-foreground shadow"
                          : "bg-success/20 text-success hover:bg-success hover:text-success-foreground border border-success/40"
                          }`}
                        title="Confirm as a real safety breach for official reports"
                      >
                        {loadingActionId === v.id ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                        {isConfirmedReal ? "Confirmed" : "Confirm Real"}
                      </button>

                      {/* Decline False Alert Button */}
                      <button
                        onClick={() => handleUpdateStatus(v.id, "declined")}
                        disabled={loadingActionId === v.id}
                        className={`display-title inline-flex items-center justify-center gap-1 rounded px-2.5 py-1.5 text-[10px] font-semibold transition-colors cursor-pointer disabled:opacity-50 ${isDeclinedFalse
                          ? "bg-muted text-foreground border border-border"
                          : "bg-warning/20 text-warning hover:bg-warning hover:text-warning-foreground border border-warning/40"
                          }`}
                        title="Decline as false alert — exclude from real violation statistics"
                      >
                        {loadingActionId === v.id ? <Loader2 className="size-3 animate-spin" /> : <XCircle className="size-3" />}
                        {isDeclinedFalse ? "Declined" : "Decline Alert"}
                      </button>
                    </div>

                    {/* Delete Button */}
                    <button
                      onClick={() => handleDelete(v.id)}
                      disabled={loadingActionId === v.id}
                      title="Delete Evidence Record completely from database"
                      className="w-full flex items-center justify-center gap-1 rounded border border-destructive/30 bg-destructive/10 px-2 py-1 text-[10px] text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors font-medium cursor-pointer disabled:opacity-50"
                    >
                      {loadingActionId === v.id ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                      Delete Evidence
                    </button>
                  </div>
                </div>
              </article>
            );
          })
        )}
      </div>

      {/* Confirm Modal for Bulk Filtered Deletion */}
      <ConfirmModal
        isOpen={showConfirmBulkDelete}
        title={bulkDeleteTitle}
        message={bulkDeleteMessage}
        confirmText={`Delete ${bulkDeleteTargetIds.length} Event(s)`}
        cancelText="Cancel"
        variant="danger"
        isLoading={isBulkDeleting}
        onConfirm={executeBulkDelete}
        onCancel={() => {
          setShowConfirmBulkDelete(false);
          setBulkDeleteTargetIds([]);
        }}
      />

      {/* Themed Confirm Modal for Purging All Records */}
      <ConfirmModal
        isOpen={showConfirmClearAll}
        title="Purge All Stored Violation Evidence"
        message="Are you sure you want to permanently delete all stored violation evidence records from database? This action cannot be undone."
        confirmText="Purge All Records"
        cancelText="Cancel"
        variant="danger"
        isLoading={isClearingAll}
        onConfirm={executeClearAll}
        onCancel={() => setShowConfirmClearAll(false)}
      />
    </AppShell>
  );
}

