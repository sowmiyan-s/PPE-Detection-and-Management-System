import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { Plus, Trash2, Edit2, X, Settings, Video, Globe, RefreshCw, Radio } from "lucide-react";

import { AppShell, PageHeader, StatusDot } from "@/components/app-shell";
import { type Camera } from "@/lib/mock-data";
import { useSessionFetch, invalidateSessionCache } from "@/hooks/use-session-fetch";
import { useAppData } from "@/lib/data-context";

export const Route = createFileRoute("/cameras")({
  head: () => ({
    meta: [
      { title: "Camera Management — EdgeVision Stream Registry" },
      {
        name: "description",
        content:
          "Registry of connected webcams & RTSP/HTTP stream links with target vs actual FPS, inference latency, zone assignment and new camera registration.",
      },
    ],
  }),
  component: CamerasPage,
});

const DEFAULT_ZONES = [
  { id: "general_plant", name: "General Plant Floor" },
  { id: "restricted_machinery", name: "Restricted Machinery Zone" },
  { id: "hazardous_material", name: "Hazardous Chemical Area" },
  { id: "ZONE-01", name: "Zone 01 — Assembly Floor" },
  { id: "ZONE-02", name: "Zone 02 — High Elevation Site" },
];

function CamerasPage() {
  const { cameras: ctxCameras, zones: ctxZones, refetchCameras } = useAppData();
  const [showForm, setShowForm] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);

  const { data: fetchList, loading: fetchLoading, refetch: manualRefetch } = useSessionFetch<Camera[]>("/api/cameras", []);
  const { data: zoneData } = useSessionFetch<any>("/api/zones", { zones: [], db_zones: [] });
  const { data: physicalCams, refetch: refetchDevices } = useSessionFetch<{ id: string; name: string; source: string }[]>("/api/devices/cameras", []);

  const cameraList = ctxCameras.length > 0 ? ctxCameras : fetchList;
  const loading = fetchLoading && cameraList.length === 0;

  const rawZones = ctxZones.length > 0 ? ctxZones : (zoneData?.zones?.length > 0 ? zoneData.zones : zoneData?.db_zones);
  const zoneList = (rawZones && rawZones.length > 0) ? rawZones : DEFAULT_ZONES;

  // New Form state
  const [cameraType, setCameraType] = useState("webcam");
  const [formName, setFormName] = useState("Local Webcam (Index 0)");
  const [formUrl, setFormUrl] = useState("0");
  const [formZone, setFormZone] = useState("general_plant");
  const [formFps, setFormFps] = useState("20");

  // Edit Form state
  const [editName, setEditName] = useState("");
  const [editSource, setEditSource] = useState("");
  const [editZone, setEditZone] = useState("");
  const [editFps, setEditFps] = useState("20");

  // Sync multi-device updates via WebSocket
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (["camera_added", "camera_switched", "camera_deleted", "camera_updated", "settings_updated"].includes(d.type)) {
          invalidateSessionCache("/api/cameras");
          refetchCameras();
          manualRefetch(true);
        }
      } catch {}
    };

    return () => {
      ws.close();
    };
  }, [refetchCameras, manualRefetch]);

  useEffect(() => {
    if (physicalCams.length > 0 && formUrl === "0" && physicalCams[0]?.id) {
      setFormUrl(physicalCams[0].id);
    }
  }, [physicalCams]);

  const handleTypeChange = (t: string) => {
    setCameraType(t);
    if (t === "webcam") {
      const defCam = physicalCams.length > 0 ? (physicalCams[0]?.id || "0") : "0";
      setFormUrl(defCam);
      setFormName(`Local Webcam (Index ${defCam})`);
    } else {
      setFormUrl("rtsp://localhost:8554/cam");
      setFormName("RTSP Camera Feed");
    }
  };

  const handleAddCamera = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) return;

    const newCam = {
      name: formName.trim(),
      source: formUrl.trim() || "0",
      streamUrl: formUrl.trim() || "0",
      type: cameraType,
      zoneId: formZone || "general_plant",
      targetFps: parseInt(formFps) || 20,
    };

    fetch("/api/cameras", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newCam),
    })
      .then(() => {
        invalidateSessionCache("/api/cameras");
        refetchCameras();
        manualRefetch(true);
      })
      .catch((err) => console.error("Failed to add camera", err));

    setShowForm(false);
    setFormName("Local Webcam (Index 0)");
    setFormUrl("0");
    setFormFps("20");
  };

  const openEditModal = (cam: Camera) => {
    setEditingCamera(cam);
    setEditName(cam.name);
    setEditSource(cam.streamUrl || "0");
    setEditZone(cam.zoneId || "general_plant");
    setEditFps(String(cam.targetFps || 20));
  };

  const handleUpdateCamera = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCamera || !editName.trim()) return;

    const updated = {
      name: editName.trim(),
      source: editSource.trim() || "0",
      streamUrl: editSource.trim() || "0",
      zoneId: editZone,
      targetFps: parseInt(editFps) || 20,
    };

    fetch(`/api/cameras/${editingCamera.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    })
      .then(() => {
        invalidateSessionCache("/api/cameras");
        refetchCameras();
        manualRefetch(true);
        setEditingCamera(null);
      })
      .catch((err) => console.error("Failed to update camera", err));
  };

  const handleActivate = (camId: string) => {
    fetch(`/api/cameras/${camId}/activate`, { method: "POST" })
      .then(() => {
        invalidateSessionCache("/api/cameras");
        refetchCameras();
        manualRefetch(true);
      })
      .catch((err) => console.error("Failed to activate camera", err));
  };

  const handleDeleteCamera = (camId: string) => {
    if (confirm("Are you sure you want to delete this camera from the MongoDB cluster?")) {
      fetch(`/api/cameras/${camId}`, { method: "DELETE" })
        .then(() => {
          invalidateSessionCache("/api/cameras");
          refetchCameras();
          manualRefetch(true);
        })
        .catch((err) => console.error("Failed to delete camera", err));
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Camera Configuration & Stream Registry"
        subtitle="Manage connected hardware webcams and network RTSP/HTTP stream links. Store configuration in MongoDB and synchronize active streams across all client devices."
        actions={
          <button
            onClick={() => {
              refetchDevices(true);
              setShowForm((s) => !s);
            }}
            className="display-title inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-[11px] text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="size-3.5" /> Register new camera / stream
          </button>
        }
      />

      {/* Edit Camera Modal */}
      {editingCamera && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <form
            onSubmit={handleUpdateCamera}
            className="relative max-w-lg w-full bg-panel rounded-lg border border-border overflow-hidden shadow-2xl p-5 space-y-4"
          >
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Settings className="size-5 text-primary" />
                <h3 className="font-semibold text-base display-title text-foreground">
                  Edit Camera Config ({editingCamera.id})
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setEditingCamera(null)}
                className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="space-y-3">
              <Field label="Camera Name" placeholder="Factory Floor Stream 1" value={editName} onChange={setEditName} />
              <Field label="Stream Source / RTSP URL / Webcam Index" placeholder="0 or rtsp://192.168.1.100:554/cam" value={editSource} onChange={setEditSource} />
              <label className="block">
                <span className="display-title text-[10px] text-muted-foreground">Assigned Zone</span>
                <select
                  value={editZone}
                  onChange={(e) => setEditZone(e.target.value)}
                  className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
                >
                  {zoneList.map((z: any) => (
                    <option key={z.id} value={z.id}>
                      {z.name} ({z.id})
                    </option>
                  ))}
                </select>
              </label>
              <Field label="Target FPS" placeholder="20" value={editFps} onChange={setEditFps} />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => setEditingCamera(null)}
                className="px-4 py-2 rounded text-xs font-medium border border-border text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 rounded bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
              >
                Save Camera Config
              </button>
            </div>
          </form>
        </div>
      )}

      {showForm ? (
        <form
          onSubmit={handleAddCamera}
          className="mb-3 grid gap-3 rounded panel-surface p-4 md:grid-cols-2 xl:grid-cols-4 border border-border shadow-lg"
        >
          <Field label="Camera Name" placeholder="Silo Platform East" value={formName} onChange={setFormName} />
          
          <label className="block">
            <span className="display-title text-[10px] text-muted-foreground">Source Type</span>
            <select
              value={cameraType}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
            >
              <option value="webcam">Local Hardware Webcam</option>
              <option value="stream">RTSP / RTSPS / HTTP Stream Link</option>
              <option value="youtube">YouTube Video / Live Link</option>
            </select>
          </label>

          {cameraType === "webcam" ? (
            <label className="block">
              <div className="flex items-center justify-between">
                <span className="display-title text-[10px] text-muted-foreground">Available Hardware Webcams</span>
                <button
                  type="button"
                  onClick={() => refetchDevices(true)}
                  className="text-[10px] text-primary hover:underline flex items-center gap-1"
                >
                  <RefreshCw className="size-2.5" /> Refresh
                </button>
              </div>
              <select
                value={formUrl}
                onChange={(e) => {
                  setFormUrl(e.target.value);
                  setFormName(`Local Webcam (Index ${e.target.value})`);
                }}
                className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
              >
                {physicalCams.length === 0 && <option value="0">Default Hardware Webcam (Index 0)</option>}
                {physicalCams.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <Field
              label={cameraType === "youtube" ? "YouTube Stream / Video URL" : "Stream URL (RTSP / RTSPS / HTTP / MediaMTX)"}
              placeholder={cameraType === "youtube" ? "https://www.youtube.com/watch?v=..." : "rtsp://admin:pass@192.168.1.100:554/cam"}
              value={formUrl}
              onChange={setFormUrl}
            />
          )}

          <label className="block">
            <span className="display-title text-[10px] text-muted-foreground">Safety Zone</span>
            <select
              value={formZone}
              onChange={(e) => setFormZone(e.target.value)}
              className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
            >
              <option value="">Select zone</option>
              {zoneList.map((z: any) => (
                <option key={z.id} value={z.id}>
                  {z.name} ({z.id})
                </option>
              ))}
            </select>
          </label>

          <Field label="Target FPS" placeholder="20" value={formFps} onChange={setFormFps} />

          <div className="md:col-span-2 xl:col-span-4 flex items-center justify-between pt-2 border-t border-border/50">
            <span className="text-[11px] text-muted-foreground flex items-center gap-1.5">
              <Radio className="size-3.5 text-primary animate-pulse" />
              New camera will be stored in MongoDB and auto-activated for AI vision inference.
            </span>
            <button
              type="submit"
              className="display-title rounded bg-primary px-4 py-2 text-[11px] text-primary-foreground font-semibold hover:bg-primary/90 transition-colors"
            >
              Add Camera & Connect Stream
            </button>
          </div>
        </form>
      ) : null}

      <div className="overflow-x-auto rounded panel-surface border border-border shadow">
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="display-title border-b border-border text-left text-[10px] text-muted-foreground bg-background/40">
              <th className="px-3 py-2.5">Camera Source</th>
              <th className="px-3 py-2.5">Type</th>
              <th className="px-3 py-2.5">Safety Zone</th>
              <th className="px-3 py-2.5">Resolution</th>
              <th className="px-3 py-2.5">Target FPS</th>
              <th className="px-3 py-2.5">Actual FPS</th>
              <th className="px-3 py-2.5">Latency</th>
              <th className="px-3 py-2.5">Status</th>
              <th className="px-3 py-2.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-sm text-muted-foreground animate-pulse">
                  Loading camera registry from MongoDB...
                </td>
              </tr>
            ) : cameraList.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-sm text-muted-foreground">
                  No active camera streams configured in backend database.
                </td>
              </tr>
            ) : (
              cameraList.map((c: any) => {
                const isWebcam = c.streamUrl?.toString().length === 1 || !c.streamUrl?.includes("://");
                return (
                  <tr key={c.id} className="hover:bg-accent/40 transition-colors">
                    <td className="px-3 py-2.5">
                      <div className="font-medium text-foreground">{c.name}</div>
                      <div className="telemetry text-[11px] text-muted-foreground">
                        {c.id} · <span className="font-mono text-xs text-primary/90">{c.streamUrl}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      {isWebcam ? (
                        <span className="inline-flex items-center gap-1 rounded bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-400 border border-blue-500/20">
                          <Video className="size-3" /> Webcam ({c.streamUrl})
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/20">
                          <Globe className="size-3" /> Stream Link
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground font-mono text-xs">{c.zoneId}</td>
                    <td className="telemetry px-3 py-2.5 text-xs">{c.resolution}</td>
                    <td className="telemetry px-3 py-2.5 text-xs">{c.targetFps}</td>
                    <td
                      className={`telemetry px-3 py-2.5 text-xs font-semibold ${
                        c.actualFps === 0
                          ? "text-muted-foreground"
                          : c.actualFps < c.targetFps * 0.8
                            ? "text-destructive"
                            : "text-emerald-400"
                      }`}
                    >
                      {c.actualFps ? c.actualFps.toFixed(1) : "0.0"}
                    </td>
                    <td className="telemetry px-3 py-2.5 text-xs">
                      {c.latencyMs ? `${c.latencyMs} ms` : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusDot status={c.status} />
                    </td>
                    <td className="px-3 py-2.5 text-right flex items-center justify-end gap-1.5">
                      {c.status !== "online" && (
                        <button
                          onClick={() => handleActivate(c.id)}
                          className="display-title rounded border border-primary/20 bg-primary/10 px-2 py-1 text-[10px] text-primary hover:bg-primary hover:text-primary-foreground transition-colors"
                        >
                          Set Active
                        </button>
                      )}
                      <button
                        onClick={() => openEditModal(c)}
                        title="Edit Camera Settings"
                        className="rounded border border-primary/30 bg-primary/10 p-1 text-primary hover:bg-primary hover:text-primary-foreground transition-colors"
                      >
                        <Edit2 className="size-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteCamera(c.id)}
                        title="Delete Camera"
                        className="rounded border border-destructive/30 bg-destructive/10 p-1 text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}

function Field({ label, placeholder, value, onChange }: { label: string; placeholder: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="display-title text-[10px] text-muted-foreground">{label}</span>
      <input
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
      />
    </label>
  );
}

