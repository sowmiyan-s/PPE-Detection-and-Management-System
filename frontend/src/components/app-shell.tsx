import { Link } from "@tanstack/react-router";
import { useSessionFetch } from "@/hooks/use-session-fetch";
import {
  Activity,
  Camera,
  Cpu,
  FileBarChart,
  Gauge,
  HardHat,
  History,
  LayoutDashboard,
  MonitorPlay,
  ShieldAlert,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/live", label: "Live Monitoring", icon: MonitorPlay },
  { to: "/violations", label: "Active Violations", icon: ShieldAlert },
  { to: "/events", label: "Event History", icon: History },
  { to: "/compliance", label: "Worker Compliance", icon: Users },
  { to: "/zones", label: "Zone Configuration", icon: SlidersHorizontal },
  { to: "/cameras", label: "Camera Management", icon: Camera },
  { to: "/reports", label: "Reports", icon: FileBarChart },
  { to: "/model", label: "Model Monitoring", icon: Cpu },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const { data: health } = useSessionFetch<any>("/api/health", null);

  const isActive = health?.status === "ok";
  const pipelineStatus = health 
    ? `PIPELINE ${health.pipeline_active ? "ACTIVE" : "IDLE"} · ${health.fps ? `${health.fps.toFixed(1)} FPS` : "0 FPS"}`
    : "CONNECTING...";

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
        <div className="flex items-center gap-2.5 border-b border-sidebar-border px-4 py-4">
          <div className="grid size-9 place-items-center rounded bg-primary text-primary-foreground">
            <HardHat className="size-5" />
          </div>
          <div className="leading-none">
            <div className="display-title text-lg font-semibold">EdgeVision</div>
            <div className="telemetry text-[10px] text-muted-foreground">PPE · HEIGHT SAFETY</div>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {nav.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact: to === "/" }}
              className="group flex items-center gap-2.5 rounded px-3 py-2 text-sm text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[status=active]:bg-sidebar-accent data-[status=active]:text-primary data-[status=active]:font-medium"
            >
              <Icon className="size-4 shrink-0" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>

        <div className="border-t border-sidebar-border p-3">
          <div className="telemetry flex items-center gap-2 text-[11px] text-muted-foreground">
            <Gauge className={`size-3.5 ${isActive ? "text-success" : "text-muted-foreground"}`} />
            EDGE NODE · JETSON ORIN NX
          </div>
          <div className="telemetry mt-1 text-[11px] text-muted-foreground">
            FP16 · SQLite
          </div>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-border bg-background/85 px-4 py-3 backdrop-blur md:px-6">
          <nav className="flex gap-1 overflow-x-auto md:hidden">
            {nav.map(({ to, icon: Icon, label }) => (
              <Link
                key={to}
                to={to}
                aria-label={label}
                activeOptions={{ exact: to === "/" }}
                className="grid size-9 shrink-0 place-items-center rounded bg-panel text-muted-foreground data-[status=active]:text-primary"
              >
                <Icon className="size-4" />
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-4">
            <div className="telemetry hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
              <Activity className={`size-3.5 ${isActive ? "text-success scan-pulse" : "text-muted-foreground"}`} />
              {pipelineStatus}
            </div>
            <div className="telemetry rounded border border-border bg-panel px-2.5 py-1 text-xs text-primary">
              v3.2-FP16
            </div>
          </div>
        </header>
        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle: string;
  actions?: ReactNode;
}) {
  return (
    <header className="relative mb-6 overflow-hidden rounded panel-surface">
      <div className="hazard-stripe absolute inset-y-0 left-0 w-1.5" />
      <div className="flex flex-wrap items-end justify-between gap-4 pl-6 pr-4 py-4">
        <div>
          <h1 className="display-title text-2xl font-semibold md:text-3xl">{title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className="hazard-stripe h-1 w-full opacity-40" />
    </header>
  );
}

export function StatCard({
  label,
  value,
  unit,
  hint,
  tone = "default",
  icon: Icon,
}: {
  label: string;
  value: string | number;
  unit?: string;
  hint?: string;
  tone?: "default" | "danger" | "success" | "warning";
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const toneClass =
    tone === "danger"
      ? "text-destructive"
      : tone === "success"
        ? "text-success"
        : tone === "warning"
          ? "text-primary"
          : "text-foreground";

  return (
    <div className="rounded panel-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <span className="display-title text-[11px] text-muted-foreground">{label}</span>
        {Icon ? <Icon className={`size-4 ${toneClass}`} /> : null}
      </div>
      <div className={`telemetry mt-2 text-3xl font-semibold ${toneClass}`}>
        {value}
        {unit ? <span className="ml-1 text-base text-muted-foreground">{unit}</span> : null}
      </div>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function StatusDot({ status }: { status: "online" | "degraded" | "offline" }) {
  const cls =
    status === "online"
      ? "bg-success"
      : status === "degraded"
        ? "bg-primary"
        : "bg-muted-foreground";
  return (
    <span className="telemetry inline-flex items-center gap-1.5 text-[11px] uppercase text-muted-foreground">
      <span className={`size-2 rounded-full ${cls} ${status === "online" ? "scan-pulse" : ""}`} />
      {status}
    </span>
  );
}
