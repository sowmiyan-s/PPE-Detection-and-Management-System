import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState, useEffect } from "react";
import { Download, Search, Image as ImageIcon, X } from "lucide-react";

import { AppShell, PageHeader } from "@/components/app-shell";
import { ppeLabel, formatTime, type ViolationEvent } from "@/lib/mock-data";

export const Route = createFileRoute("/events")({
  head: () => ({
    meta: [
      { title: "Event History & Proof of Evidence — EdgeVision" },
      {
        name: "description",
        content:
          "Searchable audit trail of violation events, worker tracking IDs, and recorded image proof of evidence.",
      },
    ],
  }),
  component: EventsPage,
});

export function EventsPage() {
  const [q, setQ] = useState("");
  const [type, setType] = useState("all");
  const [zone, setZone] = useState("all");
  const [eventList, setEventList] = useState<ViolationEvent[]>([]);
  const [zoneList, setZoneList] = useState<{ id: string; name: string }[]>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      fetch("/api/violations").then((res) => (res.ok ? res.json() : [])),
      fetch("/api/zones").then((res) => (res.ok ? res.json() : { db_zones: [] })),
    ]).then(([violationsRes, zonesRes]) => {
      if (violationsRes.status === "fulfilled" && Array.isArray(violationsRes.value)) {
        setEventList(violationsRes.value);
      }
      if (zonesRes.status === "fulfilled") {
        const data = zonesRes.value;
        setZoneList(data.db_zones || []);
      }
      setLoading(false);
    });
  }, []);

  const types = useMemo(() => Array.from(new Set(eventList.map((v) => v.type).filter(Boolean))), [eventList]);

  const rows = useMemo(
    () =>
      eventList.filter(
        (v) =>
          (type === "all" || v.type === type) &&
          (zone === "all" || v.zoneId === zone) &&
          (q === "" ||
            `${v.id} ${v.workerId} ${v.type} ${v.zoneId}`
              .toLowerCase()
              .includes(q.toLowerCase())),
      ),
    [q, type, zone, eventList],
  );

  return (
    <AppShell>
      <PageHeader
        title="Event History & Proof of Evidence"
        subtitle="Full audit trail of AI pipeline detection events, complete with recorded frame evidence snapshots."
        actions={
          <button className="display-title inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-[11px] text-primary-foreground">
            <Download className="size-3.5" /> Export Audit CSV
          </button>
        }
      />

      <div className="mb-3 grid gap-2 rounded panel-surface p-3 sm:grid-cols-[1fr_auto_auto]">
        <label className="relative flex items-center">
          <Search className="absolute left-3 size-4 text-muted-foreground" />
          <span className="sr-only">Search events</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search worker ID, event ID, violation type…"
            className="telemetry w-full rounded border border-input bg-background/60 py-2 pl-9 pr-3 text-sm outline-none focus:border-primary"
          />
        </label>
        <select
          aria-label="Filter by violation type"
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="telemetry rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
        >
          <option value="all">All violation types</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by zone"
          value={zone}
          onChange={(e) => setZone(e.target.value)}
          className="telemetry rounded border border-input bg-background/60 px-3 py-2 text-sm outline-none focus:border-primary"
        >
          <option value="all">All zones</option>
          {zoneList.map((z) => (
            <option key={z.id} value={z.id}>
              {z.name}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded panel-surface">
        <table className="w-full min-w-[950px] text-sm">
          <thead>
            <tr className="display-title border-b border-border text-left text-[10px] text-muted-foreground">
              <th className="px-3 py-2.5">Event ID</th>
              <th className="px-3 py-2.5">Evidence</th>
              <th className="px-3 py-2.5">Worker</th>
              <th className="px-3 py-2.5">Violation</th>
              <th className="px-3 py-2.5">Zone</th>
              <th className="px-3 py-2.5">Camera</th>
              <th className="px-3 py-2.5">Conf.</th>
              <th className="px-3 py-2.5">Timestamp</th>
              <th className="px-3 py-2.5">Status</th>
              <th className="px-3 py-2.5">Model</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={10} className="px-3 py-8 text-center text-sm text-muted-foreground animate-pulse">
                  Loading event history from database...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-3 py-8 text-center text-sm text-muted-foreground">
                  No detection events recorded matching the current filters.
                </td>
              </tr>
            ) : (
              rows.map((v) => (
                <tr key={v.id} className="hover:bg-accent/40">
                  <td className="telemetry px-3 py-2.5 text-xs text-primary font-semibold">{v.id}</td>
                  <td className="px-3 py-2.5">
                    {v.imagePath ? (
                      <button
                        onClick={() => setSelectedImage(v.imagePath!)}
                        className="group flex items-center gap-1.5 rounded border border-primary/40 bg-primary/10 px-2 py-1 text-[11px] text-primary transition-colors hover:bg-primary/20"
                      >
                        <ImageIcon className="size-3.5" />
                        <span>View Proof</span>
                      </button>
                    ) : (
                      <span className="text-[11px] text-muted-foreground italic">No snapshot</span>
                    )}
                  </td>
                  <td className="telemetry px-3 py-2.5 text-xs font-medium">{v.workerId}</td>
                  <td className="px-3 py-2.5 text-xs">{v.type}</td>
                  <td className="px-3 py-2.5 text-xs text-muted-foreground">{v.zoneId}</td>
                  <td className="px-3 py-2.5 text-xs text-muted-foreground">{v.cameraId}</td>
                  <td className="telemetry px-3 py-2.5 text-xs font-mono">{(v.confidence * 100).toFixed(0)}%</td>
                  <td className="telemetry px-3 py-2.5 text-xs text-muted-foreground">
                    {formatTime(v.timestamp)}
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={`display-title rounded-sm px-2 py-0.5 text-[10px] ${
                        v.status === "open"
                          ? "bg-destructive/15 text-destructive"
                          : "bg-success/15 text-success"
                      }`}
                    >
                      {v.status}
                    </span>
                  </td>
                  <td className="telemetry px-3 py-2.5 text-[11px] text-muted-foreground">
                    {v.modelVersion}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Proof of Evidence Image Lightbox Modal */}
      {selectedImage && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-background/85 p-4 backdrop-blur">
          <div className="w-full max-w-3xl overflow-hidden rounded-lg border border-border panel-surface p-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-border mb-3">
              <div className="flex items-center gap-2">
                <ImageIcon className="size-4 text-primary" />
                <h3 className="display-title text-sm">Proof of Evidence — Frame Snapshot</h3>
              </div>
              <button
                onClick={() => setSelectedImage(null)}
                className="rounded p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="relative aspect-video bg-black rounded overflow-hidden flex items-center justify-center">
              <img
                src={selectedImage}
                alt="Proof of Evidence Snapshot"
                className="size-full object-contain"
              />
            </div>
            <div className="mt-3 flex justify-end">
              <button
                onClick={() => setSelectedImage(null)}
                className="rounded bg-muted px-4 py-1.5 text-xs text-foreground hover:bg-muted/80"
              >
                Close Evidence Viewer
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
