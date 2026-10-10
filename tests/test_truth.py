import numpy as np

from behavlab.data import MAIN
from behavlab.truth import NORMAL, NOVEL, OFF_SCHEDULE, UNDETERMINED, events, ground_truth
from tests.conftest import synthetic_user


def test_reference_is_the_first_half_of_days(user) -> None:  # type: ignore[no-untyped-def]
    t = ground_truth(user)
    day = user.day()
    assert set(day[t.reference]) == {0, 1, 2, 3} and set(day[t.test]) == {4, 5, 6, 7}


def test_novel_and_off_schedule_are_defined_from_reference_days_only() -> None:
    u = synthetic_user()
    i_run = np.flatnonzero(u.day() == 5)[60]  # a test-day minute at 12:00 -> running (never in the reference)
    i_lie = np.flatnonzero(u.day() == 6)[75]  # a test-day minute at 15:00 -> lying (only ever at night)
    for k in MAIN:
        u.labels[k][[i_run, i_lie]] = 0
    u.labels["FIX_running"][i_run] = 1
    u.labels["LYING_DOWN"][i_lie] = 1
    i_none = np.flatnonzero(u.day() == 6)[10]
    for k in MAIN:
        u.labels[k][i_none] = -1
    t = ground_truth(u)
    assert t.kind[i_run] == NOVEL and t.kind[i_lie] == OFF_SCHEDULE
    assert t.kind[i_none] == UNDETERMINED and not t.scored[i_none]
    assert (t.kind[t.reference] == UNDETERMINED).all()
    assert (t.kind[t.test & (t.activity == 1)] == NORMAL).all()  # sitting in the day is familiar


def test_events_group_adjacent_minutes_and_split_on_gaps() -> None:
    ts = np.array([0, 60, 120, 600, 660, 720, 780])
    pos = np.array([True, True, False, True, True, False, True])
    assert events(ts, pos) == [(0, 1), (3, 4), (6, 6)]
    ts2 = np.array([0, 60, 600])  # 9-minute gap between rows 1 and 2
    assert events(ts2, np.array([True, True, True])) == [(0, 1), (2, 2)]
