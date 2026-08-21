import { createFileRoute } from "@tanstack/react-router";
import React, { useState, useEffect, useMemo, useRef } from "react";
import { Plus, X, ShieldAlert, Loader2, Trash2, Edit2, CheckCircle2 } from "lucide-react";

import { AppShell, PageHeader } from "@/components/app-shell";
import { ConfirmModal } from "@/components/confirm-modal";
import { PPE_LABELS, zoneLabel, type PpeKey, type Zone } from "@/lib/mock-data";
import { useSessionFetch, invalidateSessionCache } from "@/hooks/use-session-fetch";
import { useToast } from "@/lib/toast-context";
import { useAppData } from "@/lib/data-context";

export const Route = createFileRoute("/zones")({
  head: () => ({
    meta: [
      { title: "Zone Configuration — Cerberus AI" },
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

// Only these positive PPE items supported by the model should be configurable as zone rules by the user
const CONFIGURABLE_PPE: PpeKey[] = [
  "helmet",
  "vest",
  "boots",
  "glasses",
  "gloves",
  "mask",
  "earmuffs",
];

const defaultRequired: Record<PpeKey, boolean> = {
  person: false,
  helmet: true,
  "no-helmet": false,
  vest: true,
  "no-vest": false,
  boots: true,
  "no-boots": false,
  glasses: false,
  "no-glasses": false,
  gloves: false,
  "no-gloves": false,
  goggles: false,
  mask: false,
  "no-mask": false,
  earmuffs: false,
  "no-earmuffs": false,
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
    kind: "",
    description: "",
    required,
    frameThreshold: Number(apiZone.frame_threshold ?? apiZone.frameThreshold ?? 8),
    dwellSeconds: Number(apiZone.dwell_seconds ?? apiZone.dwellSeconds ?? 2),
    confidence: Number(apiZone.confidence ?? apiZone.confidence_threshold ?? 0.60),
  };
}

function ZonesPage() {
  const { showToast } = useToast();
  const { refetchAll } = useAppData();
  const [showAddModal, setShowAddModal] = useState(false);
  const [savingZoneId, setSavingZoneId] = useState<string | null>(null);
  const [submittingAddZone, setSubmittingAddZone] = useState(false);
  const { data: apiData, loading, refetch: fetchZones } = useSessionFetch<any>("/api/zones", { zones: [], db_zones: [] });

  const initialConfig = useMemo<Zone[]>(() => {
    const dbZones = apiData.db_zones || [];
    const ruleZones = apiData.zones || [];
    if (dbZones.length > 0) return dbZones.map(apiZoneToLocal);
    if (ruleZones.length > 0) return ruleZones.map(apiZoneToLocal);
    return [];
  }, [apiData]);

  const [zones, setZones] = useState<Zone[]>([]);
  const hasInitializedRef = useRef(false);

  useEffect(() => {
    if (initialConfig.length > 0) {
      if (!hasInitializedRef.current) {
        setZones(initialConfig);
        hasInitializedRef.current = true;
      } else {
        // Smooth background sync: merge ALL server fields without clobbering in-flight UI edits
        setZones((prev) => {
          if (prev.length === 0) return initialConfig;
          const serverMap = new Map(initialConfig.map((z) => [z.id, z]));
          // Add any new zones from server that are not in prev
          const prevIds = new Set(prev.map((z) => z.id));
          const newFromServer = initialConfig.filter((z) => !prevIds.has(z.id));
          const merged = prev.map((z) => {
            const incoming = serverMap.get(z.id);
            if (!incoming) return z;
            return {
              ...z,
              name: incoming.name,
              kind: incoming.kind,
              description: incoming.description,
              required: incoming.required,
              frameThreshold: incoming.frameThreshold,
              dwellSeconds: incoming.dwellSeconds,
              confidence: incoming.confidence,
            };
          });
          return [...merged, ...newFromServer];
        });
      }
    }
  }, [initialConfig]);

  const config = zones.length > 0 ? zones : initialConfig;

  // New Zone Form State
  const [newZoneName, setNewZoneName] = useState("");
  const [newRequired, setNewRequired] = useState<Record<PpeKey, boolean>>({ ...defaultRequired });
  const [newFrameThreshold, setNewFrameThreshold] = useState(8);
  const [newDwellSeconds, setNewDwellSeconds] = useState(2);
  const [newConfidence, setNewConfidence] = useState(0.60);

  const update = (id: string, patch: Partial<Zone>) => {
    setZones((prev) => {
      const base = prev.length > 0 ? prev : initialConfig;
      const updated = base.map((z) => (z.id === id ? { ...z, ...patch } : z));
      return updated;
    });
  };

  const handleAddZone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newZoneName.trim()) return;

    setSubmittingAddZone(true);
    const name = newZoneName.trim();
    const requiredPpe = CONFIGURABLE_PPE.filter((k) => newRequired[k]);
    const newZone: Zone = {
      id: name,
      name: name,
      kind: "",
      description: "",
      required: { ...newRequired },
      frameThreshold: newFrameThreshold,
      dwellSeconds: newDwellSeconds,
      confidence: newConfidence,
    };

    try {
      const res = await fetch("/api/zones", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: newZone.id,
          name: newZone.name,
          description: "",
          required_ppe: requiredPpe,
          frame_threshold: newZone.frameThreshold,
          dwell_seconds: newZone.dwellSeconds,
          confidence: newZone.confidence,
        }),
      });
      if (!res.ok) throw new Error("Failed to create zone in database");

      setZones((prev) => [...(prev.length > 0 ? prev : initialConfig), newZone]);
      invalidateSessionCache("/api/zones");
      fetchZones(false);
      refetchAll();
      setShowAddModal(false);
      setNewZoneName("");
      setNewRequired({ ...defaultRequired });
      showToast(`Safety zone '${newZone.name}' created and applied to database`);
    } catch (err) {
      console.error("Failed to sync new zone to backend", err);
      showToast("Failed to create safety zone in database");
    } finally {
      setSubmittingAddZone(false);
    }
  };

  const handleSaveZone = async (targetZone: Zone) => {
    setSavingZoneId(targetZone.id);
    const requiredPpe = CONFIGURABLE_PPE.filter((k) => targetZone.required[k]);
    const payload = {
      id: targetZone.id,
      name: targetZone.name,
      description: "",
      required_ppe: requiredPpe,
      frame_threshold: targetZone.frameThreshold,
      dwell_seconds: targetZone.dwellSeconds,
      confidence: targetZone.confidence,
    };

    try {
      const res = await fetch("/api/zones", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to save zone settings to database");

      // Update state in place immediately
      setZones((prev) =>
        prev.map((z) => (z.id === targetZone.id ? { ...z, ...targetZone } : z))
      );

      invalidateSessionCache("/api/zones");
      fetchZones(false);
      refetchAll();
      showToast(`Zone '${zoneLabel(targetZone.name || targetZone.id)}' settings updated & applied to database`);
    } catch (err) {
      console.error("Failed to save zone settings", err);
      showToast("Failed to save zone settings to database");
    } finally {
      setSavingZoneId(null);
    }
  };

  const [deletingZoneId, setDeletingZoneId] = useState<string | null>(null);
  const [confirmDeleteZone, setConfirmDeleteZone] = useState<Zone | null>(null);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);
  const [submittingEditZone, setSubmittingEditZone] = useState(false);

  const executeDeleteZone = async () => {
    if (!confirmDeleteZone) return;
    const targetId = confirmDeleteZone.id;
    setDeletingZoneId(targetId);
    try {
      const res = await fetch(`/api/zones/${encodeURIComponent(targetId)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete zone from database");

      setZones((prev) => prev.filter((z) => z.id !== targetId));
      invalidateSessionCache("/api/zones");
      fetchZones(false);
      refetchAll();
      showToast(`Safety zone '${zoneLabel(targetId)}' deleted from database`);
    } catch (err) {
      console.error("Failed to delete zone", err);
      showToast("Failed to delete safety zone from database");
    } finally {
      setDeletingZoneId(null);
      setConfirmDeleteZone(null);
    }
  };

  const handleSaveEditZone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingZone || !editingZone.name.trim()) return;

    setSubmittingEditZone(true);
    const requiredPpe = CONFIGURABLE_PPE.filter((k) => editingZone.required[k]);
    const payload = {
      id: editingZone.id,
      name: editingZone.name.trim(),
      description: "",
      required_ppe: requiredPpe,
      frame_threshold: editingZone.frameThreshold,
      dwell_seconds: editingZone.dwellSeconds,
      confidence: editingZone.confidence,
    };

    try {
      const res = await fetch("/api/zones", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to update zone in database");

      setZones((prev) =>
        prev.map((z) => (z.id === editingZone.id ? { ...z, ...editingZone } : z))
      );
      invalidateSessionCache("/api/zones");
      fetchZones(false);
      refetchAll();
      setEditingZone(null);
      showToast(`Safety zone '${editingZone.name}' updated & applied to database`);
    } catch (err) {
      console.error("Failed to update zone", err);
      showToast("Failed to update safety zone in database");
    } finally {
      setSubmittingEditZone(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Zone Configuration & Custom Rules"
        actions={[
          <button
            key="add-zone"
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded border border-primary bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90 cursor-pointer shadow-sm"
          >
            <Plus className="size-4" />
            <span>Add Safety Zone</span>
          </button>,
        ]}
      />

      {loading && config.length === 0 ? (
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
            <section key={z.id} className="relative overflow-hidden rounded panel-surface border border-border/80 shadow-md">
              <div className="hazard-stripe absolute inset-x-0 top-0 h-1 opacity-60" />
              <div className="px-4 pb-4 pt-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="display-title text-lg uppercase">{zoneLabel(z.name || z.id)}</h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="display-title rounded-sm bg-accent px-2 py-0.5 text-[10px] text-accent-foreground font-semibold">
                      {CONFIGURABLE_PPE.filter((k) => z.required[k]).length} rules active
                    </span>
                    <button
                      onClick={() => setEditingZone({ ...z })}
                      title="Edit Zone Settings & Rules"
                      className="rounded border border-primary/30 bg-primary/10 p-1.5 text-primary hover:bg-primary hover:text-primary-foreground transition-colors cursor-pointer"
                    >
                      <Edit2 className="size-3.5" />
                    </button>
                    <button
                      onClick={() => setConfirmDeleteZone(z)}
                      disabled={deletingZoneId === z.id}
                      title="Delete Safety Zone"
                      className="rounded border border-destructive/30 bg-destructive/10 p-1.5 text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      {deletingZoneId === z.id ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />}
                    </button>
                  </div>
                </div>

                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  {CONFIGURABLE_PPE.map((k) => (
                    <label
                      key={k}
                      className="flex cursor-pointer items-center justify-between gap-3 rounded border border-border bg-background/40 px-3 py-2 transition-colors hover:bg-background/70"
                    >
                      <span className="text-sm">{PPE_LABELS[k]}</span>
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={!!z.required[k]}
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
                  <h3 className="display-title text-[10px] text-muted-foreground uppercase font-bold tracking-wider">
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

                <div className="mt-4 flex items-center justify-end border-t border-border pt-3">
                  <button
                    type="button"
                    disabled={savingZoneId === z.id}
                    onClick={() => handleSaveZone(z)}
                    className="flex items-center gap-1.5 rounded bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
                  >
                    {savingZoneId === z.id ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
                    <span>{savingZoneId === z.id ? "Saving to Database..." : "Save Zone Settings"}</span>
                  </button>
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
                <h2 className="display-title text-base font-bold">Add New Safety Zone</h2>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="rounded p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="size-5" />
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
                <label className="block text-xs text-muted-foreground mb-2 font-semibold">Required Safety Items</label>
                <div className="grid grid-cols-2 gap-2">
                  {CONFIGURABLE_PPE.map((k) => (
                    <label key={k} className="flex items-center gap-2 text-xs cursor-pointer rounded border border-border/60 p-2 hover:bg-muted/40">
                      <input
                        type="checkbox"
                        checked={newRequired[k]}
                        onChange={(e) => setNewRequired({ ...newRequired, [k]: e.target.checked })}
                        className="rounded border-border text-primary focus:ring-0 size-3.5"
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
                  className="rounded border border-border px-4 py-2 text-xs text-muted-foreground hover:bg-muted cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingAddZone}
                  className="flex items-center gap-1.5 rounded bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 cursor-pointer"
                >
                  {submittingAddZone ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
                  <span>{submittingAddZone ? "Saving to DB..." : "Create & Save Zone"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Zone Themed Modal */}
      {editingZone && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="relative w-full max-w-lg overflow-hidden rounded-lg border border-border panel-surface shadow-2xl">
            <div className="hazard-stripe h-1.5 w-full bg-primary" />
            <div className="flex items-center justify-between border-b border-border/80 px-5 py-4 bg-background/50">
              <div className="flex items-center gap-2">
                <Edit2 className="size-4 text-primary" />
                <h3 className="display-title text-base font-bold">Edit Safety Zone: {editingZone.name}</h3>
              </div>
              <button
                type="button"
                onClick={() => setEditingZone(null)}
                className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors cursor-pointer"
              >
                <X className="size-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEditZone} className="p-5 space-y-4">
              <div>
                <label className="telemetry text-xs text-muted-foreground block mb-1">Zone Name</label>
                <input
                  type="text"
                  required
                  value={editingZone.name}
                  onChange={(e) => setEditingZone({ ...editingZone, name: e.target.value })}
                  className="telemetry w-full rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
                />
              </div>


              <div>
                <label className="telemetry text-xs text-muted-foreground block mb-2 font-semibold">Enforced PPE Safety Rules</label>
                <div className="grid gap-2 sm:grid-cols-2 max-h-48 overflow-y-auto pr-1">
                  {CONFIGURABLE_PPE.map((k) => (
                    <label
                      key={k}
                      className="flex cursor-pointer items-center justify-between gap-3 rounded border border-border bg-background/40 px-3 py-2 text-xs"
                    >
                      <span>{PPE_LABELS[k]}</span>
                      <input
                        type="checkbox"
                        checked={!!editingZone.required[k]}
                        onChange={(e) =>
                          setEditingZone({
                            ...editingZone,
                            required: { ...editingZone.required, [k]: e.target.checked },
                          })
                        }
                        className="rounded border-border bg-background text-primary focus:ring-primary size-4"
                      />
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-3 pt-2 border-t border-border/80">
                <Slider
                  label="Violation Frames Threshold"
                  value={editingZone.frameThreshold}
                  min={4}
                  max={10}
                  step={1}
                  suffix="/10"
                  onChange={(v) => setEditingZone({ ...editingZone, frameThreshold: v })}
                />
                <Slider
                  label="Minimum Dwell Seconds"
                  value={editingZone.dwellSeconds}
                  min={1}
                  max={10}
                  step={1}
                  suffix=" s"
                  onChange={(v) => setEditingZone({ ...editingZone, dwellSeconds: v })}
                />
                <Slider
                  label="Confidence Floor"
                  value={Math.round(editingZone.confidence * 100)}
                  min={40}
                  max={95}
                  step={1}
                  suffix="%"
                  onChange={(v) => setEditingZone({ ...editingZone, confidence: v / 100 })}
                />
              </div>

              <div className="flex justify-end gap-2.5 pt-4 border-t border-border/80">
                <button
                  type="button"
                  onClick={() => setEditingZone(null)}
                  className="rounded border border-border px-4 py-2 text-xs text-muted-foreground hover:bg-muted cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingEditZone}
                  className="flex items-center gap-1.5 rounded bg-primary px-4 py-2 text-xs font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 cursor-pointer"
                >
                  {submittingEditZone ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
                  <span>{submittingEditZone ? "Saving to Database..." : "Update Zone Rules"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Themed Confirm Modal for Deleting Zone */}
      <ConfirmModal
        isOpen={!!confirmDeleteZone}
        title={`Delete Zone: ${confirmDeleteZone ? zoneLabel(confirmDeleteZone.name || confirmDeleteZone.id) : ""}`}
        message={`Are you sure you want to delete safety zone '${confirmDeleteZone?.name || confirmDeleteZone?.id}'? This will purge its rules from SQL database.`}
        confirmText="Delete Safety Zone"
        cancelText="Keep Zone"
        variant="danger"
        isLoading={deletingZoneId !== null}
        onConfirm={executeDeleteZone}
        onCancel={() => setConfirmDeleteZone(null)}
      />
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
        <span className="telemetry text-xs text-primary font-bold">
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
