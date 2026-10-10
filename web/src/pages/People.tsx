import { useNavigate } from "react-router-dom";
import { DataTable } from "../components/DataTable";
import { ErrorOrPending, Loading, PageHead } from "../components/ui";
import { api, type PersonIndex, useApi } from "../lib/api";
import { num, pct, shortId } from "../lib/format";

export function People() {
  const nav = useNavigate();
  const { data, error, loading, retry } = useApi<{ items: PersonIndex[] }>(
    api.people,
  );
  return (
    <>
      <PageHead title="Timelines">
        One row per person in ExtraSensory, scored by model C (accelerometer,
        gyroscope and time of day) with k-nearest neighbours on the days after
        their reference days. Open a person to see their anomaly timeline.
      </PageHead>
      {loading && !data && <Loading label="Loading people" />}
      {error && (
        <ErrorOrPending
          error={error}
          retry={retry}
          what="timelines"
          command="make timelines"
        />
      )}
      {data && (
        <section className="panel">
          <div className="panel-head">
            <h2>{data.items.length} people</h2>
            <span className="muted small">
              Sorted by number of anomaly events
            </span>
          </div>
          <DataTable
            caption="People and detection on their test days"
            rows={[...data.items].sort((a, b) => b.events - a.events)}
            rowKey={(r) => r.uuid}
            onSelect={(k) => nav(`/people/${k}`)}
            columns={[
              {
                key: "uuid",
                label: "Person",
                render: (r) => <span className="mono">{shortId(r.uuid)}</span>,
              },
              {
                key: "range",
                label: "Test days",
                render: (r) => `${r.start.slice(0, 10)} → ${r.end.slice(0, 10)}`,
              },
              {
                key: "minutes",
                label: "Minutes",
                align: "r",
                render: (r) => r.minutes.toLocaleString("en"),
              },
              {
                key: "events",
                label: "Anomaly events",
                align: "r",
                render: (r) => r.events,
              },
              {
                key: "detected",
                label: "Detected",
                align: "r",
                render: (r) => (r.events ? `${r.detected} / ${r.events}` : "–"),
              },
              {
                key: "auroc",
                label: "AUROC",
                align: "r",
                render: (r) => num(r.auroc),
              },
              {
                key: "fpr",
                label: "False-positive rate",
                align: "r",
                render: (r) => pct(r.fpr),
              },
            ]}
          />
        </section>
      )}
    </>
  );
}
