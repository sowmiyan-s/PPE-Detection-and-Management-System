import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";

import { AppShell, PageHeader } from "@/components/app-shell";
import { formatTime, type Worker, type ViolationEvent } from "@/lib/mock-data";

export const Route = createFileRoute("/compliance")({
  head: () => ({
    meta: [
      { title: "Worker Compliance — EdgeVision Safety Scorecards" },
      {
        name: "description",
        content:
          "Per-worker PPE compliance scores, shift and zone assignment, incident counts and recent violation history from tracked worker IDs.",
      },
    ],
  }),
  component: CompliancePage,
});

function Ring({ value }: { value: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const tone = value >= 90 ? "var(--success)" : value >= 80 ? "var(--primary)" : "var(--destructive)";
  return (
    <svg viewBox="0 0 130 130" className="size-36">
      <circle cx="65" cy="65" r={r} fill="none" stroke="var(--border)" strokeWidth="12" />
      <circle
        cx="65"
        cy="65"
        r={r}
        fill="none"
        stroke={tone}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={`${(value / 100) * c} ${c}`}
        transform="rotate(-90 65 65)"
      />
      <text
        x="65"
        y="71"
        textAnchor="middle"
        fill="var(--foreground)"
        style={{ font: "600 26px var(--font-mono)" }}
      >
        {value}%
      </text>
    </svg>
  );
}

function CompliancePage() {
  const [workerList, setWorkerList] = useState<Worker[]>([]);
  const [violations, setViolations] = useState<ViolationEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      fetch("/api/workers").then((res) => (res.ok ? res.json() : [])),
      fetch("/api/violations").then((res) => (res.ok ? res.json() : [])),
    ]).then(([workersRes, violationsRes]) => {
      if (workersRes.status === "fulfilled" && Array.isArray(workersRes.value)) {
        setWorkerList(workersRes.value);
        if (workersRes.value.length > 0) {
          setSelectedId(workersRes.value[0].id);
        }
      }
      if (violationsRes.status === "fulfilled" && Array.isArray(violationsRes.value)) {
        setViolations(violationsRes.value);
      }
      setLoading(false);
    });
  }, []);

  const selected = workerList.find((w) => w.id === selectedId) || workerList[0];
  const incidents = selected ? violations.filter((v) => v.workerId === selected.id) : [];

  return (
    <AppShell>
      <PageHeader
        title="Worker Compliance & Safety Scorecards"
        subtitle="Compliance scores derived from tracked worker IDs, zone dwell time and confirmed PPE violations."
      />

      {loading ? (
        <div className="rounded panel-surface p-12 text-center text-muted-foreground animate-pulse">
          Loading worker compliance data from database...
        </div>
      ) : workerList.length === 0 ? (
        <div className="rounded panel-surface p-12 text-center text-muted-foreground">
          <p className="text-sm">No worker tracking data yet.</p>
          <p className="text-xs mt-1">Worker compliance scores will appear as the AI pipeline detects and tracks workers.</p>
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr]">
          <div className="overflow-x-auto rounded panel-surface">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="display-title border-b border-border text-left text-[10px] text-muted-foreground">
                  <th className="px-3 py-2.5">Worker</th>
                  <th className="px-3 py-2.5">Crew</th>
                  <th className="px-3 py-2.5">Primary zone</th>
                  <th className="px-3 py-2.5">Incidents</th>
                  <th className="px-3 py-2.5">Compliance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {workerList.map((w) => (
                  <tr
                    key={w.id}
                    onClick={() => setSelectedId(w.id)}
                    className={`cursor-pointer hover:bg-accent/40 ${
                      w.id === selected?.id ? "bg-accent/60" : ""
                    }`}
                  >
                    <td className="px-3 py-2.5">
                      <div className="font-medium">{w.name}</div>
                      <div className="telemetry text-[11px] text-muted-foreground">{w.id}</div>
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">{w.crew}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{w.primaryZone}</td>
                    <td className="telemetry px-3 py-2.5">{w.incidents}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                          <div
                            className={`h-full rounded-full ${
                              w.compliance >= 90
                                ? "bg-success"
                                : w.compliance >= 80
                                  ? "bg-primary"
                                  : "bg-destructive"
                            }`}
                            style={{ width: `${w.compliance}%` }}
                          />
                        </div>
                        <span className="telemetry text-xs">{w.compliance}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selected && (
            <aside className="rounded panel-surface p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="display-title text-lg">{selected.name}</h2>
                  <p className="telemetry text-[11px] text-muted-foreground">
                    {selected.id} · {selected.crew}
                  </p>
                </div>
              </div>

              <div className="mt-2 grid place-items-center">
                <Ring value={selected.compliance} />
              </div>

              <dl className="telemetry mt-2 grid grid-cols-2 gap-2 text-xs">
                {[
                  ["Shift", selected.shift],
                  ["Primary zone", selected.primaryZone],
                  ["Hours tracked", `${selected.hoursTracked} h`],
                  ["Incidents", String(selected.incidents)],
                ].map(([k, v]) => (
                  <div key={k} className="rounded border border-border bg-background/40 p-2.5">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="mt-1 text-foreground">{v}</dd>
                  </div>
                ))}
              </dl>

              <h3 className="display-title mt-4 text-xs text-muted-foreground">Recent incident log</h3>
              <ul className="mt-2 space-y-2">
                {incidents.length === 0 ? (
                  <li className="text-sm text-muted-foreground">No recorded incidents for this worker.</li>
                ) : (
                  incidents.map((i) => (
                    <li key={i.id} className="rounded border border-border bg-background/40 p-2.5">
                      <div className="text-sm">{i.type}</div>
                      <div className="telemetry mt-0.5 text-[11px] text-muted-foreground">
                        {i.id} · {i.zoneId} · {formatTime(i.timestamp)}
                      </div>
                    </li>
                  ))
                )}
              </ul>
            </aside>
          )}
        </div>
      )}
    </AppShell>
  );
}
