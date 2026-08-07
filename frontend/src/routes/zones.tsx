import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { Plus, X, ShieldAlert } from "lucide-react";

import { AppShell, PageHeader } from "@/components/app-shell";
import { PPE_LABELS, type PpeKey, type Zone } from "@/lib/mock-data";

export const Route = createFileRoute("/zones")({
  head: () => ({
    meta: [
      { title: "Zone Configuration — EdgeVision Rule Engine" },
      {
        name: "description",
        content:
          "Configure required PPE per zone and tune temporal validation: frame threshold, minimum dwell time and confidence floor.",
      },
    ],
  }),
  component: ZonesPage,
});

const ppeKeys = Object.keys(PPE_LABELS) as PpeKey[];

const defaultRequired: Record<PpeKey, boolean> = {
  helmet: true,
  vest: true,
  boots: false,
  safety_belt: false,
  lanyard: false,
  hook: false,
  anchor_point: false,
};

/** Convert a zone from the API into our local Zone type */
function apiZoneToLocal(apiZone: any): Zone {
  const requiredPpe: string[] = apiZone.required_ppe || [];
  const required: Record<PpeKey, boolean> = { ...defaultRequired };
  for (const key of ppeKeys) {
    required[key] = requiredPpe.includes(key);
  }
  return {
    id: apiZone.id || apiZone.name,
    name: apiZone.name || apiZone.id,
    kind: apiZone.description || "General plant",
    required,
    frameThreshold: 8,
    dwellSeconds: 2,
    confidence: 0.60,
  };
}

function ZonesPage() {
  const [config, setConfig] = useState<Zone[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [loading, setLoading] = useState(true);

  // New Zone Form State
  const [newZoneName, setNewZoneName] = useState("");
  const [newZoneKind, setNewZoneKind] = useState<string>("General plant");
  const [newRequired, setNewRequired] = useState<Record<PpeKey, boolean>>({ ...defaultRequired });
  const [newFrameThreshold, setNewFrameThreshold] = useState(8);
  const [newDwellSeconds, setNewDwellSeconds] = useState(2);
  const [newConfidence, setNewConfidence] = useState(0.60);

  useEffect(() => {
    fetch("/api/zones")
      .then((res) => (res.ok ? res.json() : { zones: [], db_zones: [] }))
      .then((data) => {
        // Prefer db_zones which have zone IDs; fall back to rule engine zones
        const dbZones = data.db_zones || [];
        const ruleZones = data.zones || [];

        if (dbZones.length > 0) {
          setConfig(dbZones.map(apiZoneToLocal));
        } else if (ruleZones.length > 0) {
          setConfig(ruleZones.map(apiZoneToLocal));
        }
      })
      .catch((err) => console.error("Failed to fetch zones", err))
      .finally(() => setLoading(false));
  }, []);

  const update = (id: string, patch: Partial<Zone>) =>
    setConfig((c) => c.map((z) => (z.id === id ? { ...z, ...patch } : z)));

  const handleAddZone = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newZoneName.trim()) return;

    const newZone: Zone = {
      id: `ZONE-0${config.length + 1}`,
      name: newZoneName.trim(),
      kind: newZoneKind,
      required: { ...newRequired },
      frameThreshold: newFrameThreshold,
      dwellSeconds: newDwellSeconds,
      confidence: newConfidence,
    };

    setConfig((prev) => [...prev, newZone]);
    setShowAddModal(false);

    // Reset Form
    setNewZoneName("");
    setNewRequired({ ...defaultRequired });

    // Notify Backend API
    fetch("/api/zones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newZone),
    }).catch((err) => console.error("Failed to sync new zone to backend", err));
  };

  return (
    <AppShell>
      <PageHeader
        title="Zone Configuration & Custom Rules"
        subtitle="Required PPE is evaluated per zone. Temporal validation suppresses single-frame noise before an alert is raised."
        actions={[
          <button
            key="add-zone"
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded border border-primary bg-primary px-3 py-1.5 text-xs text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Plus className="size-4" />
            <span>Add Safety Zone</span>
          </button>,
        ]}
      />

      {loading ? (
        <div className="rounded panel-surface p-12 text-center text-muted-foreground animate-pulse">
          Loading zone configuration from database...
        </div>
      ) : config.length === 0 ? (
        <div className="rounded panel-surface p-12 text-center text-muted-foreground">
          <p className="text-sm">No zones configured yet.</p>
          <p className="text-xs mt-1">Click "Add Safety Zone" to create your first zone.</p>
        </div>
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {config.map((z) => (
            <section key={z.id} className="relative overflow-hidden rounded panel-surface">
              <div className="hazard-stripe absolute inset-x-0 top-0 h-1 opacity-60" />
              <div className="px-4 pb-4 pt-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="display-title text-lg">{z.name}</h2>
                    <p className="telemetry text-[11px] text-muted-foreground">
                      {z.id} · {z.kind}
                    </p>
                  </div>
                  <span className="display-title rounded-sm bg-accent px-2 py-0.5 text-[10px] text-accent-foreground">
                    {ppeKeys.filter((k) => z.required[k]).length} rules active
                  </span>
                </div>

                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  {ppeKeys.map((k) => (
                    <label
                      key={k}
                      className="flex cursor-pointer items-center justify-between gap-3 rounded border border-border bg-background/40 px-3 py-2"
                    >
                      <span className="text-sm">{PPE_LABELS[k]}</span>
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={z.required[k]}
                        onChange={(e) =>
                          update(z.id, { required: { ...z.required, [k]: e.target.checked } })
                        }
                      />
                      <span
                        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${
                          z.required[k] ? "bg-primary" : "bg-muted"
                        }`}
                      >
                        <span
                          className={`absolute top-0.5 size-4 rounded-full bg-background transition-all ${
                            z.required[k] ? "left-4.5" : "left-0.5"
                          }`}
                        />
                      </span>
                    </label>
                  ))}
                </div>

                <div className="mt-4 space-y-4 rounded border border-border bg-background/40 p-3">
                  <h3 className="display-title text-[10px] text-muted-foreground">
                    Temporal validation parameters
                  </h3>
                  <Slider
                    label="Violation frames (of last 10)"
                    value={z.frameThreshold}
                    min={4}
                    max={10}
                    step={1}
                    suffix="/10"
                    onChange={(v) => update(z.id, { frameThreshold: v })}
                  />
                  <Slider
                    label="Minimum dwell in zone"
                    value={z.dwellSeconds}
                    min={1}
                    max={10}
                    step={1}
                    suffix=" s"
                    onChange={(v) => update(z.id, { dwellSeconds: v })}
                  />
                  <Slider
                    label="Confidence threshold"
                    value={Math.round(z.confidence * 100)}
                    min={40}
                    max={95}
                    step={1}
                    suffix="%"
                    onChange={(v) => update(z.id, { confidence: v / 100 })}
                  />
                </div>
              </div>
            </section>
          ))}
        </div>
      )}

      {/* Custom Zone Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-background/80 p-4 backdrop-blur">
          <div className="w-full max-w-lg rounded-lg border border-border panel-surface p-6 shadow-xl">
            <div className="flex items-center justify-between pb-4 border-b border-border">
              <div className="flex items-center gap-2">
                <ShieldAlert className="size-5 text-primary" />
                <h2 className="display-title text-base">Add New Safety Zone</h2>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="rounded p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <form onSubmit={handleAddZone} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Zone Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Chemical Storage Bay 4"
                  value={newZoneName}
                  onChange={(e) => setNewZoneName(e.target.value)}
                  className="w-full rounded border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1">Zone Environment Kind</label>
                <select
                  value={newZoneKind}
                  onChange={(e) => setNewZoneKind(e.target.value)}
                  className="w-full rounded border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                >
                  <option value="General plant">General plant</option>
                  <option value="Construction">Construction</option>
                  <option value="Work at height">Work at height</option>
                  <option value="Restricted machinery">Restricted machinery</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-2">Required Safety Items</label>
                <div className="grid grid-cols-2 gap-2">
                  {ppeKeys.map((k) => (
                    <label key={k} className="flex items-center gap-2 text-xs cursor-pointer">
                      <input
                        type="checkbox"
                        checked={newRequired[k]}
                        onChange={(e) => setNewRequired({ ...newRequired, [k]: e.target.checked })}
                        className="rounded border-border text-primary focus:ring-0"
                      />
                      <span>{PPE_LABELS[k]}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-3 pt-2 border-t border-border">
                <Slider
                  label="Violation Frames Threshold"
                  value={newFrameThreshold}
                  min={4}
                  max={10}
                  step={1}
                  suffix="/10"
                  onChange={setNewFrameThreshold}
                />
                <Slider
                  label="Minimum Dwell Seconds"
                  value={newDwellSeconds}
                  min={1}
                  max={10}
                  step={1}
                  suffix=" s"
                  onChange={setNewDwellSeconds}
                />
                <Slider
                  label="Confidence Floor"
                  value={Math.round(newConfidence * 100)}
                  min={40}
                  max={95}
                  step={1}
                  suffix="%"
                  onChange={(v) => setNewConfidence(v / 100)}
                />
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="rounded border border-border px-4 py-2 text-xs text-muted-foreground hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-primary px-4 py-2 text-xs text-primary-foreground hover:bg-primary/90"
                >
                  Save Safety Zone
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix: string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block">
      <span className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground text-xs">{label}</span>
        <span className="telemetry text-xs text-primary">
          {value}
          {suffix}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-muted accent-[var(--primary)]"
      />
    </label>
  );
}
