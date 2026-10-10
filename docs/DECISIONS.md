# Decisions

**D1. ExtraSensory per-minute features, not raw signals.** ExtraSensory is the public dataset with
all the streams the spec names (accelerometer, gyroscope, location, time, activity labels) recorded
in daily life. It publishes per-minute features computed by its authors from each sensor's 20 s
recording; the raw recordings are a separate download of tens of gigabytes. We use the published
features, so "feature extraction" for the motion sensors is the authors', and ours for time. The
study therefore measures which streams help *given these features*.

**D2. Ground truth from each person's own reports, fixed before any detector ran.** The dataset
has no anomaly label. Defining anomalies as rare behaviour for the person (novel activity) or
familiar behaviour at an unfamiliar time (off schedule), from their reference days only, matches
"abnormal behavioural pattern" without inventing events. Thresholds (1% rarity, 3-hour slots, 30
reference minutes per slot) were fixed in `truth.py` before E1; E5 varies the rarity threshold.

**D3. Thresholds from reference data only.** The alarm threshold is the 95th percentile of
out-of-sample reference scores (two-fold cross-fit over reference days), so no test label tunes
anything. The detector used on test days is fitted on all reference minutes, so its test scores are
slightly lower than the cross-fitted ones; the alarm rate on normal test minutes can therefore be
below the nominal 5%.

**D4. Equal weight per sensor block.** After robust standardisation each modality's block is
scaled to mean squared norm 1 on the reference minutes. Plain concatenation would let the 26
accelerometer features outweigh the 2 time features by count. A first version divided each block
by the square root of its number of features; a unit test showed that robust (IQR) scaling leaves
blocks of different spread, so the scale is now computed from the data. E5 reports the ablation with
plain concatenation as a robustness check.

**D5. Time of day only; no weekday.** With about four reference days per person, a weekly
pattern cannot be learned, and a test weekday absent from the reference would look anomalous by
construction. An early smoke run showed exactly that: with weekday features, a Gaussian model
alarmed on every test minute of one person (false-positive rate 1.0). Temporal information is the
hour of day on the circle.

**D6. Local time.** Timestamps are UTC. Participants were in San Diego, so local time is
America/Los_Angeles. The data card checks this against the dataset's own time-of-day flags
(agreement per person reported in `docs/generated/data_check.json`).

**D7. Primary model for error analysis and the console fixed in advance.** E3, E4 and the console
use model C with kNN, chosen before E1 ran because C is the specified full model and kNN's score
splits exactly into per-modality shares, which is the per-event explanation the spec asks for.

**D8. Per-minute outputs are not committed.** Timelines and per-minute scores are derived from
the dataset (CC BY-NC-SA 4.0). They are generated locally (`make timelines`, `var/`); the
repository holds code, configs, aggregate results and sampled false-positive examples.
