# Plan: Multimodal Behavioural Anomaly Detection

> Written before the experiments ran; changes made during the build are recorded in
> `docs/DECISIONS.md`.

## 1. Scope

Detect abnormal behavioural patterns from several sensor streams, and find out which streams
actually help. Pipeline: sensor streams → synchronisation → feature extraction → multimodal fusion
→ anomaly detection → anomaly score → classification (alarm or not).

The key experiment is a **modality ablation**, not a combination of everything:

| Model | Streams |
|---|---|
| A | accelerometer |
| B | accelerometer + gyroscope |
| C | accelerometer + gyroscope + temporal information (time of day) |

Two extensions separate effects the A/B/C chain confounds: **accelerometer + time** (does time help
without the gyroscope?) and **C + location** (the spec lists GPS among the streams).

## 2. Data

ExtraSensory (Vaizman et al., 2017): 60 people, 377,346 minutes of normal life, phone accelerometer,
gyroscope, location, timestamps and self-reported context labels (`data/DATASET.md`). It is the only
public dataset found that has all the streams the spec names, recorded in daily life with time and
location. Its features are computed by the dataset authors per minute; raw signals are a separate,
much larger download and are not used (DECISIONS D1).

## 3. Ground truth

The dataset has no anomaly label. One is defined from each person's own reports, before any
detector runs (DECISIONS D2): their first half of days is the **reference**, later days are the
**test** period; a test minute is a **novel activity** if its main activity is under 1% of their
reference minutes, **off schedule** if a familiar activity occurs in a three-hour slot where it never
occurred in the reference (slot with ≥ 30 reference minutes), and **normal** if seen in that slot.
Detectors never see labels.

## 4. Research questions and hypotheses

| | Question | Hypothesis | Experiment |
|---|---|---|---|
| RQ1 | Does each added stream improve detection? | The gyroscope adds little over the accelerometer (both measure motion of the same phone). Time of day helps. | E1 |
| RQ2 | Which stream helps which kind of anomaly? | Time helps off-schedule anomalies and not novel activities. | E2 |
| RQ3 | Why does the detector raise false alarms? | False alarms cluster in phone-handling and transition minutes, where motion changes without behaviour changing. | E3 |
| RQ4 | What does cutting false alarms cost in latency? | A persistence rule (k of n minutes) cuts false alarms more than it delays detection. | E4 |
| RQ5 | Does the answer depend on choices we made? | The A/B/C conclusions hold under other fusion weighting, anomaly thresholds and kNN k. | E5 |

## 5. Method

- **Detectors**, fitted per person on reference minutes only: k-nearest neighbours (mean distance to
  10 neighbours; decomposes exactly into per-modality shares, used for explanations), isolation
  forest (3 seeds), Gaussian (Mahalanobis, Ledoit-Wolf covariance).
- **Threshold**: the 95th percentile of out-of-sample reference scores (two-fold cross-fit over the
  reference days). No test label sets any parameter.
- **Comparison**: models compared on the same minutes per person; mean over people with a 95%
  bootstrap interval; paired Wilcoxon over people, Holm-corrected within detector.

## 6. Metrics

Precision, recall, F1, AUROC, false-positive rate, events detected, detection latency, false
alarms per hour of normal behaviour (`docs/METRICS.md`).

## 7. Deliverables

Python package `behavlab`; experiments E1–E5 with versioned results; `docs/REPORT.md`; the
**Cadence** console (temporal sensor analytics with an interactive anomaly timeline and
per-event explanation); tests; CI.

## 8. Risks

- Self-reported labels are incomplete and noisy, so ground truth is imperfect.
- About four reference days per person; weekly routines cannot be learned.
- Anomalies are rare (a few percent of minutes), so per-person AUROC is noisy; results are
  aggregated over people with intervals.
