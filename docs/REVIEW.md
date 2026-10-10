# Internal review board

Reviewed 2026-10-10 against [REPORT.md](REPORT.md) and the runs at commit `ef4e2b8`.
**Overall: pass.**

| Reviewer | Verdict | Required fixes |
|---|---|---|
| Research | Pass | Two reporting fixes made before sign-off (below) |
| Engineering | Pass | None open |
| QA | Pass | None open |
| Security | Pass | None open |
| UX | Pass | Two layout fixes made before sign-off (below) |
| Recruiter | Pass | None open |
| PhD supervisor | Pass | None open |

## Research reviewer

*Is this scientifically defensible?*

- The anomaly definition is operational, per person, and fixed before any detector ran (D2);
  detectors and thresholds never see labels (D3).
- The ablation compares models on the same minutes per person, with paired tests over people and
  Holm correction; extensions (accelerometer + time, C + location) separate effects the A/B/C chain
  confounds and are labelled as extensions.
- Null and negative results are reported as results: the gyroscope adds nothing, persistence rules
  are dominated by a stricter threshold, detection overall is weak (AUROC about 0.6).
- Fixes required in review and made: the E1 table showed 57 people next to AUROC means that
  average over the 49 people with anomalies (the table now shows both counts); E5's Holm family is
  smaller than E1's, so a comparison could read "significant" in E5 and not in E1 (now stated in the
  run and the report, with E1 as the primary analysis). Neither fix changed a number; the rerun
  reproduced the first run exactly.
- An interpretation that was not tested (false alarms reflect phone motion more than personal
  routine) is marked as inferred.

## Engineering reviewer

- One command per stage (`make experiments`, `make smoke`, `make screenshots`); versioned runs
  with config, commit, dirty flag and dataset hash; failed runs never become `LATEST`.
- Fitting uses reference minutes only everywhere (scaling, block weights, detectors, thresholds).
- mypy strict on `src`, `tests` and `scripts`; ruff; ESLint; CI runs tests, the smoke pipeline,
  the console build and browser tests.

## QA reviewer

- 14 unit and API tests (synthetic people with known anomalies, exact explanation shares, event
  segmentation, threshold behaviour, API guards) and 22 browser tests pass.
- axe-core reports no WCAG 2.1 A/AA violations in light or dark mode.
- 18 real screenshots from the running console with the measured results.

## Security reviewer

- Read-only API; a non-loopback bind needs a token; per-client rate limit; CSP and other headers;
  person IDs validated against a UUID pattern before any file access.
- The dataset is CC BY-NC-SA and is not redistributed; per-minute derived outputs are not
  committed (D8). No secrets in the repository.

## UX reviewer

- The timeline shows motion, score, threshold, alarms and truth on one time axis, and each minute
  can be explained by sensor share, which makes the ablation's question tangible.
- Fixes required in review and made: the minute details grid misaligned labels and values; the
  ablation chart's type grew with the panel width. Both fixed and screenshots recaptured.
- On phones the ablation chart's type is small; the paired-test table below it carries the same
  numbers.

## Recruiter reviewer

- The README opens with the question, the measured table and five findings, including the weak
  overall detection, then how to run it and screenshots.

## PhD supervisor reviewer

- Hypotheses are judged one by one against evidence, with "partly supported" and "not supported"
  where that is what the data say.
- Threats to validity are specific (self-reported labels, four reference days, feature summaries,
  one population), and future work follows from them.
