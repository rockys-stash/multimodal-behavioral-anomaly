# Metrics

Computed per person on their test minutes whose ground truth is determined (normal, novel
activity or off schedule), then averaged over people with a 95% percentile bootstrap interval
(people resampled). Code: `src/behavlab/evaluate.py`, `src/behavlab/stats.py`.

| Metric | Definition |
|---|---|
| Precision | Alarms on anomalous minutes / all alarms. |
| Recall | Anomalous minutes with an alarm / anomalous minutes. |
| F1 | Harmonic mean of precision and recall (0 when one of them is 0). |
| AUROC | Area under the ROC curve of the raw score, anomalous vs normal minutes. Threshold-free. Undefined for a person with only one class. |
| False-positive rate | Alarms on normal minutes / normal minutes. |
| False alarms per hour | Alarms on normal minutes / hours of normal minutes. |
| Events detected | Share of anomaly events with at least one alarm inside the event. An event is a maximal run of adjacent anomalous minutes with at most 2 minutes between records. |
| Detection latency | Minutes from an event's first minute to its first alarm, median over the person's detected events. Missed events do not enter it, so it must be read with events detected. |
| AUROC by kind | AUROC of one anomaly kind against normal minutes (E2). |
| Lift (E3) | Share of false positives in a category / share of true negatives (normal, no alarm) in that category. |

## Statistical tests

Model comparisons are paired by person: Wilcoxon signed-rank test on the per-person differences,
over people that have both values; Holm correction across the comparisons within a detector
(E1, E2) or within a variant and detector (E5). A comparison with fewer than 5 people, or with all
differences zero, has no p-value.
