# Design: Cadence console

**Purpose.** A temporal sensor analytics interface: for any person, see their test days as a
timeline of motion, anomaly score, alarms and true anomalies, select a minute or an event, and see
why it scored as it did. Then see the study's answers (ablation, false positives) as evidence.

**Users.** A researcher checking whether alarms make sense; a reviewer of the study.

**Pages.** Timelines (people table) → person timeline (day picker, three-lane chart, minute
inspector with per-sensor explanation, event table); Ablation (interval chart per model, paired
tests); False positives (category lifts, sampled examples); Experiments (every result with
provenance); Method.

**Visual language.** Paper or graphite surfaces, hairline rules, one teal accent for selection and
focus. Model series colours (blue, orange, green, violet, ochre) appear only where models are
compared. Ground-truth anomalies are amber: solid for novel activities, hatched for off-schedule, so
the two kinds differ in more than colour. Alarms are red ticks; red and green carry a ✕ / ✓ glyph.

**Accessibility.** Keyboard: the timeline chart is focusable and the arrow keys move the selected
minute (Shift for 30-minute steps); every table row action is a button. The minute inspector is a
polite live region. Charts have text alternatives with their counts. Tested with axe in both themes
and at phone width.

**Honesty rules.** Nothing is drawn without a result: a missing experiment shows "Status: pending"
and the command that produces it. Every page with numbers shows the result directory and commit.
