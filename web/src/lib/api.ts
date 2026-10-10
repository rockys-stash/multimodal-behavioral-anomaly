import { useCallback, useEffect, useRef, useState } from "react";

/* ---------- types mirrored from the API (src/behavlab/api.py) ---------- */
export interface Provenance {
  experiment: string;
  run_id: string;
  commit: string;
  dirty: boolean;
  created_at: string;
  runtime_seconds: number;
  cpus: number;
  users: string | number;
  dataset_sha256: string;
}

export interface CI {
  n: number;
  mean: number | null;
  lo: number | null;
  hi: number | null;
}

export interface AblationRow {
  set: "core" | "location";
  model: string;
  detector: string;
  people: number;
  auroc: CI;
  f1: CI;
  precision: CI;
  recall: CI;
  fpr: CI;
  event_recall: CI;
  latency_min: CI;
  false_alarms_per_hour: CI;
  auroc_novel_activity: CI;
  auroc_off_schedule: CI;
}

export interface Test {
  detector: string;
  set: string;
  a: string;
  b: string;
  metric: string;
  n: number;
  mean_diff: number | null;
  better?: number;
  worse?: number;
  p: number | null;
  p_holm: number | null;
}

export interface Ablation {
  aggregate: AblationRow[];
  tests: Test[];
  provenance: Provenance;
}

export interface Category {
  category: string;
  fp: number;
  fp_share: number;
  tn_share: number;
  lift: number | null;
}

export interface FPExample {
  uuid: string;
  time: string;
  score: number;
  threshold: number;
  categories: string[];
  explanation: Record<string, number>;
}

export interface FalsePositives {
  categories: Category[];
  examples: FPExample[];
  provenance: Provenance;
}

export interface PersonIndex {
  uuid: string;
  minutes: number;
  events: number;
  detected: number;
  alarms: number;
  auroc: number | null;
  f1: number | null;
  fpr: number | null;
  start: string;
  end: string;
}

export interface Minute {
  t: string;
  score: number;
  alarm: boolean;
  kind: number; // 0 normal, 1 novel activity, 2 off schedule, -1 undetermined
  activity: string | null;
  acc: number | null;
  gyro: number | null;
  why: Record<string, number> | null;
}

export interface AnomalyEvent {
  start: string;
  end: string;
  minutes: number;
  kind: string;
  activity: string | null;
  detected: boolean;
  latency_min: number | null;
  first: number;
  last: number;
}

export interface Timeline {
  uuid: string;
  model: string;
  detector: string;
  threshold: number;
  metrics: Record<string, number | string | null>;
  minutes: Minute[];
  events: AnomalyEvent[];
}

export interface SummaryTable {
  id: string;
  caption: string;
  columns: { key: string; label: string; align?: "l" | "r" }[];
  rows: Record<string, string | number | boolean | null>[];
}

export interface ExperimentSummary {
  title: string;
  question: string;
  findings: string[];
  tables: SummaryTable[];
  notes: string[];
  provenance: Provenance;
}

export interface ExperimentItem extends Partial<Provenance> {
  experiment: string;
  status: "complete" | "pending";
  title?: string;
  question?: string;
}

/* ---------- fetching ---------- */
export class ApiError extends Error {
  constructor(
    public url: string,
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const cache = new Map<string, unknown>();

export async function getJson<T>(url: string): Promise<T> {
  if (cache.has(url)) return cache.get(url) as T;
  let res: Response;
  try {
    res = await fetch(url, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError(url, 0, "The Cadence API could not be reached.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(url, res.status, detail);
  }
  const data = (await res.json()) as T;
  cache.set(url, data);
  return data;
}

export interface ApiState<T> {
  data: T | undefined;
  error: ApiError | undefined;
  loading: boolean;
  retry: () => void;
}

export function useApi<T>(url: string | null): ApiState<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<ApiError | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(url !== null);
  const [nonce, setNonce] = useState(0);
  const current = useRef(url);

  useEffect(() => {
    current.current = url;
    if (url === null) {
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(undefined);
    getJson<T>(url)
      .then((d) => {
        if (alive && current.current === url) setData(d);
      })
      .catch((e: unknown) => {
        if (alive && current.current === url)
          setError(e instanceof ApiError ? e : new ApiError(url, 0, String(e)));
      })
      .finally(() => {
        if (alive && current.current === url) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [url, nonce]);

  const retry = useCallback(() => {
    if (url) cache.delete(url);
    setNonce((n) => n + 1);
  }, [url]);

  return { data, error, loading, retry };
}

export const api = {
  ablation: "/api/ablation",
  falsePositives: "/api/false-positives",
  people: "/api/people",
  person: (uuid: string) => `/api/people/${encodeURIComponent(uuid)}`,
  experiments: "/api/experiments",
  experiment: (exp: string) => `/api/experiments/${encodeURIComponent(exp)}`,
};
