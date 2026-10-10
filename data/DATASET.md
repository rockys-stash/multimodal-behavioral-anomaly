# Data

## ExtraSensory (per-minute features and labels)

| | |
|---|---|
| Source | `http://extrasensory.ucsd.edu/data/primary_data_files/ExtraSensory.per_uuid_features_labels.zip` |
| SHA-256 | `412d307bdf54a60dff81a705c2f25833889a46dca64a184e3b588ad99c69cb56` (checked by `behavlab fetch`) |
| Size | 225 MB zip; 60 gzipped CSV files, one per person |
| Licence | CC BY-NC-SA 4.0 (dataset website). Not committed here; fetched by `make data`. |
| Citation | Vaizman, Y., Ellis, K. and Lanckriet, G. (2017). Recognizing Detailed Human Context in the Wild from Smartphones and Smartwatches. *IEEE Pervasive Computing* 16(4), 62–74. |
| Collection | 60 volunteers in San Diego (students and staff), 2015–2016, using their own phones (and a smartwatch for 56) in their normal lives. A recording every minute for 20 s; the person labelled their context in an app. |

Counts printed by `behavlab check` (`docs/generated/data_check.json`): 60 people, 377,346
records (the paper states 377,346), 482 local days. Records with accelerometer features 377,056,
gyroscope 359,912, location 334,008; a single reported main activity 306,594.

**Streams used.** Phone accelerometer (`raw_acc:*`, 26 features), phone gyroscope
(`proc_gyro:*`, 26), location (`location:*` and `location_quick_features:*`, 17), and the
timestamp. Not used: audio, magnetometer, smartwatch, phone state (outside the spec's streams).

**Labels used.** The six mutually exclusive main activities (lying down, sitting, standing, walking,
running, bicycling) define the ground truth; phone position and other context labels are used only
to describe false positives (E3). Labels are self-reported, incomplete and sometimes wrong
(the dataset paper discusses this), so the ground truth is approximate.

**Known biases.** A student-heavy sample from one city; phones carried differently by different
people; labelling effort varies by person and by day.

**Privacy.** People are identified only by the dataset's random UUIDs. Per-minute derived data is
not committed (DECISIONS D8); E3 commits up to five sampled false-positive minutes per person
(UUID, local time, reported labels, scores), which are already public in the dataset.
