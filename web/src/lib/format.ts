export const MODEL_LABEL: Record<string, string> = {
  A: "A · accelerometer",
  B: "B · + gyroscope",
  C: "C · + time of day",
  "A+time": "accelerometer + time",
  "C+location": "C + location",
};
export const MODEL_SERIES: Record<string, string> = {
  A: "var(--series-a)",
  B: "var(--series-b)",
  C: "var(--series-c)",
  "A+time": "var(--series-d)",
  "C+location": "var(--series-e)",
};
export const DETECTOR_LABEL: Record<string, string> = {
  knn: "k-nearest neighbours",
  iforest: "Isolation forest",
  gauss: "Gaussian (Mahalanobis)",
};
export const MODALITY_LABEL: Record<string, string> = {
  acc: "Accelerometer",
  gyro: "Gyroscope",
  time: "Time of day",
  location: "Location",
};
export const ACTIVITY_LABEL: Record<string, string> = {
  LYING_DOWN: "lying down",
  SITTING: "sitting",
  OR_standing: "standing",
  FIX_walking: "walking",
  FIX_running: "running",
  BICYCLING: "bicycling",
};
export const KIND_LABEL: Record<number, string> = {
  0: "normal",
  1: "novel activity",
  2: "off schedule",
  [-1]: "undetermined",
};

export function num(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return v.toFixed(digits);
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${(v * 100).toFixed(digits)}%`;
}

export function signed(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const s = v.toFixed(digits);
  return v > 0 ? `+${s}` : s.replace("-", "−");
}

export function pval(p: number | null | undefined): string {
  if (p === null || p === undefined) return "–";
  if (p < 0.001) return "< 0.001";
  return p.toFixed(3);
}

export function shortId(uuid: string): string {
  return uuid.slice(0, 8);
}

export function cell(v: unknown): string {
  if (v === null || v === undefined) return "–";
  if (typeof v === "boolean") return v ? "yes" : "";
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toLocaleString("en");
    return Math.abs(v) < 100 ? v.toFixed(3) : v.toLocaleString("en", { maximumFractionDigits: 1 });
  }
  return String(v);
}
