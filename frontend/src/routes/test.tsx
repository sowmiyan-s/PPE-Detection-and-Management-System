import { createFileRoute } from "@tanstack/react-router";
import React, { useState, useRef } from "react";
import {
  Upload,
  FlaskConical,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Image as ImageIcon,
  Video as VideoIcon,
  RotateCcw,
  Sparkles,
  Zap,
  HardHat,
  Eye,
  Clock,
  Layers,
  ChevronRight
} from "lucide-react";

import { AppShell, PageHeader } from "@/components/app-shell";
import { useSessionFetch } from "@/hooks/use-session-fetch";
import { useToast } from "@/lib/toast-context";

export const Route = createFileRoute("/test")({
  head: () => ({
    meta: [
      { title: "Model Test Sandbox — Cerberus AI" },
      {
        name: "description",
        content:
          "Upload custom images or video files to run real-time YOLO model inference and evaluate per-zone safety compliance.",
      },
    ],
  }),
  component: ModelTestPage,
});

function ModelTestPage() {
  const { showToast } = useToast();
  const [selectedZone, setSelectedZone] = useState<string>("General Plant Floor");
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [result, setResult] = useState<any | null>(null);
  const [activeKeyframeIdx, setActiveKeyframeIdx] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<"annotated" | "original">("annotated");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: zoneData } = useSessionFetch<any>("/api/zones", { db_zones: [] });
  const availableZones = zoneData?.db_zones || [
    { id: "General Plant Floor", name: "General Plant Floor" },
    { id: "Construction Area", name: "Construction Area" },
    { id: "Work at Height Platform", name: "Work at Height Platform" },
    { id: "Restricted Machinery Zone", name: "Restricted Machinery Zone" },
    { id: "Hazardous Chemical Area", name: "Hazardous Chemical Area" }
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      processFileSelection(selected);
    }
  };

  const processFileSelection = (selected: File) => {
    setFile(selected);
    setResult(null);
    setActiveKeyframeIdx(0);
    const url = URL.createObjectURL(selected);
    setFilePreview(url);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) {
      processFileSelection(dropped);
    }
  };

  const handleRunInference = async () => {
    if (!file) {
      showToast("Please select an image or video file first.");
      return;
    }

    setIsProcessing(true);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("zone", selectedZone);

    try {
      const response = await fetch("/api/test/infer", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || "Inference failed");
      }

      const data = await response.json();
      setResult(data);
      showToast(
        data.type === "image"
          ? `Inference completed in ${data.inference_time_ms} ms`
          : `Video processed ${data.total_frames} frames in ${data.inference_time_ms} ms`
      );
    } catch (err: any) {
      console.error("Test inference error", err);
      showToast(err.message || "Failed to execute model inference");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setFilePreview(null);
    setResult(null);
    setActiveKeyframeIdx(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const activeWorkerStates = result
    ? result.type === "image"
      ? result.worker_states || []
      : result.keyframes?.[activeKeyframeIdx]?.worker_states || []
    : [];

  const totalWorkers = activeWorkerStates.length;
  const compliantWorkers = activeWorkerStates.filter((w: any) => w.compliant).length;
  const violationWorkers = totalWorkers - compliantWorkers;

  return (
    <AppShell>
      <PageHeader
        title="Model Test Sandbox"
        actions={[
          <button
            key="reset-btn"
            onClick={handleReset}
            disabled={!file && !result}
            className="flex items-center gap-1.5 rounded border border-border bg-panel px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground disabled:opacity-40"
          >
            <RotateCcw className="size-3.5" /> Reset Upload
          </button>,
        ]}
      />

      <div className="space-y-6">
        {/* Top Control Header Card */}
        <div className="rounded-lg border border-border panel-surface p-4 md:p-6 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="display-title text-base font-semibold flex items-center gap-2">
                <FlaskConical className="size-5 text-primary" />
                Upload Test Media & Target Safety Zone
              </h2>
              <p className="telemetry text-xs text-muted-foreground mt-0.5">
                Run single-frame or multi-frame video inference against YOLO models and per-zone rules.
              </p>
            </div>

            {/* Zone Selector & Run Action */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="telemetry text-xs text-muted-foreground font-medium">Zone Rule:</span>
                <select
                  value={selectedZone}
                  onChange={(e) => setSelectedZone(e.target.value)}
                  className="rounded border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground outline-none focus:ring-1 focus:ring-primary"
                >
                  {availableZones.map((z: any) => (
                    <option key={z.id || z.name} value={z.name || z.id}>
                      {z.name || z.id}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleRunInference}
                disabled={!file || isProcessing}
                className="flex items-center gap-2 rounded bg-primary px-4 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-40"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="size-4 animate-spin" /> Processing AI...
                  </>
                ) : (
                  <>
                    <Zap className="size-4" /> Run Inference
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Upload Dropzone */}
          {!result && (
            <div
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`group relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-all cursor-pointer ${
                file
                  ? "border-primary/60 bg-primary/5"
                  : "border-border hover:border-primary/50 hover:bg-muted/20"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,video/*"
                onChange={handleFileChange}
                className="hidden"
              />

              {file ? (
                <div className="space-y-2">
                  <div className="grid size-12 place-items-center rounded-full bg-primary/20 text-primary mx-auto">
                    {file.type.startsWith("video/") ? (
                      <VideoIcon className="size-6" />
                    ) : (
                      <ImageIcon className="size-6" />
                    )}
                  </div>
                  <div className="font-semibold text-sm text-foreground">{file.name}</div>
                  <div className="telemetry text-xs text-muted-foreground">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB · {file.type || "Media file"}
                  </div>
                  <p className="text-xs text-primary font-medium mt-2">
                    Click "Run Inference" above to evaluate compliance.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="grid size-12 place-items-center rounded-full bg-muted/40 text-muted-foreground group-hover:text-primary transition-colors mx-auto">
                    <Upload className="size-6" />
                  </div>
                  <div className="text-sm font-semibold text-foreground">
                    Drag and drop your image or video file here
                  </div>
                  <div className="telemetry text-xs text-muted-foreground">
                    Supports JPG, PNG, WEBP, MP4, AVI, MOV (Max 100MB)
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Inference Results Dashboard */}
        {result && (
          <div className="space-y-6">
            {/* Inference Telemetry Banner */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-border panel-surface p-4">
                <div className="telemetry text-xs text-muted-foreground">INFERENCE LATENCY</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-primary">
                    {result.inference_time_ms}
                  </span>
                  <span className="text-xs text-muted-foreground">ms</span>
                </div>
              </div>

              <div className="rounded-lg border border-border panel-surface p-4">
                <div className="telemetry text-xs text-muted-foreground">TRACKED WORKERS</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-foreground">
                    {totalWorkers}
                  </span>
                  <span className="text-xs text-muted-foreground">detected</span>
                </div>
              </div>

              <div className="rounded-lg border border-border panel-surface p-4">
                <div className="telemetry text-xs text-muted-foreground">COMPLIANT WORKERS</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-success">
                    {compliantWorkers}
                  </span>
                  <span className="text-xs text-muted-foreground">passed</span>
                </div>
              </div>

              <div className="rounded-lg border border-border panel-surface p-4">
                <div className="telemetry text-xs text-muted-foreground">PPE VIOLATIONS</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-bold font-mono text-destructive">
                    {violationWorkers}
                  </span>
                  <span className="text-xs text-muted-foreground">alerts</span>
                </div>
              </div>
            </div>

            {/* Split View: Media Display & Real-time Telemetry Panel */}
            <div className="grid gap-6 lg:grid-cols-3">
              {/* Left Column: Visual Overlay Preview */}
              <div className="lg:col-span-2 space-y-4">
                <div className="rounded-lg border border-border panel-surface overflow-hidden">
                  <div className="flex items-center justify-between border-b border-border bg-background/60 px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Eye className="size-4 text-primary" />
                      <span className="display-title text-sm font-semibold">AI Detection Output</span>
                    </div>

                    <div className="flex items-center gap-1 rounded bg-panel p-1 border border-border">
                      <button
                        onClick={() => setActiveTab("annotated")}
                        className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                          activeTab === "annotated"
                            ? "bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        AI Bounding Boxes
                      </button>
                      <button
                        onClick={() => setActiveTab("original")}
                        className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                          activeTab === "original"
                            ? "bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        Original Upload
                      </button>
                    </div>
                  </div>

                  <div className="relative aspect-video bg-black/90 flex items-center justify-center overflow-hidden">
                    {result.type === "image" ? (
                      <img
                        src={activeTab === "annotated" ? result.annotated_image : filePreview || ""}
                        alt="Model Output"
                        className="size-full object-contain"
                      />
                    ) : (
                      <img
                        src={
                          activeTab === "annotated"
                            ? result.keyframes?.[activeKeyframeIdx]?.image || result.keyframes?.[0]?.image
                            : filePreview || ""
                        }
                        alt="Video Keyframe"
                        className="size-full object-contain"
                      />
                    )}
                  </div>

                  {/* Video Keyframe Navigation Carousel */}
                  {result.type === "video" && result.keyframes && (
                    <div className="border-t border-border bg-background/50 p-3 space-y-2">
                      <div className="telemetry text-xs text-muted-foreground flex items-center justify-between">
                        <span>Extracted Video Keyframes ({result.keyframes.length})</span>
                        <span>
                          Keyframe {activeKeyframeIdx + 1} of {result.keyframes.length} (
                          {result.keyframes[activeKeyframeIdx]?.timestamp_sec}s)
                        </span>
                      </div>
                      <div className="flex items-center gap-2 overflow-x-auto pb-1">
                        {result.keyframes.map((kf: any, idx: number) => (
                          <button
                            key={idx}
                            onClick={() => setActiveKeyframeIdx(idx)}
                            className={`relative h-16 w-24 shrink-0 overflow-hidden rounded border transition-all ${
                              activeKeyframeIdx === idx
                                ? "border-primary ring-2 ring-primary"
                                : "border-border opacity-70 hover:opacity-100"
                            }`}
                          >
                            <img src={kf.image} alt={`Frame ${kf.frame}`} className="size-full object-cover" />
                            <span className="absolute bottom-0 inset-x-0 bg-black/75 telemetry text-[9px] text-center text-foreground py-0.5">
                              {kf.timestamp_sec}s
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Worker Compliance Cards */}
              <div className="space-y-4">
                <div className="rounded-lg border border-border panel-surface p-4 space-y-4">
                  <div className="flex items-center justify-between border-b border-border pb-3">
                    <h3 className="display-title text-sm font-semibold flex items-center gap-1.5">
                      <HardHat className="size-4 text-primary" />
                      Worker Detections & Rules
                    </h3>
                    <span className="telemetry text-xs text-muted-foreground">{selectedZone}</span>
                  </div>

                  {activeWorkerStates.length === 0 ? (
                    <div className="py-8 text-center text-muted-foreground space-y-2">
                      <CheckCircle2 className="size-8 text-muted-foreground/40 mx-auto" />
                      <p className="text-xs">No worker bounding boxes detected in this frame.</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {activeWorkerStates.map((w: any) => (
                        <div
                          key={w.worker_id}
                          className={`rounded-md border p-3 bg-background/60 transition-all ${
                            w.compliant ? "border-success/50 bg-success/5" : "border-destructive/50 bg-destructive/5"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="font-semibold text-sm text-foreground">{w.worker_id}</span>
                            <span
                              className={`telemetry text-[10px] font-bold px-2 py-0.5 rounded border ${
                                w.compliant
                                  ? "bg-success/20 text-success border-success/30"
                                  : "bg-destructive/20 text-destructive border-destructive/30"
                              }`}
                            >
                              {w.compliant ? "COMPLIANT" : "VIOLATION"}
                            </span>
                          </div>

                          {w.required_ppe && w.required_ppe.length > 0 && (
                            <div className="telemetry text-[10px] text-muted-foreground mb-2">
                              REQUIRED: {w.required_ppe.join(", ")}
                            </div>
                          )}

                          <div className="flex flex-wrap gap-1.5">
                            {w.detected_ppe?.map((p: string) => (
                              <span
                                key={p}
                                className="rounded bg-success/20 px-2 py-0.5 text-[10px] text-success border border-success/30 font-medium"
                              >
                                ✓ {p}
                              </span>
                            ))}
                            {w.missing_ppe?.map((p: string) => (
                              <span
                                key={`miss-${p}`}
                                className="flex items-center gap-1 rounded bg-destructive/20 px-2 py-0.5 text-[10px] text-destructive border border-destructive/30 font-semibold"
                              >
                                <AlertTriangle className="size-3" /> MISSING {p}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
