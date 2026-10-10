import { type KeyboardEvent, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { ErrorOrPending, Loading, PageHead, Segmented } from "../components/ui";
import { type Minute, type Timeline, api, useApi } from "../lib/api";
import {
  ACTIVITY_LABEL,
  KIND_LABEL,
  MODALITY_LABEL,
  num,
  pct,
  shortId,
} from "../lib/format";

const W = 960;
const H = 260;
const PAD = { l: 44, r: 12, t: 12, b: 26 };
const LANES = { motion: [PAD.t, 92], score: [104, 214], truth: [222, 234] } as const;

function minuteOfDay(t: string): number {
  const h = Number(t.slice(11, 13));
  const m = Number(t.slice(14, 16));
  return h * 60 + m;
}

export function Person() {
  const { uuid = "" } = useParams();
  const { data, error, loading, retry } = useApi<Timeline>(api.person(uuid));
  if (loading && !data) return <Loading label="Loading timeline" rows={8} />;
  if (error)
    return (
      <>
        <PageHead title={`Person ${shortId(uuid)}`} />
        <ErrorOrPending
          error={error}
          retry={retry}
          what="this person's timeline"
          command="make timelines"
        />
      </>
    );
  if (!data) return null;
  return <PersonView tl={data} />;
}

function PersonView({ tl }: { tl: Timeline }) {
  const days = useMemo(
    () => [...new Set(tl.minutes.map((m) => m.t.slice(0, 10)))],
    [tl],
  );
  const firstEventDay = tl.events[0]?.start.slice(0, 10);
  const [day, setDay] = useState<string>(firstEventDay ?? days[0] ?? "");
  const [sel, setSel] = useState<number | null>(
    tl.events[0] ? tl.events[0].first : null,
  );
  const idx = useMemo(
    () =>
      tl.minutes
        .map((m, i) => [m, i] as const)
        .filter(([m]) => m.t.startsWith(day))
        .map(([, i]) => i),
    [tl, day],
  );
  const m = tl.metrics;
  const detected = tl.events.filter((e) => e.detected).length;
  const selected = sel !== null ? tl.minutes[sel] : undefined;

  return (
    <>
      <PageHead
        title={`Person ${shortId(tl.uuid)}`}
        actions={
          <Link className="btn ghost" to="/people">
            All people
          </Link>
        }
      >
        Test days scored by model {tl.model} with{" "}
        {tl.detector === "knn" ? "k-nearest neighbours" : tl.detector}. Alarms
        fire when the score passes the threshold set on this person's reference
        days.
      </PageHead>
      <div className="stat-row" role="list">
        <Stat label="AUROC" value={num(m.auroc as number | null)} />
        <Stat
          label="Events detected"
          value={tl.events.length ? `${detected} / ${tl.events.length}` : "none"}
        />
        <Stat label="Precision" value={pct(m.precision as number | null)} />
        <Stat label="Recall" value={pct(m.recall as number | null)} />
        <Stat
          label="False-positive rate"
          value={pct(m.fpr as number | null)}
        />
      </div>
      <section className="panel">
        <div className="panel-head">
          <h2>Day</h2>
          <Segmented
            label="Day"
            value={day}
            onChange={(d) => {
              setDay(d);
              setSel(null);
            }}
            options={days.map((d) => ({
              id: d,
              label: d.slice(5),
              title: `${tl.events.filter((e) => e.start.startsWith(d)).length} events`,
            }))}
          />
        </div>
        <div className="panel-body">
          <DayChart
            tl={tl}
            idx={idx}
            sel={sel}
            onSelect={setSel}
            day={day}
          />
          <Legend />
        </div>
      </section>
      <div className="grid-2">
        <section className="panel" aria-live="polite">
          <div className="panel-head">
            <h2>Minute</h2>
          </div>
          <div className="panel-body">
            {selected ? (
              <MinuteView m={selected} thr={tl.threshold} />
            ) : (
              <p className="muted">
                Select a minute on the chart (click, or focus the chart and use
                the arrow keys), or an event below.
              </p>
            )}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Anomaly events</h2>
            <span className="muted small">{tl.events.length} on test days</span>
          </div>
          {tl.events.length ? (
            <DataTable
              caption="Anomaly events"
              rows={tl.events}
              rowKey={(e) => String(e.first)}
              selected={sel !== null ? String(sel) : null}
              onSelect={(k) => {
                const ev = tl.events.find((e) => String(e.first) === k);
                if (ev) {
                  setDay(ev.start.slice(0, 10));
                  setSel(ev.first);
                }
              }}
              columns={[
                {
                  key: "start",
                  label: "Start",
                  render: (e) => e.start.slice(5, 16).replace("T", " "),
                },
                { key: "kind", label: "Kind", render: (e) => e.kind },
                {
                  key: "activity",
                  label: "Activity",
                  render: (e) =>
                    e.activity ? (ACTIVITY_LABEL[e.activity] ?? e.activity) : "–",
                },
                {
                  key: "minutes",
                  label: "Minutes",
                  align: "r",
                  render: (e) => e.minutes,
                },
                {
                  key: "detected",
                  label: "Detected",
                  render: (e) =>
                    e.detected ? (
                      <span className="ok">✓ after {num(e.latency_min, 0)} min</span>
                    ) : (
                      <span className="bad">✕ missed</span>
                    ),
                },
              ]}
            />
          ) : (
            <div className="panel-body muted">
              No anomaly events on this person's test days.
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat" role="listitem">
      <span className="muted small">{label}</span>
      <strong className="mono">{value}</strong>
    </div>
  );
}

function Legend() {
  return (
    <div className="legend small">
      <span>
        <span className="swatch" style={{ background: "var(--series-a)" }} />{" "}
        accelerometer magnitude
      </span>
      <span>
        <span className="swatch" style={{ background: "var(--series-b)" }} />{" "}
        gyroscope magnitude
      </span>
      <span>
        <span className="swatch" style={{ background: "var(--ink)" }} /> anomaly
        score
      </span>
      <span>
        <span className="swatch dashed" /> threshold
      </span>
      <span>
        <span className="swatch" style={{ background: "var(--bad)" }} /> alarm
      </span>
      <span>
        <span className="swatch" style={{ background: "var(--anomaly)" }} />{" "}
        true anomaly (novel activity solid, off schedule hatched)
      </span>
    </div>
  );
}

function DayChart({
  tl,
  idx,
  sel,
  onSelect,
  day,
}: {
  tl: Timeline;
  idx: number[];
  sel: number | null;
  onSelect: (i: number) => void;
  day: string;
}) {
  const pts = idx.map((i) => ({ i, m: tl.minutes[i] as Minute }));
  const x = (t: string) => PAD.l + ((W - PAD.l - PAD.r) * minuteOfDay(t)) / 1440;
  const maxScore = Math.max(tl.threshold * 1.6, ...pts.map((p) => p.m.score));
  const yScore = (s: number) =>
    LANES.score[1] - ((LANES.score[1] - LANES.score[0]) * Math.min(s, maxScore)) / maxScore;
  const accMax = Math.max(1e-6, ...pts.map((p) => p.m.acc ?? 0));
  const gyroMax = Math.max(1e-6, ...pts.map((p) => p.m.gyro ?? 0));
  const yMotion = (v: number, max: number) =>
    LANES.motion[1] - ((LANES.motion[1] - LANES.motion[0]) * v) / max;

  const path = (sel: (m: Minute) => number | null) => {
    let d = "";
    let prev: Minute | null = null;
    for (const { m } of pts) {
      const v = sel(m);
      if (v === null) {
        prev = null;
        continue;
      }
      const gap = prev ? minuteOfDay(m.t) - minuteOfDay(prev.t) : 99;
      d += `${gap > 3 ? "M" : "L"}${x(m.t).toFixed(1)},${v.toFixed(1)}`;
      prev = m;
    }
    return d;
  };

  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    if (!pts.length) return;
    const pos = sel === null ? -1 : pts.findIndex((p) => p.i === sel);
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const step = e.shiftKey ? 30 : 1;
      const next =
        e.key === "ArrowRight"
          ? Math.min(pts.length - 1, pos + step)
          : Math.max(0, pos < 0 ? 0 : pos - step);
      const p = pts[next];
      if (p) onSelect(p.i);
    }
  };

  const pick = (clientX: number, rect: DOMRect) => {
    const vx = ((clientX - rect.left) / rect.width) * W;
    let best: number | null = null;
    let bestD = Infinity;
    for (const p of pts) {
      const d = Math.abs(x(p.m.t) - vx);
      if (d < bestD) {
        bestD = d;
        best = p.i;
      }
    }
    if (best !== null) onSelect(best);
  };

  const selMinute = sel !== null ? tl.minutes[sel] : undefined;
  const alarms = pts.filter((p) => p.m.alarm).length;
  const anomalous = pts.filter((p) => p.m.kind > 0).length;

  return (
    <figure className="chart">
      <svg
        className="chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        tabIndex={0}
        aria-label={`Timeline for ${day}: ${pts.length} scored minutes, ${anomalous} truly anomalous, ${alarms} alarms. Use the left and right arrow keys to move between minutes.`}
        onKeyDown={onKey}
        onClick={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
      >
        <defs>
          <pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="2" height="4" fill="var(--anomaly)" />
          </pattern>
        </defs>
        {[0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => {
          const xx = PAD.l + ((W - PAD.l - PAD.r) * h) / 24;
          return (
            <g key={h}>
              <line x1={xx} x2={xx} y1={PAD.t} y2={LANES.truth[1]} stroke="var(--rule)" />
              <text x={xx} y={H - 8} textAnchor="middle" className="tick">
                {String(h).padStart(2, "0")}:00
              </text>
            </g>
          );
        })}
        <text x={4} y={LANES.motion[0] + 10} className="tick">motion</text>
        <text x={4} y={LANES.score[0] + 10} className="tick">score</text>
        <text x={4} y={LANES.truth[1]} className="tick">truth</text>
        {pts
          .filter((p) => p.m.kind > 0)
          .map((p) => (
            <rect
              key={`t${p.i}`}
              x={x(p.m.t) - 1}
              width={2.2}
              y={LANES.truth[0]}
              height={LANES.truth[1] - LANES.truth[0]}
              fill={p.m.kind === 1 ? "var(--anomaly)" : "url(#hatch)"}
            />
          ))}
        <path d={path((m) => (m.acc === null ? null : yMotion(m.acc, accMax)))} fill="none" stroke="var(--series-a)" strokeWidth={1} />
        <path d={path((m) => (m.gyro === null ? null : yMotion(m.gyro, gyroMax)))} fill="none" stroke="var(--series-b)" strokeWidth={1} />
        <line x1={PAD.l} x2={W - PAD.r} y1={yScore(tl.threshold)} y2={yScore(tl.threshold)} stroke="var(--ink-3)" strokeDasharray="4 3" />
        <path d={path((m) => yScore(m.score))} fill="none" stroke="var(--ink)" strokeWidth={1.1} />
        {pts
          .filter((p) => p.m.alarm)
          .map((p) => (
            <line key={`a${p.i}`} x1={x(p.m.t)} x2={x(p.m.t)} y1={LANES.score[0] - 6} y2={LANES.score[0]} stroke="var(--bad)" strokeWidth={1.5} />
          ))}
        {selMinute && selMinute.t.startsWith(day) && (
          <line x1={x(selMinute.t)} x2={x(selMinute.t)} y1={PAD.t} y2={LANES.truth[1]} stroke="var(--accent)" strokeWidth={2} />
        )}
      </svg>
      <figcaption className="muted small">
        {pts.length} scored minutes on {day}; {anomalous} truly anomalous;{" "}
        {alarms} alarms. Motion lines are scaled to the day's maximum.
      </figcaption>
    </figure>
  );
}

function MinuteView({ m, thr }: { m: Minute; thr: number }) {
  const why = m.why ? Object.entries(m.why).sort((a, b) => b[1] - a[1]) : [];
  return (
    <div className="stack-sm">
      <dl className="kv">
        <dt>Time</dt>
        <dd className="mono">{m.t.replace("T", " ")}</dd>
        <dt>Reported activity</dt>
        <dd>{m.activity ? (ACTIVITY_LABEL[m.activity] ?? m.activity) : "not reported"}</dd>
        <dt>Ground truth</dt>
        <dd>{KIND_LABEL[m.kind] ?? m.kind}</dd>
        <dt>Score</dt>
        <dd className="mono">
          {num(m.score)} (threshold {num(thr)})
        </dd>
        <dt>Alarm</dt>
        <dd>{m.alarm ? <span className="bad">✕ raised</span> : "no"}</dd>
      </dl>
      {why.length > 0 && (
        <>
          <h3>Why this score</h3>
          <p className="muted small">
            Share of the distance to the 10 most similar reference minutes that
            each sensor accounts for.
          </p>
          <div className="bars" role="list">
            {why.map(([mod, share]) => (
              <div key={mod} className="bar-row" role="listitem">
                <span>{MODALITY_LABEL[mod] ?? mod}</span>
                <span className="bar-track" aria-hidden="true">
                  <span className="bar-fill" style={{ width: `${share * 100}%` }} />
                </span>
                <span className="mono">{pct(share, 0)}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
