import { useState } from "react";
import { DataTable } from "../components/DataTable";
import {
  ErrorOrPending,
  Loading,
  PageHead,
  ProvenanceLine,
  Segmented,
} from "../components/ui";
import { type Ablation as AblationData, type AblationRow, type CI, api, useApi } from "../lib/api";
import { DETECTOR_LABEL, MODEL_LABEL, MODEL_SERIES, num, pval, signed } from "../lib/format";

type Metric = "auroc" | "f1" | "event_recall" | "fpr";
const METRICS: { id: Metric; label: string }[] = [
  { id: "auroc", label: "AUROC" },
  { id: "f1", label: "F1" },
  { id: "event_recall", label: "Events detected" },
  { id: "fpr", label: "False-positive rate" },
];

export function Ablation() {
  const { data, error, loading, retry } = useApi<AblationData>(api.ablation);
  const [det, setDet] = useState("knn");
  const [metric, setMetric] = useState<Metric>("auroc");
  return (
    <>
      <PageHead title="Modality ablation">
        Does adding a sensor stream improve detection? Each model is fitted per
        person on their reference days and scored on their test days; points are
        means over people with 95% bootstrap intervals.
      </PageHead>
      {loading && !data && <Loading label="Loading ablation" />}
      {error && <ErrorOrPending error={error} retry={retry} what="the ablation" command="make e1" />}
      {data && (
        <>
          <div className="controls">
            <Segmented
              label="Detector"
              value={det}
              onChange={setDet}
              options={[...new Set(data.aggregate.map((r) => r.detector))].map((d) => ({
                id: d,
                label: DETECTOR_LABEL[d] ?? d,
              }))}
            />
            <Segmented label="Metric" value={metric} onChange={setMetric} options={METRICS} />
          </div>
          <section className="panel">
            <div className="panel-head">
              <h2>{METRICS.find((m) => m.id === metric)?.label} by model</h2>
            </div>
            <div className="panel-body">
              <IntervalChart rows={data.aggregate.filter((r) => r.detector === det)} metric={metric} />
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>Paired tests over people</h2>
              <span className="muted small">Wilcoxon signed-rank, Holm-corrected within detector</span>
            </div>
            <DataTable
              caption="Paired tests"
              rows={data.tests.filter((t) => t.detector === det && t.metric === metric.replace("fpr", "auroc"))}
              rowKey={(t) => `${t.a}-${t.b}-${t.metric}`}
              columns={[
                { key: "cmp", label: "Comparison", render: (t) => `${MODEL_LABEL[t.b] ?? t.b} vs ${MODEL_LABEL[t.a] ?? t.a}` },
                { key: "metric", label: "Metric", render: (t) => METRICS.find((m) => m.id === t.metric)?.label ?? t.metric },
                { key: "n", label: "People", align: "r", render: (t) => t.n },
                { key: "d", label: "Mean difference", align: "r", render: (t) => signed(t.mean_diff) },
                { key: "bw", label: "Better / worse", align: "r", render: (t) => (t.better !== undefined ? `${t.better} / ${t.worse}` : "–") },
                {
                  key: "p",
                  label: "p (Holm)",
                  align: "r",
                  render: (t) => (
                    <span className={t.p_holm !== null && t.p_holm < 0.05 ? "strong" : undefined}>{pval(t.p_holm)}</span>
                  ),
                },
              ]}
            />
            {metric === "fpr" && (
              <p className="muted small panel-body">Tests are run on AUROC, F1 and events detected; the AUROC tests are shown.</p>
            )}
          </section>
          <ProvenanceLine p={data.provenance} />
        </>
      )}
    </>
  );
}

function IntervalChart({ rows, metric }: { rows: AblationRow[]; metric: Metric }) {
  const W = 720;
  const rowH = 34;
  const L = 230;
  const R = 70;
  const H = rows.length * rowH + 30;
  const cis: CI[] = rows.map((r) => r[metric]);
  const lo = Math.min(...cis.map((c) => c.lo ?? 1));
  const hi = Math.max(...cis.map((c) => c.hi ?? 0));
  const span = Math.max(hi - lo, 0.02);
  const min = Math.max(0, lo - span * 0.15);
  const max = Math.min(1, hi + span * 0.15);
  const x = (v: number) => L + ((W - L - R) * (v - min)) / (max - min || 1);
  const ticks = Array.from({ length: 5 }, (_, i) => min + ((max - min) * i) / 4);
  return (
    <figure className="chart">
      <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Mean ${metric} per model with 95% intervals`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={4} y2={H - 22} stroke="var(--rule)" />
            <text x={x(t)} y={H - 6} textAnchor="middle" className="tick">
              {t.toFixed(2)}
            </text>
          </g>
        ))}
        {rows.map((r, i) => {
          const c = r[metric];
          const y = 18 + i * rowH;
          if (c.mean === null || c.lo === null || c.hi === null) return null;
          const color = MODEL_SERIES[r.model] ?? "var(--ink)";
          return (
            <g key={`${r.set}-${r.model}`}>
              <text x={L - 10} y={y + 4} textAnchor="end" className="label">
                {MODEL_LABEL[r.model] ?? r.model}
                {r.set === "location" ? " ¹" : ""}
              </text>
              <line x1={x(c.lo)} x2={x(c.hi)} y1={y} y2={y} stroke={color} strokeWidth={2} />
              <circle cx={x(c.mean)} cy={y} r={5} fill={color} />
              <text x={W - R + 8} y={y + 4} className="tick mono">
                {num(c.mean)}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="muted small">
        n = {rows[0]?.people ?? 0} people per model on minutes with accelerometer and gyroscope. ¹ On the minutes that also have location (fewer people), so compare it with the C row marked ¹.
      </figcaption>
    </figure>
  );
}
