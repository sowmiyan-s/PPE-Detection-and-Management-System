import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { Check, ShieldAlert, Image as ImageIcon, Trash2, Filter, History as HistoryIcon, AlertTriangle, X, Eye } from "lucide-react";
import { AppShell, PageHeader } from "@/components/app-shell";
import { PPE_LABELS, ppeLabel, formatTime, type ViolationEvent } from "@/lib/mock-data";
import { useSessionFetch, invalidateSessionCache } from "@/hooks/use-session-fetch";
import { useAppData } from "@/lib/data-context";

export const Route = createFileRoute("/violations")({
  head: () => ({
    meta: [
      { title: "Active Violations — EdgeVision Safety Alerts" },
      {
        name: "description",
        content:
          "Unacknowledged PPE and work-at-height violations with worker tracking ID, zone, confidence, evidence frame and clip review actions.",
      },
    ],
  }),
  component: ViolationsPage,
});

type ExtendedViolationEvent = ViolationEvent & {
  imageBase64?: string;
  videoPath?: string;
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
  onOpenPreview?: () => void;
}) {
  const imgSrc = imageBase64 || imagePath;

  if (videoPath) {
    return (
      <div
        onClick={onOpenPreview}
        className="relative aspect-video w-48 shrink-0 overflow-hidden rounded border border-destructive/50 bg-black shadow-inner cursor-pointer group"
      >
        <video src={videoPath} controls className="size-full object-cover" />
        <span className="telemetry absolute top-1 left-1 rounded-sm bg-primary/90 px-1 py-0.5 text-[9px] text-primary-foreground font-mono font-bold tracking-wider">
          MP4 CLIP
        </span>
      </div>
    );
  }

  if (imgSrc) {
    return (
      <div
        onClick={onOpenPreview}
        className="relative aspect-video w-48 shrink-0 overflow-hidden rounded border border-destructive/50 bg-black shadow-inner cursor-pointer group"
      >
        <img src={imgSrc} alt="Real Evidence Snapshot" className="size-full object-cover transition-transform group-hover:scale-105" />
        <span className="telemetry absolute bottom-1 left-1 rounded-sm bg-destructive/90 px-1 py-0.5 text-[9px] text-destructive-foreground font-mono font-bold tracking-wider">
          PROOF EVIDENCE
        </span>
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white">
          <Eye className="size-5" />
        </div>
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
  const { data: fetchList, loading: fetchLoading, refetch: manualRefetch, mutate } = useSessionFetch<ExtendedViolationEvent[]>("/api/violations", []);

  const violationList: ExtendedViolationEvent[] = ctxViolations.length > 0 ? ctxViolations : fetchList;
  const loading = ctxLoading && fetchLoading && violationList.length === 0;

  const [acked, setAcked] = useState<string[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [previewMedia, setPreviewMedia] = useState<{ src: string; isVideo: boolean; title: string } | null>(null);

  const openViolations = violationList.filter((v) => !v.acknowledged && !acked.includes(v.id));
  const displayedViolations = showHistory ? violationList : openViolations;

  const handleAcknowledge = (id: string) => {
    setAcked((prev) => [...prev, id]);
    fetch(`/api/violations/${id}/acknowledge`, { method: "POST" })
      .then(() => {
        invalidateSessionCache("/api/violations");
        refetchViolations();
        manualRefetch(true);
      })
      .catch((err) => console.error("Ack failed", err));
  };

  const handleDelete = (id: string) => {
    mutate(violationList.filter((v) => v.id !== id));
    fetch(`/api/violations/${id}`, { method: "DELETE" })
      .then(() => {
        invalidateSessionCache("/api/violations");
        refetchViolations();
        manualRefetch(true);
      })
      .catch((err) => console.error("Delete failed", err));
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
        title="Active Violations & Incident Management"
        subtitle="Events confirmed by the rule engine and temporal validator, stored with timestamped image evidence in MongoDB."
        actions={[
          <div key="filter" className="flex items-center gap-1 rounded border border-border bg-panel p-1">
            <button
              onClick={() => setShowHistory(false)}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                !showHistory ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <AlertTriangle className="size-3.5" /> Unacknowledged ({openViolations.length})
            </button>
            <button
              onClick={() => setShowHistory(true)}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                showHistory ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <HistoryIcon className="size-3.5" /> All History Log ({violationList.length})
            </button>
          </div>,
          violationList.length > 0 && (
            <button
              key="clear-all"
              onClick={handleClearAll}
              className="flex items-center gap-1.5 rounded border border-destructive/30 bg-destructive/10 px-3 py-1.5 text-xs text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors font-medium"
            >
              <Trash2 className="size-3.5" /> Purge Past Evidence
            </button>
          ),
        ]}
      />

      {/* Media Evidence Modal */}
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
              {previewMedia.isVideo ? (
                <video src={previewMedia.src} controls autoPlay className="size-full object-contain" />
              ) : (
                <img src={previewMedia.src} alt="Evidence Large" className="size-full object-contain" />
              )}
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {loading ? (
          <div className="rounded border border-border panel-surface p-12 text-center text-muted-foreground">
            <div className="animate-pulse text-sm">Loading violation events from database...</div>
          </div>
        ) : displayedViolations.length === 0 ? (
          <div className="rounded border border-border panel-surface p-12 text-center text-muted-foreground">
            <ShieldAlert className="size-10 text-success mx-auto mb-2 opacity-80" />
            <h3 className="display-title text-base text-foreground">
              {showHistory ? "No Violation Evidence Recorded" : "No Unacknowledged Violations"}
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              {showHistory
                ? "Your safety pipeline has not detected any non-compliant events yet."
                : "All detected safety events have been reviewed and acknowledged."}
            </p>
          </div>
        ) : (
          displayedViolations.map((v) => {
            const isAcked = v.acknowledged || acked.includes(v.id);
            const imgSrc = v.imageBase64 || v.imagePath;

            return (
              <article
                key={v.id}
                className={`relative overflow-hidden rounded ${isAcked ? "panel-surface opacity-75" : "alert-surface"}`}
              >
                <div className="hazard-stripe absolute inset-y-0 left-0 w-1.5" />
                <div className="flex flex-col gap-4 pl-6 pr-4 py-4 lg:flex-row lg:items-center">
                  <Evidence
                    imagePath={v.imagePath}
                    imageBase64={v.imageBase64}
                    videoPath={v.videoPath}
                    missing={v.missing}
                    onOpenPreview={() => {
                      if (v.videoPath) {
                        setPreviewMedia({ src: v.videoPath, isVideo: true, title: `Evidence Video — ${v.id}` });
                      } else if (imgSrc) {
                        setPreviewMedia({ src: imgSrc, isVideo: false, title: `Evidence Snapshot — ${v.id}` });
                      }
                    }}
                  />

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <ShieldAlert className="size-4 text-destructive" />
                      <h2 className="display-title text-base">{v.type}</h2>
                      <span className="telemetry rounded-sm bg-background/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        {v.id}
                      </span>
                      {isAcked && (
                        <span className="rounded bg-success/20 px-2 py-0.5 text-[10px] text-success font-semibold border border-success/30">
                          Reviewed / Accepted
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

                  <div className="flex shrink-0 flex-col items-stretch gap-2 lg:w-44">
                    <div className="rounded border border-border bg-background/40 px-3 py-1.5 text-center">
                      <div className="display-title text-[10px] text-muted-foreground">Confidence</div>
                      <div className="telemetry text-lg text-destructive font-mono font-bold">
                        {(v.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        disabled={isAcked}
                        onClick={() => handleAcknowledge(v.id)}
                        className="flex-1 display-title inline-flex items-center justify-center gap-1 rounded bg-primary px-3 py-1.5 text-[11px] text-primary-foreground disabled:opacity-50 hover:bg-primary/90 transition-colors"
                      >
                        <Check className="size-3.5" /> {isAcked ? "Accepted" : "Accept & Ack"}
                      </button>
                      <button
                        onClick={() => handleDelete(v.id)}
                        title="Delete Evidence Record"
                        className="rounded border border-destructive/30 bg-destructive/10 p-1.5 text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
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


