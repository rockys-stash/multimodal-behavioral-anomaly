"""Shared fixtures. Most tests use small synthetic people so they run without the dataset;
tests marked ``needs_data`` read the real archive (``make data``)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pytest

from behavlab import data
from behavlab.data import MAIN, TZ, UserData

HAVE_DATA = (data.RAW / data.ARCHIVE).exists()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="dataset not fetched (make data)")


def synthetic_user(days: int = 8, per_day: int = 120, seed: int = 0, uuid: str = "SYNTH") -> UserData:
    """A person who sits by day and lies down at night, with motion features that follow the activity.

    Minutes are spread over each day's hours; activity: lying 0-6h, sitting otherwise, walking at noon."""
    rng = np.random.default_rng(seed)
    start = datetime(2015, 10, 5, tzinfo=TZ)
    local, acts = [], []
    for d in range(days):
        for k in range(per_day):
            t = start + timedelta(days=d, minutes=int(k * 1440 / per_day))
            local.append(t)
            h = t.hour
            acts.append(0 if h < 6 else (3 if h == 12 else 1))
    n = len(local)
    acts_a = np.array(acts)
    level = np.array([0.1, 0.2, 0.3, 1.0, 2.0, 1.5])[acts_a]
    acc = level[:, None] + rng.normal(0, 0.05, (n, 4))
    gyro = level[:, None] * 0.5 + rng.normal(0, 0.05, (n, 3))
    loc = rng.normal(0, 1, (n, 2))
    labels = {k: np.where(acts_a == i, 1, 0).astype(np.int8) for i, k in enumerate(MAIN)}
    labels["PHONE_IN_POCKET"] = np.ones(n, dtype=np.int8)
    ts = np.array([int(t.timestamp()) for t in local], dtype=np.int64)
    return UserData(
        uuid=uuid, ts=ts, local=local,
        features={"acc": acc, "gyro": gyro, "location": loc},
        feature_names={"acc": [f"raw_acc:f{i}" for i in range(4)], "gyro": [f"proc_gyro:f{i}" for i in range(3)],
                       "location": ["location:a", "location:b"]},
        available={"acc": np.ones(n, bool), "gyro": np.ones(n, bool), "location": np.ones(n, bool)},
        labels=labels, tod_flags=np.full((n, 8), np.nan), gap_before=np.concatenate([[np.inf], np.diff(ts) / 60]),
    )  # fmt: skip


@pytest.fixture
def user() -> UserData:
    return synthetic_user()
