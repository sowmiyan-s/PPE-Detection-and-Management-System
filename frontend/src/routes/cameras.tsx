import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { Plus, Trash2, Edit2, X, Settings } from "lucide-react";

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
          "Registry of connected 1080p streams with target vs actual FPS, inference latency, zone assignment and new camera registration.",
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
  const { data: physicalCams } = useSessionFetch<{ id: string; name: string }[]>("/api/devices/cameras", []);

  const cameraList = ctxCameras.length > 0 ? ctxCameras : fetchList;
  const loading = fetchLoading && cameraList.length === 0;

  const rawZones = ctxZones.length > 0 ? ctxZones : (zoneData?.zones?.length > 0 ? zoneData.zones : zoneData?.db_zones);
  const zoneList = (rawZones && rawZones.length > 0) ? rawZones : DEFAULT_ZONES;

  // New Form state
  const [cameraType, setCameraType] = useState("webcam");
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("0");
  const [formZone, setFormZone] = useState("");
  const [formFps, setFormFps] = useState("20");

  // Edit Form state
  const [editName, setEditName] = useState("");
  const [editSource, setEditSource] = useState("");
  const [editZone, setEditZone] = useState("");
  const [editFps, setEditFps] = useState("20");

  useEffect(() => {
    if (physicalCams.length > 0 && formUrl === "0" && physicalCams[0]?.id) {
      setFormUrl(physicalCams[0].id);
    }
  }, [physicalCams]);

  const handleTypeChange = (t: string) => {
    setCameraType(t);
    if (t === "webcam") {
      setFormUrl(physicalCams.length > 0 ? (physicalCams[0]?.id || "0") : "0");
    } else {
      setFormUrl("");
    }
  };

  const handleAddCamera = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) return;

    const newCam = {
      name: formName.trim(),
      source: formUrl.trim() || "0",
      streamUrl: formUrl.trim() || "0",
      zoneId: formZone || "ZONE-01",
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
    setFormName("");
    setFormUrl("");
    setFormFps("20");
  };

  const openEditModal = (cam: Camera) => {
    setEditingCamera(cam);
    setEditName(cam.name);
    setEditSource(cam.streamUrl || "0");
    setEditZone(cam.zoneId || "ZONE-01");
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
        subtitle="Each stream is bound to a safety zone; configure camera names, sources, target FPS and zone assignments as needed."
        actions={
          <button
            onClick={() => setShowForm((s) => !s)}
            className="display-title inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-[11px] text-primary-foreground"
          >
            <Plus className="size-3.5" /> Register new camera
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
              <Field label="Stream Source / RTSP URL / Index" placeholder="0 or https://..." value={editSource} onChange={setEditSource} />
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
          className="mb-3 grid gap-3 rounded panel-surface p-4 md:grid-cols-2 xl:grid-cols-4"
        >
          <Field label="Camera name" placeholder="Silo Platform East" value={formName} onChange={setFormName} />
          <label className="block">
            <span className="display-title text-[10px] text-muted-foreground">Camera Type</span>
            <select
              value={cameraType}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
            >
              <option value="webcam">Local Webcam</option>
              <option value="youtube">YouTube Stream</option>
              <option value="stream">RTSP / Direct Stream</option>
            </select>
          </label>
          {cameraType === "webcam" ? (
            <label className="block">
              <span className="display-title text-[10px] text-muted-foreground">Select Webcam</span>
              <select
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
              >
                {physicalCams.length === 0 && <option value="0">Default (0)</option>}
                {physicalCams.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} (Index {c.id})
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <Field label={cameraType === "youtube" ? "YouTube URL" : "Stream URL (RTSP/HTTP)"} placeholder="https://..." value={formUrl} onChange={setFormUrl} />
          )}
          <label className="block">
            <span className="display-title text-[10px] text-muted-foreground">Zone</span>
            <select
              value={formZone}
              onChange={(e) => setFormZone(e.target.value)}
              className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
            >
              <option value="">Select zone</option>
              {zoneList.map((z: any) => (
                <option key={z.id} value={z.id}>
                  {z.name}
                </option>
              ))}
            </select>
          </label>
          <Field label="Target FPS" placeholder="20" value={formFps} onChange={setFormFps} />
          <div className="md:col-span-2 xl:col-span-4">
            <button
              type="submit"
              className="display-title rounded bg-primary px-4 py-2 text-[11px] text-primary-foreground"
            >
              Add camera to pipeline
            </button>
          </div>
        </form>
      ) : null}

      <div className="overflow-x-auto rounded panel-surface">
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="display-title border-b border-border text-left text-[10px] text-muted-foreground">
              <th className="px-3 py-2.5">Camera</th>
              <th className="px-3 py-2.5">Zone</th>
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
                <td colSpan={8} className="px-3 py-8 text-center text-sm text-muted-foreground animate-pulse">
                  Loading camera registry...
                </td>
              </tr>
            ) : cameraList.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-sm text-muted-foreground">
                  No active camera streams configured in backend database.
                </td>
              </tr>
            ) : (
              cameraList.map((c) => (
                <tr key={c.id} className="hover:bg-accent/40">
                  <td className="px-3 py-2.5">
                    <div className="font-medium">{c.name}</div>
                    <div className="telemetry text-[11px] text-muted-foreground">
                      {c.id} · {c.streamUrl}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{c.zoneId}</td>
                  <td className="telemetry px-3 py-2.5 text-xs">{c.resolution}</td>
                  <td className="telemetry px-3 py-2.5 text-xs">{c.targetFps}</td>
                  <td
                    className={`telemetry px-3 py-2.5 text-xs ${
                      c.actualFps === 0
                        ? "text-muted-foreground"
                        : c.actualFps < c.targetFps * 0.8
                          ? "text-destructive"
                          : "text-success"
                    }`}
                  >
                    {c.actualFps.toFixed(1)}
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
                        className="display-title rounded border border-primary/20 bg-primary/10 px-2 py-1 text-[10px] text-primary hover:bg-primary hover:text-primary-foreground"
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
              ))
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

