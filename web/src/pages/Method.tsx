import { PageHead } from "../components/ui";

const STAGES = [
  ["Sensor streams", "ExtraSensory: one record per minute for 60 people, with features the dataset authors computed from each sensor's 20-second recording (phone accelerometer, gyroscope, location) and the timestamp."],
  ["Synchronisation", "Records sorted and de-duplicated by time, converted to local time (America/Los_Angeles, checked against the dataset's own time-of-day flags), with a per-minute availability mask for each sensor and real gaps kept."],
  ["Feature extraction", "Per-minute sensor features as published; time of day as a point on the circle (sine and cosine of the hour)."],
  ["Multimodal fusion", "Each sensor's features are imputed and robust-standardised on the person's reference days only, then scaled so every sensor block carries equal weight, and concatenated."],
  ["Anomaly detection", "Per person: k-nearest neighbours, isolation forest or a Gaussian model, fitted on the reference days (the first half of their days)."],
  ["Anomaly score", "Distance or isolation score per minute; higher means less like anything in the reference days."],
  ["Classification", "Alarm when the score passes the 95th percentile of out-of-sample reference scores (two-fold cross-fit over reference days). No test label sets any threshold."],
];

export function Method() {
  return (
    <>
      <PageHead title="Method">
        How a minute of someone's life becomes an anomaly score, and how the
        score is judged.
      </PageHead>
      <section className="panel">
        <div className="panel-head">
          <h2>Pipeline</h2>
        </div>
        <ol className="pipeline">
          {STAGES.map(([t, d]) => (
            <li key={t}>
              <strong>{t}.</strong> <span className="secondary">{d}</span>
            </li>
          ))}
        </ol>
      </section>
      <div className="grid-2">
        <section className="panel">
          <div className="panel-head">
            <h2>What counts as abnormal</h2>
          </div>
          <div className="panel-body prose">
            <p>
              The dataset has no anomaly label, so one is defined from what each
              person reported, before any detector is run. Their first half of
              days is the reference; on later days a minute is
            </p>
            <ul>
              <li>
                <strong>novel activity</strong> if its main activity is under 1%
                of their reference minutes;
              </li>
              <li>
                <strong>off schedule</strong> if the activity is familiar but
                never happened in that three-hour slot of the reference days, and
                the slot has at least 30 reference minutes;
              </li>
              <li>
                <strong>normal</strong> if it was seen in that slot, and
                undetermined otherwise (left out of the metrics).
              </li>
            </ul>
            <p>Detectors never see labels.</p>
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>The ablation</h2>
          </div>
          <div className="panel-body prose">
            <p>
              <strong>Model A</strong>: accelerometer. <strong>Model B</strong>:
              accelerometer and gyroscope. <strong>Model C</strong>: accelerometer,
              gyroscope and time of day. Two extensions separate the effects:
              accelerometer with time, and C with location.
            </p>
            <p>
              Models are compared on the same minutes, per person, with paired
              Wilcoxon tests over people and Holm correction. Metrics: precision,
              recall, F1, AUROC, false-positive rate, the share of anomaly events
              detected, and detection latency (minutes from an event's start to
              its first alarm).
            </p>
          </div>
        </section>
      </div>
      <section className="panel">
        <div className="panel-head">
          <h2>Limits</h2>
        </div>
        <div className="panel-body prose">
          <ul>
            <li>
              Anomalies are defined from self-reported labels, which are
              incomplete and sometimes wrong; an "anomaly" here is unusual for
              the person, not necessarily harmful.
            </li>
            <li>
              Features are the dataset's per-minute summaries, not raw signals,
              so the study measures which streams help given these features.
            </li>
            <li>
              About four reference days per person: weekly routines cannot be
              learned, so weekday is not used.
            </li>
          </ul>
        </div>
      </section>
    </>
  );
}
