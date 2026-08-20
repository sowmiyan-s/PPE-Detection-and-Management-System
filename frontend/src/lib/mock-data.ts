// Cerberus AI industrial telemetry types and utility helpers.
// All runtime data is fetched from the backend API — no hardcoded mock arrays.

export type PpeKey =
  | "person"
  | "helmet"
  | "no-helmet"
  | "vest"
  | "no-vest"
  | "boots"
  | "no-boots"
  | "glasses"
  | "no-glasses"
  | "gloves"
  | "no-gloves"
  | "goggles"
  | "mask"
  | "no-mask"
  | "earmuffs"
  | "no-earmuffs";

export const PPE_LABELS: Record<PpeKey, string> = {
  person: "Worker",
  helmet: "Safety Helmet",
  "no-helmet": "Missing Helmet",
  vest: "Reflective Vest",
  "no-vest": "Missing Vest",
  boots: "Safety Boots",
  "no-boots": "Missing Boots",
  glasses: "Safety Glasses",
  "no-glasses": "Missing Glasses",
  gloves: "Safety Gloves",
  "no-gloves": "Missing Gloves",
  goggles: "Safety Goggles",
  mask: "Face Mask",
  "no-mask": "Missing Mask",
  earmuffs: "Ear Protection",
  "no-earmuffs": "Missing Ear Protection",
};

export type CameraStatus = "online" | "degraded" | "offline";

export type Camera = {
  id: string;
  name: string;
  zoneId: string;
  resolution: string;
  targetFps: number;
  actualFps: number;
  latencyMs: number;
  status: CameraStatus;
  streamUrl: string;
};

export type Zone = {
  id: string;
  name: string;
  kind?: string | undefined;
  description?: string | undefined;
  required: Record<PpeKey, boolean>;
  frameThreshold: number; // violation frames out of last 10
  dwellSeconds: number;
  confidence: number;
};

export type ViolationEvent = {
  id: string;
  cameraId: string;
  zoneId: string;
  workerId: string;
  type: string;
  detected: string[];
  missing: string[];
  confidence: number;
  timestamp: string;
  status: string;
  acknowledged: boolean;
  modelVersion: string;
  imagePath?: string;
  imageBase64?: string;
  clip?: string;
};

export type Worker = {
  id: string;
  name: string;
  crew: string;
  shift: string;
  primaryZone: string;
  compliance: number;
  incidents: number;
  hoursTracked: number;
};

// ── Utility helpers ─────────────────────────────────────────────────────────

export const formatTime = (iso: string) => {
  if (!iso) return "—";
  try {
    let cleanStr = String(iso).trim();
    if (cleanStr.includes(" IST")) {
      cleanStr = cleanStr.replace(" IST", " GMT+0530");
    }
    // If format is "YYYY-MM-DD HH:MM:SS" without timezone specifier, treat as UTC by replacing space with 'T' and adding 'Z'
    if (/^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}/.test(cleanStr)) {
      cleanStr = cleanStr.replace(" ", "T") + "Z";
    } else if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(cleanStr)) {
      cleanStr = cleanStr + "Z";
    }
    const date = new Date(cleanStr);
    if (isNaN(date.getTime())) {
      return iso;
    }
    return date.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    }) + " IST";
  } catch {
    return iso;
  }
};

/** Look up a PPE label with fallback to raw key */
export const ppeLabel = (key: string): string =>
  PPE_LABELS[key as PpeKey] || key.replace(/_/g, " ");

export const zoneLabel = (key: string, availableZones?: Array<{ id?: string; name?: string }>): string => {
  if (!key) return "General Plant Floor";
  const k = String(key).trim();

  let zones = availableZones;
  if (!zones && typeof window !== "undefined") {
    try {
      const stored = window.sessionStorage.getItem("ev_zones");
      if (stored) {
        zones = JSON.parse(stored);
      }
    } catch (e) {
      // Ignore storage retrieval errors
    }
  }

  if (Array.isArray(zones) && zones.length > 0) {
    const match = zones.find(
      (z) => z && (z.id === k || z.name?.toLowerCase() === k.toLowerCase() || z.id?.toLowerCase() === k.toLowerCase())
    );
    if (match && match.name) {
      return match.name;
    }
  }

  return k
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

export function getEvidenceUrl(path: string | undefined): string {
  if (!path) return "";
  if (path.startsWith("data:")) return path; // base64
  if (path.startsWith("http:") || path.startsWith("https:")) return path;
  
  // Resolve relative /api/evidence paths to the absolute backend URL to bypass TanStack dev server proxy
  if (typeof window !== "undefined") {
    const backendHost = window.location.hostname;
    return `http://${backendHost}:8000${path}`;
  }
  return path;
}
