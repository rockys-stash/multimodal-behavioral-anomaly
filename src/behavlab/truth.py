"""Ground truth: what counts as abnormal behaviour for one person.

The dataset has no "anomaly" label, so we define one from what each person reported, before
looking at any detector, and the detectors never see labels (DECISIONS D2). Each person's days are
split in time: the first half of their days is the *reference* (what is normal for them), the rest
is the *test* period. A test minute with a reported main activity is

- **novel activity** when that activity is under ``RARE`` of the person's reference minutes
  (e.g. running for someone who never ran in the reference days);
- **off schedule** when the activity is familiar but the person never did it in that three-hour
  slot of the day in the reference, and the slot has at least ``MIN_SLOT`` reference minutes, so
  we know what they normally do then (e.g. lying down at 15:00 for someone who only lies down at
  night);
- **normal** when the activity is familiar and either seen in that slot or the slot is too sparse
  to tell (in which case the minute is *undetermined* and left out of the metrics);
- **undetermined** when no single main activity was reported.

Anomalies are scored per minute and grouped into *events*: maximal runs of anomalous minutes with
no more than ``EVENT_GAP`` minutes between consecutive records.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from behavlab.data import MAIN, UserData

RARE = 0.01
MIN_SLOT = 30
SLOT_HOURS = 3
EVENT_GAP = 2.0  # minutes

NORMAL, NOVEL, OFF_SCHEDULE, UNDETERMINED = 0, 1, 2, -1
KIND = {NOVEL: "novel activity", OFF_SCHEDULE: "off schedule"}


@dataclass
class Truth:
    reference: NDArray[np.bool_]  # minute is in the reference period
    kind: NDArray[np.int64]  # NORMAL / NOVEL / OFF_SCHEDULE / UNDETERMINED for test minutes; UNDETERMINED in reference
    activity: NDArray[np.int64]  # main activity index or -1
    slot: NDArray[np.int64]

    @property
    def test(self) -> NDArray[np.bool_]:
        return ~self.reference

    @property
    def scored(self) -> NDArray[np.bool_]:
        return self.test & (self.kind != UNDETERMINED)

    @property
    def anomalous(self) -> NDArray[np.bool_]:
        return self.kind > 0


def split_days(u: UserData) -> NDArray[np.bool_]:
    """Reference = minutes on the first half of the person's distinct recording days."""
    day = u.day()
    days = np.unique(day)
    cut = days[(len(days) - 1) // 2]  # with 8 days, days[0..3] are reference
    return day <= cut


def ground_truth(u: UserData, rare: float = RARE, min_slot: int = MIN_SLOT) -> Truth:
    ref = split_days(u)
    act = u.main_activity()
    slot = np.array([t.hour // SLOT_HOURS for t in u.local], dtype=np.int64)
    known_ref = ref & (act >= 0)
    n_ref = max(int(known_ref.sum()), 1)
    share = np.array([(act[known_ref] == a).sum() / n_ref for a in range(len(MAIN))])
    slot_total = np.array([(known_ref & (slot == s)).sum() for s in range(24 // SLOT_HOURS)])
    seen = np.zeros((24 // SLOT_HOURS, len(MAIN)), dtype=bool)
    for s, a in zip(slot[known_ref], act[known_ref], strict=True):
        seen[s, a] = True
    kind = np.full(u.n, UNDETERMINED, dtype=np.int64)
    for i in np.flatnonzero(~ref & (act >= 0)):
        a, s = act[i], slot[i]
        if share[a] < rare:
            kind[i] = NOVEL
        elif not seen[s, a] and slot_total[s] >= min_slot:
            kind[i] = OFF_SCHEDULE
        elif seen[s, a]:
            kind[i] = NORMAL
    return Truth(ref, kind, act, slot)


def events(ts: NDArray[np.int64], positive: NDArray[np.bool_], gap: float = EVENT_GAP) -> list[tuple[int, int]]:
    """Maximal runs [start, end] (row indices, inclusive) of adjacent positive rows with small time gaps."""
    out: list[tuple[int, int]] = []
    start = prev = -1
    for i in np.flatnonzero(positive).tolist():
        if start >= 0 and i == prev + 1 and (ts[i] - ts[prev]) / 60.0 <= gap:
            prev = i
            continue
        if start >= 0:
            out.append((start, prev))
        start = prev = i
    if start >= 0:
        out.append((start, prev))
    return out
