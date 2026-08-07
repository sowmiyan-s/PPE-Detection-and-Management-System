import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { AlertTriangle, Camera, HardHat, ShieldCheck, Activity, Grid, Maximize2, Play, CheckCircle2, Radio } from "lucide-react";

import { AppShell, PageHeader, StatusDot } from "@/components/app-shell";

export const Route = createFileRoute("/live")({
  head: () => ({
    meta: [
      { title: "Live AI Monitoring — EdgeVision" },
      {
        name: "description",
        content: "Real-time multi-camera YOLOv8 vision pipeline monitoring grid and worker compliance telemetry.",
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

type CameraItem = {
  id: string;
  name: string;
  zoneId: string;
  resolution: string;
  targetFps: number;
  actualFps: number;
  latencyMs: number;
  status: "online" | "offline";
  streamUrl: string;
};

function LivePage() {
  const [frame, setFrame] = useState<string | null>(null);
  const [workers, setWorkers] = useState<WorkerState[]>([]);
  const [fps, setFps] = useState<number>(0);
  const [zone, setZone] = useState<string>("");
  const [wsStatus, setWsStatus] = useState<"offline" | "online" | "connecting">("connecting");
  const [cameraList, setCameraList] = useState<CameraItem[]>([]);
  const [selectedCamId, setSelectedCamId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "focus">("grid");
  const [filterMode, setFilterMode] = useState<"all" | "violations" | "compliant" | "has_helmet" | "has_vest">("all");
  const wsRef = useRef<WebSocket | null>(null);

  const fetchCameras = () => {
    fetch("/api/cameras")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setCameraList(data);
          if (data.length > 0 && !selectedCamId) {
            setSelectedCamId(data[0].id);
          }
        }
      })
      .catch((err) => console.error("Failed to load cameras", err));
  };

  useEffect(() => {
    fetchCameras();
    const interval = setInterval(fetchCameras, 5000);
    connectWs();
    return () => {
      clearInterval(interval);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const connectWs = () => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
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

  const handleActivateCam = (camId: string) => {
    setSelectedCamId(camId);
    fetch(`/api/cameras/${camId}/activate`, { method: "POST" })
      .then(() => fetchCameras())
      .catch((err) => console.error("Failed to activate camera", err));
  };

  const selectedCam = cameraList.find((c) => c.id === selectedCamId) || cameraList[0];
  const compliantCount = workers.filter((w) => w.compliant).length;
  const violationCount = workers.filter((w) => !w.compliant).length;

  return (
    <AppShell>
      <PageHeader
        title="Live AI Monitoring Feed"
        subtitle="Multi-camera cluster monitoring grid. View all active feeds or focus on a specific camera stream for real-time telemetry."
        actions={[
          <div key="view-toggle" className="flex items-center gap-1 rounded border border-border bg-panel p-1">
            <button
              onClick={() => setViewMode("grid")}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                viewMode === "grid" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Grid className="size-3.5" /> All Cards Grid
            </button>
            <button
              onClick={() => setViewMode("focus")}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                viewMode === "focus" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Maximize2 className="size-3.5" /> Single Focus View
            </button>
          </div>,
          <div key="status" className="flex items-center gap-2 rounded border border-border bg-panel px-3 py-1.5">
            <span className="text-xs text-muted-foreground capitalize">WebSocket: {wsStatus}</span>
            <StatusDot status={wsStatus === "online" ? "online" : "offline"} />
          </div>,
        ]}
      />

      {/* Multiple Camera Cards Grid View */}
      {viewMode === "grid" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold display-title">
              Active Monitored Cameras ({cameraList.length})
            </div>
            <div className="telemetry text-xs text-muted-foreground">
              Select any card to switch live AI stream feed
            </div>
          </div>

          {cameraList.length === 0 ? (
            <div className="rounded-lg border border-border panel-surface p-12 text-center text-muted-foreground">
              <Camera className="size-10 mx-auto text-muted-foreground/40 mb-3" />
              <p className="text-sm font-medium">No cameras currently configured.</p>
              <p className="text-xs mt-1">Go to Camera Management to add your first webcam, RTSP stream, or YouTube feed.</p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {cameraList.map((cam) => {
                const isSelected = selectedCam?.id === cam.id;
                const isLive = cam.status === "online";

                return (
                  <div
                    key={cam.id}
                    className={`relative overflow-hidden rounded-lg border panel-surface transition-all ${
                      isSelected
                        ? "border-primary ring-1 ring-primary shadow-lg"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    {/* Top Status Banner */}
                    <div className="relative aspect-video bg-black/90 overflow-hidden flex items-center justify-center">
                      {(isSelected || isLive) && frame ? (
                        <img
                          src={`data:image/jpeg;base64,${frame}`}
                          alt={cam.name}
                          className="size-full object-contain"
                        />
                      ) : (
                        <div className="flex flex-col items-center justify-center text-center p-4">
                          <Camera className="size-8 text-muted-foreground/50 mb-2" />
                          <span className="text-xs font-medium text-foreground">{cam.name}</span>
                          <span className="telemetry text-[10px] text-muted-foreground mt-1 truncate max-w-[200px]">
                            {cam.streamUrl}
                          </span>
                        </div>
                      )}

                      {/* Overlaid Badges */}
                      <div className="absolute top-2 left-2 flex items-center gap-1.5">
                        <span className="rounded bg-background/80 px-2 py-0.5 text-[10px] telemetry font-mono backdrop-blur border border-border">
                          {cam.zoneId}
                        </span>
                        {isLive && (
                          <span className="flex items-center gap-1 rounded bg-success/20 text-success px-2 py-0.5 text-[10px] font-semibold backdrop-blur border border-success/30">
                            <Radio className="size-3 animate-pulse" /> LIVE
                          </span>
                        )}
                      </div>

                      {isSelected && (
                        <div className="absolute top-2 right-2 rounded bg-primary px-2 py-0.5 text-[10px] font-bold text-primary-foreground uppercase tracking-wider">
                          Active Stream
                        </div>
                      )}
                    </div>

                    {/* Card Content */}
                    <div className="p-4 space-y-3">
                      <div>
                        <h3 className="font-semibold text-sm line-clamp-1">{cam.name}</h3>
                        <div className="telemetry text-xs text-muted-foreground mt-0.5">
                          ID: {cam.id} · Resolution: {cam.resolution}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs telemetry bg-background/40 p-2 rounded border border-border/50">
                        <div>
                          <span className="text-muted-foreground block text-[10px]">Target FPS</span>
                          <span className="font-semibold">{cam.targetFps} FPS</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block text-[10px]">Status</span>
                          <StatusDot status={cam.status} label={cam.status} />
                        </div>
                      </div>

                      {/* Card Actions */}
                      <div className="flex items-center gap-2 pt-1">
                        {!isSelected ? (
                          <button
                            onClick={() => handleActivateCam(cam.id)}
                            className="w-full flex items-center justify-center gap-1.5 rounded bg-primary/10 border border-primary/30 px-3 py-1.5 text-xs text-primary font-medium hover:bg-primary hover:text-primary-foreground transition-colors"
                          >
                            <Play className="size-3.5" /> Set Active Stream
                          </button>
                        ) : (
                          <button
                            onClick={() => setViewMode("focus")}
                            className="w-full flex items-center justify-center gap-1.5 rounded bg-primary px-3 py-1.5 text-xs text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
                          >
                            <Maximize2 className="size-3.5" /> Expand Focus Feed
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Single Focus View Mode */}
      {viewMode === "focus" && (
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
                {selectedCam && (
                  <div className="rounded bg-primary/20 px-2.5 py-1 text-xs text-primary backdrop-blur border border-primary/40 font-medium">
                    {selectedCam.name} ({selectedCam.id})
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
                <div className="flex items-center gap-2">
                  <h2 className="display-title text-sm">Real-Time Detections</h2>
                  <select
                    className="bg-background border border-border text-xs rounded px-2 py-1 outline-none focus:ring-1 focus:ring-primary text-muted-foreground"
                    value={filterMode}
                    onChange={(e) => setFilterMode(e.target.value as any)}
                  >
                    <option value="all">Show All</option>
                    <option value="violations">Violations Only</option>
                    <option value="compliant">Compliant Only</option>
                    <option value="has_helmet">Wearing Helmet</option>
                    <option value="has_vest">Wearing Vest</option>
                  </select>
                </div>
                <span className="telemetry text-[10px] text-muted-foreground">ByteTrack IDs</span>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2 max-h-[550px] pr-1">
                {workers.filter(w => {
                  if (filterMode === "violations") return !w.compliant;
                  if (filterMode === "compliant") return w.compliant;
                  if (filterMode === "has_helmet") return w.detected_ppe?.includes("helmet");
                  if (filterMode === "has_vest") return w.detected_ppe?.includes("vest");
                  return true;
                }).length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                    <HardHat className="size-8 text-muted-foreground/40 mb-2" />
                    <p className="text-xs">No workers match the current filter in camera view.</p>
                  </div>
                ) : (
                  workers.filter(w => {
                    if (filterMode === "violations") return !w.compliant;
                    if (filterMode === "compliant") return w.compliant;
                    if (filterMode === "has_helmet") return w.detected_ppe?.includes("helmet");
                    if (filterMode === "has_vest") return w.detected_ppe?.includes("vest");
                    return true;
                  }).map((w) => (
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
      )}
    </AppShell>
  );
}

