import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { Check, ShieldAlert, Image as ImageIcon, Trash2, Filter, History, AlertTriangle } from "lucide-react";

import { AppShell, PageHeader } from "@/components/app-shell";
import { PPE_LABELS, ppeLabel, formatTime, type ViolationEvent } from "@/lib/mock-data";

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

function Evidence({ imagePath, imageBase64, videoPath, missing }: { imagePath?: string; imageBase64?: string; videoPath?: string; missing: string[] }) {
  const imgSrc = imageBase64 || imagePath;

  if (videoPath) {
    return (
      <div className="relative aspect-video w-48 shrink-0 overflow-hidden rounded border border-destructive/50 bg-black shadow-inner">
        <video src={videoPath} controls className="size-full object-cover" />
        <span className="telemetry absolute top-1 left-1 rounded-sm bg-primary/90 px-1 py-0.5 text-[9px] text-primary-foreground font-mono font-bold tracking-wider">
          MP4 CLIP
        </span>
      </div>
    );
  }

  if (imgSrc) {
    return (
      <div className="relative aspect-video w-48 shrink-0 overflow-hidden rounded border border-destructive/50 bg-black shadow-inner">
        <img src={imgSrc} alt="Real Evidence Snapshot" className="size-full object-cover" />
        <span className="telemetry absolute bottom-1 left-1 rounded-sm bg-destructive/90 px-1 py-0.5 text-[9px] text-destructive-foreground font-mono font-bold tracking-wider">
          PROOF EVIDENCE
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
  const [violationList, setViolationList] = useState<ExtendedViolationEvent[]>([]);
  const [acked, setAcked] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);

  const fetchViolations = () => {
    fetch("/api/violations")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setViolationList(data);
        }
      })
      .catch((err) => console.error("Failed to fetch violations", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchViolations();
  }, []);

  const openViolations = violationList.filter((v) => !v.acknowledged && !acked.includes(v.id));
  const displayedViolations = showHistory ? violationList : openViolations;

  const handleAcknowledge = (id: string) => {
    setAcked((prev) => [...prev, id]);
    fetch(`/api/violations/${id}/acknowledge`, { method: "POST" })
      .then(() => fetchViolations())
      .catch((err) => console.error("Ack failed", err));
  };

  const handleDelete = (id: string) => {
    setViolationList((prev) => prev.filter((v) => v.id !== id));
    fetch(`/api/violations/${id}`, { method: "DELETE" })
      .then(() => fetchViolations())
      .catch((err) => console.error("Delete failed", err));
  };

  const handleClearAll = () => {
    if (confirm("Are you sure you want to delete all stored violation evidence records from MongoDB?")) {
      setViolationList([]);
      fetch("/api/violations", { method: "DELETE" })
        .then(() => fetchViolations())
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
              <History className="size-3.5" /> All History Log ({violationList.length})
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
            return (
              <article
                key={v.id}
                className={`relative overflow-hidden rounded ${isAcked ? "panel-surface opacity-75" : "alert-surface"}`}
              >
                <div className="hazard-stripe absolute inset-y-0 left-0 w-1.5" />
                <div className="flex flex-col gap-4 pl-6 pr-4 py-4 lg:flex-row lg:items-center">
                  <Evidence imagePath={v.imagePath} imageBase64={v.imageBase64} videoPath={v.videoPath} missing={v.missing} />

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <ShieldAlert className="size-4 text-destructive" />
                      <h2 className="display-title text-base">{v.type}</h2>
                      <span className="telemetry rounded-sm bg-background/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        {v.id}
                      </span>
                      {isAcked && (
                        <span className="rounded bg-success/20 px-2 py-0.5 text-[10px] text-success font-semibold border border-success/30">
                          Reviewed
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
                        className="flex-1 display-title inline-flex items-center justify-center gap-1 rounded bg-primary px-3 py-1.5 text-[11px] text-primary-foreground disabled:opacity-50"
                      >
                        <Check className="size-3.5" /> {isAcked ? "Ack'd" : "Acknowledge"}
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

