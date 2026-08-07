import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { Plus } from "lucide-react";

import { AppShell, PageHeader, StatusDot } from "@/components/app-shell";
import { type Camera } from "@/lib/mock-data";

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

function CamerasPage() {
  const [showForm, setShowForm] = useState(false);
  const [cameraList, setCameraList] = useState<Camera[]>([]);
  const [zoneList, setZoneList] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formZone, setFormZone] = useState("");
  const [formFps, setFormFps] = useState("20");

  useEffect(() => {
    Promise.allSettled([
      fetch("/api/cameras").then((res) => (res.ok ? res.json() : [])),
      fetch("/api/zones").then((res) => (res.ok ? res.json() : { db_zones: [] })),
    ]).then(([camerasRes, zonesRes]) => {
      if (camerasRes.status === "fulfilled" && Array.isArray(camerasRes.value)) {
        setCameraList(camerasRes.value);
      }
      if (zonesRes.status === "fulfilled") {
        const data = zonesRes.value;
        setZoneList(data.db_zones || []);
      }
      setLoading(false);
    });
  }, []);

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
        // Refresh camera list
        return fetch("/api/cameras").then((res) => (res.ok ? res.json() : []));
      })
      .then((data) => {
        if (Array.isArray(data)) setCameraList(data);
      })
      .catch((err) => console.error("Failed to add camera", err));

    setShowForm(false);
    setFormName("");
    setFormUrl("");
    setFormFps("20");
  };

  return (
    <AppShell>
      <PageHeader
        title="Camera Management & Stream Registry"
        subtitle="Each stream is bound to a zone; the rule engine applies that zone's PPE requirements to every tracked worker."
        actions={
          <button
            onClick={() => setShowForm((s) => !s)}
            className="display-title inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-[11px] text-primary-foreground"
          >
            <Plus className="size-3.5" /> Register new camera
          </button>
        }
      />

      {showForm ? (
        <form
          onSubmit={handleAddCamera}
          className="mb-3 grid gap-3 rounded panel-surface p-4 md:grid-cols-2 xl:grid-cols-4"
        >
          <Field label="Camera name" placeholder="Silo Platform East" value={formName} onChange={setFormName} />
          <Field label="RTSP stream URL" placeholder="rtsp://10.20.4.17/stream1" value={formUrl} onChange={setFormUrl} />
          <label className="block">
            <span className="display-title text-[10px] text-muted-foreground">Zone</span>
            <select
              value={formZone}
              onChange={(e) => setFormZone(e.target.value)}
              className="telemetry mt-1 w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
            >
              <option value="">Select zone</option>
              {zoneList.map((z) => (
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
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-sm text-muted-foreground animate-pulse">
                  Loading camera registry...
                </td>
              </tr>
            ) : cameraList.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-sm text-muted-foreground">
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
