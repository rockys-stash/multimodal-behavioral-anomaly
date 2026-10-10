# Report: which sensor streams actually reveal unusual behaviour?

All numbers come from the runs in `results/` at commit `ef4e2b8` (clean work tree, all 60
ExtraSensory participants). Full tables are generated into
[generated/results.md](generated/results.md) and the data card into
[generated/data_check.json](generated/data_check.json); this report interprets them.

## 1. Set-up

**Data.** ExtraSensory: 60 people, 377,346 minutes of everyday life with per-minute phone
accelerometer, gyroscope and location features, timestamps, and self-reported activity and
context. Local time is America/Los_Angeles; it agrees with the dataset's own time-of-day flags for
a median of 96.4% of minutes per person (minimum 94.2%).

**Ground truth** (fixed before any detector ran, D2). Each person's first half of days is the
reference (208,853 minutes). On later days, a minute is a *novel activity* if its main activity is
under 1% of their reference minutes, *off schedule* if a familiar activity happens in a three-hour
slot where it never happened in the reference, and *normal* if it was seen in that slot. This
yields 131,705 scored test minutes: 955 novel-activity and 5,197 off-schedule minutes in 406
events, for 52 people. 57 people have enough reference data to be scored; 49 of them have at least
one anomalous minute on the accelerometer-and-gyroscope minutes, so AUROC, recall and events
detected average over 49 people and the false-positive rate over 57.

**Models.** A (accelerometer), B (+ gyroscope), C (+ time of day), plus two extensions:
accelerometer + time, and C + location. Each sensor block is robust-standardised on the reference
days and weighted equally (D4). Three detectors are fitted per person on reference minutes only:
k-nearest neighbours (kNN, k = 10), isolation forest (3 seeds) and a Gaussian (Mahalanobis) model.
The alarm threshold is the 95th percentile of cross-fitted reference scores, so no test label sets
any parameter (D3). Comparisons are paired over people (Wilcoxon), Holm-corrected within each
detector over 15 tests (five comparisons, three metrics).

## 2. Results by research question

**RQ1: does each added stream improve detection? (E1)** Detection is weak overall: mean AUROC is
0.61–0.65 for every model and detector. Within that:

- *The gyroscope adds nothing measurable.* B against A: +0.009 (kNN), +0.013 (isolation forest),
  +0.008 (Gaussian), none significant. Hypothesis supported: both sensors measure the motion of
  the same phone.
- *Time of day helps on top of motion, a little.* C against B: +0.029 AUROC for kNN (better for 31
  of 49 people, Holm p = 0.047) and +0.008 for the Gaussian model (34 of 49, p = 0.029); the
  isolation forest's +0.004 is borderline (34 of 49, p = 0.050). C against A is not significant
  after correction for any detector (kNN +0.038, p = 0.082).
- *Time without the gyroscope* (accelerometer + time against A) is positive for all detectors but
  not significant.
- *Location adds nothing in AUROC* (C + location against C: +0.005, −0.006, +0.004). With kNN it
  raises recall (0.078 → 0.113) by raising the false-positive rate (0.015 → 0.040), which is a
  threshold effect, not better ranking.
- No model improves F1 or events detected significantly.

Hypothesis partly supported: the gyroscope result holds; time helps, but the gain is small and
detector-dependent.

**RQ2: which stream helps which kind of anomaly? (E2)** The two kinds behave very differently.
Novel activities are easy (AUROC 0.85–0.87 for every model) and gain nothing from time (C against
B: +0.001 to +0.004). Off-schedule minutes are barely detectable (AUROC 0.55–0.59), and this is
where time helps: C against B +0.037 for kNN (44 people, Holm p = 0.017) and +0.010 for the
Gaussian model (p = 0.014). Hypothesis supported, with the caveat that even with time, off-schedule
behaviour is detected only slightly better than chance. One time feature (hour on the circle) is a
weak description of a routine learned from about four days.

**RQ3: why does the detector raise false alarms? (E3, model C with kNN, fixed in advance, D7).**
1,633 false positives against 116,737 quiet normal minutes. Phone handling and transitions are
over-represented as hypothesised: phone in hand (lift 2.11), in pocket (1.51), and minutes where
the person reported a transition (2.57). But the largest lifts are normal activities and places in which
phone motion varies more than when sitting or lying: walking (3.45), being outside (4.26), with co-workers
(2.92), driving (2.34). Our reading (inferred, not tested) is that the detector flags "unusual phone
motion" more than "unusual for this person". Hypothesis partly supported. Which sensor dominates the distance barely differs between
false alarms and quiet minutes (accelerometer-dominated 53.6% against 50.8%), so the explanation
does not help separate them.

**RQ4: what does cutting false alarms cost? (E4)** A persistence rule cuts false alarms about as
much as it cuts detection, so the hypothesis is not supported. At a 5% reference alarm rate, "2 of
3 minutes" lowers false alarms from 0.96 to 0.53 per hour (−45%) while events detected fall from
23.4% to 14.8% (−37%) and median latency rises from 9.0 to 10.7 minutes; "3 of 5" gives 0.41 per
hour and 9.5% of events. Simply raising the single-minute threshold does better: at a 2% rate the
single-minute rule gives 0.42 false alarms per hour and detects 17.8% of events, beating "2 of 3"
at 5% on both. On this data, persistence rules are dominated by a stricter threshold.

**RQ5: does the answer depend on our choices? (E5)** The direction of every A/B/C difference is
the same under all four alternative choices (plain concatenation without block weighting, novelty
cut-offs of 0.5% and 2%, kNN with k = 5 and 20): all 24 comparisons keep a positive mean
difference. Significance is fragile for kNN: without block weighting C against B drops from +0.029
to +0.006, and with k = 5 it loses significance. 20 of 24 variant comparisons reach the same verdict
as the default. Note that E5 corrects over three tests per variant, a smaller family than E1's, so
its "significant" is less conservative (stated in the run). The robust conclusions are the null
gyroscope effect and the small positive effect of time; the size of the time effect depends on
how the blocks are weighted.

## 3. What this means

1. On phone sensor summaries, the second motion sensor is redundant for behavioural anomaly
   detection; time of day is the stream that adds information, and only for timing anomalies.
2. Unsupervised detectors find *new activities* well and *activities at the wrong time* poorly.
   A system meant for routine monitoring needs a better model of time than an hour feature and a
   few reference days.
3. Most false alarms come from normal but motion-rich contexts (walking, outdoors, driving), which argues for a
   longer reference period or context-aware baselines, not for persistence rules.

## 4. Threats to validity

- **Ground truth is self-reported** and incomplete (missing labels are excluded as undetermined,
  36,788 test minutes). An "anomaly" is unusual for the person, not necessarily concerning.
- **Short reference periods** (about four days) make every routine-based judgement noisy; weekday
  structure cannot be learned and is not used (D5).
- **Per-minute features, not raw signals** (D1): the study says which streams help given these
  summaries; raw-signal models could change the gyroscope result.
- **Small effects, many tests.** Holm correction within detector is applied; effects near the
  threshold (isolation forest C against B, p = 0.050) are reported as not significant.
- **One population** of 60 mostly student and staff volunteers in one city.

## 5. Reproducibility

`make experiments` reruns the data check, E1–E5, the generated tables and the console timelines
(about 7 minutes on 4 CPUs). The first full run, before two reporting fixes, gave identical
numbers. `make smoke` checks the pipeline on 6 people in CI and is never reported.
