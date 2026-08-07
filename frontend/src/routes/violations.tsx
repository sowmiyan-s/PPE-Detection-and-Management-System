import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { Check, ShieldAlert, Image as ImageIcon } from "lucide-react";

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

function Evidence({ imagePath, missing }: { imagePath: string | undefined; missing: string[] }) {
  if (imagePath) {
    return (
      <div className="relative aspect-video w-44 shrink-0 overflow-hidden rounded border border-destructive/50 bg-black">
        <img src={imagePath} alt="Real Evidence Snapshot" className="size-full object-cover" />
        <span className="telemetry absolute bottom-1 left-1 rounded-sm bg-destructive/90 px-1 text-[9px] text-destructive-foreground font-mono">
          EVIDENCE SNAPSHOT
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
  const [violationList, setViolationList] = useState<ViolationEvent[]>([]);
  const [acked, setAcked] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/violations")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setViolationList(data);
        }
      })
      .catch((err) => console.error("Failed to fetch violations", err))
      .finally(() => setLoading(false));
  }, []);

  const openViolations = violationList.filter((v) => !v.acknowledged && !acked.includes(v.id));

  const handleAcknowledge = (id: string) => {
    setAcked((prev) => [...prev, id]);
    fetch(`/api/violations/${id}/acknowledge`, { method: "POST" }).catch((err) =>
      console.error("Ack failed", err),
    );
  };

  return (
    <AppShell>
      <PageHeader
        title="Active Violations & Incident Management"
        subtitle="Events confirmed by the rule engine and temporal validator, awaiting supervisor acknowledgement."
        actions={
          <span className="telemetry rounded border border-destructive/50 bg-destructive/10 px-3 py-1.5 text-[11px] text-destructive font-semibold">
            {openViolations.length} UNACKNOWLEDGED
          </span>
        }
      />

      <div className="space-y-3">
        {loading ? (
          <div className="rounded border border-border panel-surface p-12 text-center text-muted-foreground">
            <div className="animate-pulse text-sm">Loading violation events from database...</div>
          </div>
        ) : openViolations.length === 0 ? (
          <div className="rounded border border-border panel-surface p-12 text-center text-muted-foreground">
            <ShieldAlert className="size-10 text-success mx-auto mb-2 opacity-80" />
            <h3 className="display-title text-base text-foreground">No Unacknowledged Violations</h3>
            <p className="text-xs text-muted-foreground mt-1">
              All detected safety events have been reviewed and acknowledged.
            </p>
          </div>
        ) : (
          openViolations.map((v) => {
            const isAcked = acked.includes(v.id);
            return (
              <article
                key={v.id}
                className={`relative overflow-hidden rounded ${isAcked ? "panel-surface opacity-60" : "alert-surface"}`}
              >
                <div className="hazard-stripe absolute inset-y-0 left-0 w-1.5" />
                <div className="flex flex-col gap-4 pl-6 pr-4 py-4 lg:flex-row lg:items-center">
                  <Evidence imagePath={v.imagePath} missing={v.missing} />

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <ShieldAlert className="size-4 text-destructive" />
                      <h2 className="display-title text-base">{v.type}</h2>
                      <span className="telemetry rounded-sm bg-background/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        {v.id}
                      </span>
                    </div>
                    <div className="telemetry mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
                      <span>WORKER {v.workerId}</span>
                      <span>ZONE {v.zoneId}</span>
                      <span>CAMERA {v.cameraId}</span>
                      <span>{formatTime(v.timestamp)}</span>
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
                          className="rounded-sm border border-destructive/50 bg-destructive/15 px-2 py-0.5 text-[11px] text-destructive"
                        >
                          Missing: {ppeLabel(m)}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-col items-stretch gap-2 lg:w-40">
                    <div className="rounded border border-border bg-background/40 px-3 py-2 text-center">
                      <div className="display-title text-[10px] text-muted-foreground">Confidence</div>
                      <div className="telemetry text-xl text-destructive font-mono">
                        {(v.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                    <button
                      disabled={isAcked}
                      onClick={() => handleAcknowledge(v.id)}
                      className="display-title inline-flex items-center justify-center gap-1.5 rounded bg-primary px-3 py-2 text-[11px] text-primary-foreground disabled:opacity-50"
                    >
                      <Check className="size-3.5" /> {isAcked ? "Acknowledged" : "Acknowledge"}
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
