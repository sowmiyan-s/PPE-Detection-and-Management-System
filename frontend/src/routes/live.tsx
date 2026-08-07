import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { AlertTriangle, Camera, HardHat, ShieldCheck, Activity } from "lucide-react";

import { AppShell, PageHeader, StatusDot } from "@/components/app-shell";

export const Route = createFileRoute("/live")({
  head: () => ({
    meta: [
      { title: "Live AI Monitoring — EdgeVision" },
      {
        name: "description",
        content: "Real-time YOLOv8 vision pipeline inference stream and worker compliance telemetry.",
      },
    ],
  }),
  component: LivePage,
});

type WorkerState = {
  worker_id: string;
  compliant: boolean;
  missing_ppe: string[];
  detected_ppe: string[];
  confidence: number;
  zone: string;
};

function LivePage() {
  const [frame, setFrame] = useState<string | null>(null);
  const [workers, setWorkers] = useState<WorkerState[]>([]);
  const [fps, setFps] = useState<number>(0);
  const [zone, setZone] = useState<string>("");
  const [wsStatus, setWsStatus] = useState<"offline" | "online" | "connecting">("connecting");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    connectWs();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const connectWs = () => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname || "localhost";
    // Connect directly to backend FastAPI WebSocket port 8000
    const wsUrl = `${protocol}//${host}:8000/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus("online");
    ws.onclose = () => {
      setWsStatus("offline");
      setTimeout(connectWs, 3000);
    };
    ws.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.frame) setFrame(d.frame);
        if (d.fps !== undefined) setFps(d.fps);
        if (d.zone) setZone(d.zone);
        if (d.workers) setWorkers(d.workers);
      } catch (err) {
        console.error("WS Parse Error", err);
      }
    };
  };

  const compliantCount = workers.filter((w) => w.compliant).length;
  const violationCount = workers.filter((w) => !w.compliant).length;

  return (
    <AppShell>
      <PageHeader
        title="Live AI Monitoring Stream"
        subtitle="Real-time multi-stage YOLOv8 inference feed, ByteTrack tracking IDs, and person-to-PPE compliance telemetry."
        actions={[
          <div key="status" className="flex items-center gap-2 rounded border border-border bg-panel px-3 py-1.5">
            <span className="text-xs text-muted-foreground capitalize">WebSocket: {wsStatus}</span>
            <StatusDot status={wsStatus === "online" ? "online" : "offline"} />
          </div>,
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Left 2 Cols: Main Real-Time Video Monitor */}
        <div className="flex flex-col gap-3 lg:col-span-2">
          <div className="relative aspect-video overflow-hidden rounded-lg border border-border bg-black shadow-2xl">
            {frame ? (
              <img
                src={`data:image/jpeg;base64,${frame}`}
                alt="Live AI Inference Stream"
                className="size-full object-contain"
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted-foreground">
                <Camera className="size-10 animate-pulse text-muted-foreground/60" />
                <div className="text-sm font-medium">WAITING FOR LIVE AI VIDEO STREAM</div>
                <div className="telemetry text-xs text-muted-foreground/80">Connecting to WebSocket /ws ...</div>
              </div>
            )}

            {/* Overlaid Telemetry Metrics */}
            <div className="absolute left-3 top-3 flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded bg-background/80 px-2.5 py-1 text-xs text-primary backdrop-blur border border-primary/30">
                <Activity className="size-3.5 animate-pulse text-primary" />
                <span className="telemetry font-mono font-semibold">{fps.toFixed(1)} FPS</span>
              </div>
              {zone && (
                <div className="rounded bg-background/80 px-2.5 py-1 text-xs text-foreground backdrop-blur border border-border">
                  ZONE: <span className="telemetry font-mono font-semibold uppercase">{zone.replace(/_/g, " ")}</span>
                </div>
              )}
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-3 gap-3">
            <div className="flex items-center justify-between rounded border border-border panel-surface p-3">
              <div>
                <div className="text-xs text-muted-foreground">Tracked Workers</div>
                <div className="telemetry text-lg font-bold">{workers.length}</div>
              </div>
              <HardHat className="size-5 text-primary" />
            </div>

            <div className="flex items-center justify-between rounded border border-border panel-surface p-3">
              <div>
                <div className="text-xs text-muted-foreground">Compliant</div>
                <div className="telemetry text-lg font-bold text-success">{compliantCount}</div>
              </div>
              <ShieldCheck className="size-5 text-success" />
            </div>

            <div className="flex items-center justify-between rounded border border-border panel-surface p-3">
              <div>
                <div className="text-xs text-muted-foreground">Violations</div>
                <div className="telemetry text-lg font-bold text-destructive">{violationCount}</div>
              </div>
              <AlertTriangle className="size-5 text-destructive" />
            </div>
          </div>
        </div>

        {/* Right Col: Real-Time Worker Detections Panel */}
        <div className="flex flex-col gap-3">
          <div className="flex-1 rounded-lg border border-border panel-surface p-4 flex flex-col">
            <div className="flex items-center justify-between border-b border-border pb-3 mb-3">
              <h2 className="display-title text-sm">Real-Time Detections ({workers.length})</h2>
              <span className="telemetry text-[10px] text-muted-foreground">ByteTrack IDs</span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 max-h-[550px] pr-1">
              {workers.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                  <HardHat className="size-8 text-muted-foreground/40 mb-2" />
                  <p className="text-xs">No workers currently detected in camera view.</p>
                </div>
              ) : (
                workers.map((w) => (
                  <div
                    key={w.worker_id}
                    className={`rounded border-l-4 p-3 bg-background/50 transition-all ${
                      w.compliant ? "border-success bg-success/5" : "border-destructive bg-destructive/5"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-sm">{w.worker_id}</span>
                      <span className="telemetry text-xs text-muted-foreground">
                        {(w.confidence * 100).toFixed(0)}% conf
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-1 mt-2">
                      {w.detected_ppe?.map((p) => (
                        <span
                          key={p}
                          className="rounded bg-success/20 px-2 py-0.5 text-[10px] text-success border border-success/30"
                        >
                          {p}
                        </span>
                      ))}
                      {w.missing_ppe?.map((p) => (
                        <span
                          key={`miss-${p}`}
                          className="flex items-center gap-1 rounded bg-destructive/20 px-2 py-0.5 text-[10px] text-destructive border border-destructive/30"
                        >
                          <AlertTriangle className="size-3" /> missing {p}
                        </span>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
