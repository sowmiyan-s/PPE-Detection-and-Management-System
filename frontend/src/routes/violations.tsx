import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Check, ShieldAlert, Image as ImageIcon, Trash2, History as HistoryIcon, AlertTriangle, X, Eye, XCircle, CheckCircle2, Loader2 } from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { ppeLabel, formatTime, type ViolationEvent } from "@/lib/mock-data";
import { useSessionFetch, invalidateSessionCache } from "@/hooks/use-session-fetch";
import { useAppData } from "@/lib/data-context";
import { useToast } from "@/lib/toast-context";

export const Route = createFileRoute("/violations")({
  head: () => ({
    meta: [
      { title: "Manual Safety Violation Review & Triage — EdgeVision" },
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
          src={imgSrc}
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
  const { violations: ctxViolations, loading: ctxLoading, refetchViolations } = useAppData();
  const { showToast } = useToast();
  const [loadingActionId, setLoadingActionId] = useState<string | null>(null);
  const { data: fetchList, loading: fetchLoading, refetch: manualRefetch, mutate } = useSessionFetch<ExtendedViolationEvent[]>("/api/violations", []);

  const violationList: ExtendedViolationEvent[] = ctxViolations.length > 0 ? ctxViolations : fetchList;
  const loading = ctxLoading && fetchLoading && violationList.length === 0;

  const [triageTab, setTriageTab] = useState<"unacknowledged" | "accepted" | "declined" | "all">("unacknowledged");
  const [previewMedia, setPreviewMedia] = useState<{ src: string; imgSrc?: string; isVideo: boolean; title: string } | null>(null);

  const unacknowledgedList = violationList.filter((v) => !v.acknowledged && !v.declined && v.status !== "accepted" && v.status !== "declined");
  const acceptedList = violationList.filter((v) => v.acknowledged || v.status === "accepted" || v.status === "reviewed");
  const declinedList = violationList.filter((v) => v.declined || v.status === "declined");

  const displayedViolations =
    triageTab === "unacknowledged"
      ? unacknowledgedList
      : triageTab === "accepted"
        ? acceptedList
        : triageTab === "declined"
          ? declinedList
          : violationList;

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

  const handleClearAll = () => {
    if (confirm("Are you sure you want to delete all stored violation evidence records from MongoDB?")) {
      mutate([]);
      fetch("/api/violations", { method: "DELETE" })
        .then(() => {
          invalidateSessionCache("/api/violations");
          refetchViolations();
          manualRefetch(true);
        })
        .catch((err) => console.error("Clear all failed", err));
    }
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
          violationList.length > 0 && (
            <button
              key="clear-all"
              onClick={handleClearAll}
              className="flex items-center gap-1.5 rounded border border-destructive/30 bg-destructive/10 px-3 py-1.5 text-xs text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors font-medium cursor-pointer"
            >
              <Trash2 className="size-3.5" /> Purge Past Evidence
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
                  src={previewMedia.src}
                  poster={previewMedia.imgSrc}
                  controls
                  autoPlay
                  className="size-full object-contain"
                />
              ) : (
                <img src={previewMedia.src} alt="Evidence Large Snapshot" className="size-full object-contain" />
              )}
            </div>
          </div>
        </div>
      )}

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
            const imgSrc = v.imageBase64 || v.imagePath;

            return (
              <article
                key={v.id}
                className={`relative overflow-hidden rounded transition-all ${isConfirmedReal
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
                <div className="flex flex-col gap-4 pl-6 pr-4 py-4 lg:flex-row lg:items-center">
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
                      <span>ZONE: {v.zoneId}</span>
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
    </AppShell>
  );
}
