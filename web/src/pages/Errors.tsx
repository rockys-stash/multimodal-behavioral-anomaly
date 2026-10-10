import { useState } from "react";
import { Link } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { ErrorOrPending, Loading, PageHead, ProvenanceLine, Segmented } from "../components/ui";
import { type Category, type FalsePositives, api, useApi } from "../lib/api";
import { MODALITY_LABEL, num, pct, shortId } from "../lib/format";

const GROUPS = [
  { id: "phone", label: "Phone position" },
  { id: "transition", label: "Transition" },
  { id: "activity", label: "Activity" },
  { id: "explanation", label: "Explanation" },
  { id: "context", label: "Context labels" },
];

export function Errors() {
  const { data, error, loading, retry } = useApi<FalsePositives>(api.falsePositives);
  const [group, setGroup] = useState("phone");
  return (
    <>
      <PageHead title="False positives">
        Alarms on minutes that were normal for the person. Each category is
        compared with the normal minutes that raised no alarm: a lift above 1
        means the category is over-represented among false alarms.
      </PageHead>
      {loading && !data && <Loading label="Loading error analysis" />}
      {error && <ErrorOrPending error={error} retry={retry} what="the error analysis" command="make e3" />}
      {data && (
        <>
          <Segmented label="Category" value={group} onChange={setGroup} options={GROUPS} />
          <section className="panel">
            <div className="panel-head">
              <h2>{GROUPS.find((g) => g.id === group)?.label}</h2>
            </div>
            <DataTable
              caption="False positives by category"
              rows={data.categories
                .filter((c) => c.category.startsWith(`${group}:`) && (group !== "context" || c.fp >= 30))
                .sort((a, b) => (b.lift ?? 0) - (a.lift ?? 0))}
              rowKey={(c) => c.category}
              columns={[
                { key: "c", label: "Category", render: (c: Category) => c.category.split(": ")[1] },
                { key: "fp", label: "False positives", align: "r", render: (c) => c.fp.toLocaleString("en") },
                { key: "fps", label: "Share of false positives", align: "r", render: (c) => pct(c.fp_share) },
                { key: "tns", label: "Share of quiet normal minutes", align: "r", render: (c) => pct(c.tn_share) },
                {
                  key: "lift",
                  label: "Lift",
                  align: "r",
                  render: (c) => <LiftBar lift={c.lift} />,
                },
              ]}
            />
            {group === "context" && <p className="muted small panel-body">Labels with at least 30 false positives.</p>}
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>Examples</h2>
              <span className="muted small">{data.examples.length} sampled false positives (up to five per person)</span>
            </div>
            <DataTable
              caption="Example false positives"
              rows={data.examples.slice(0, 40)}
              rowKey={(e) => `${e.uuid}-${e.time}`}
              columns={[
                {
                  key: "who",
                  label: "Person",
                  render: (e) => (
                    <Link className="mono" to={`/people/${e.uuid}`}>
                      {shortId(e.uuid)}
                    </Link>
                  ),
                },
                { key: "t", label: "Time", render: (e) => <span className="mono">{e.time.slice(0, 16).replace("T", " ")}</span> },
                { key: "s", label: "Score / threshold", align: "r", render: (e) => `${num(e.score, 2)} / ${num(e.threshold, 2)}` },
                {
                  key: "what",
                  label: "What the person reported",
                  render: (e) =>
                    e.categories
                      .filter((c) => !c.startsWith("explanation") && !c.startsWith("transition: no"))
                      .map((c) => c.split(": ")[1])
                      .join(", "),
                },
                {
                  key: "why",
                  label: "Largest share",
                  render: (e) => {
                    const top = Object.entries(e.explanation).sort((a, b) => b[1] - a[1])[0];
                    return top ? `${MODALITY_LABEL[top[0]] ?? top[0]} ${pct(top[1], 0)}` : "–";
                  },
                },
              ]}
            />
          </section>
          <ProvenanceLine p={data.provenance} />
        </>
      )}
    </>
  );
}

function LiftBar({ lift }: { lift: number | null }) {
  if (lift === null) return <>–</>;
  const w = Math.min(lift / 4, 1) * 60;
  return (
    <span className="lift">
      <span className="lift-bar" style={{ width: `${w}px` }} data-over={lift > 1 ? "yes" : "no"} aria-hidden="true" />
      <span className="mono">{lift.toFixed(2)}</span>
    </span>
  );
}
