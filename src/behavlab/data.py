"""The ExtraSensory dataset: download, integrity check, loading and stream synchronisation.

ExtraSensory (Vaizman, Ellis and Lanckriet, 2017) holds one record per minute for 60 people living
their normal lives, with features already computed by the authors from each sensor's 20 s
recording that minute, and labels the person reported. We use the per-minute sensor features as
streams: phone accelerometer, phone gyroscope, location, and the timestamp. See data/DATASET.md.

Synchronisation (``load_user``): records are sorted and de-duplicated by timestamp, timestamps are
converted to the person's local time (America/Los_Angeles; checked against the dataset's own
time-of-day flags), each modality gets an availability mask, and gaps between records are kept so
that events and latencies are measured in real minutes, not in row counts.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import os
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(os.environ.get("BEHAVLAB_DATA", ROOT / "data" / "raw"))
ARCHIVE = "ExtraSensory.per_uuid_features_labels.zip"
URL = "http://extrasensory.ucsd.edu/data/primary_data_files/ExtraSensory.per_uuid_features_labels.zip"
SHA256 = "412d307bdf54a60dff81a705c2f25833889a46dca64a184e3b588ad99c69cb56"
EXPECTED_USERS, EXPECTED_RECORDS = 60, 377_346  # dataset paper, Table 1 ("60 users", "377,346 examples")
TZ = ZoneInfo("America/Los_Angeles")  # participants were in San Diego

# Column-name prefixes of each sensor modality in the per-minute feature files.
MODALITY_PREFIX = {
    "acc": ("raw_acc:",),
    "gyro": ("proc_gyro:",),
    "location": ("location:", "location_quick_features:"),
}
# The dataset's six mutually exclusive "main activity" labels (posture / movement).
MAIN = ("LYING_DOWN", "SITTING", "OR_standing", "FIX_walking", "FIX_running", "BICYCLING")
TIME_OF_DAY = ("between0and6", "between3and9", "between6and12", "between9and15",
               "between12and18", "between15and21", "between18and24", "between21and3")  # fmt: skip

Array = NDArray[np.float64]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(raw: Path = RAW, url: str = URL) -> Path:
    """Download (if needed) and verify the archive; return its path."""
    raw.mkdir(parents=True, exist_ok=True)
    archive = raw / ARCHIVE
    if not archive.exists():
        tmp = archive.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)  # fixed URL; accepted only if the hash below matches
        tmp.rename(archive)
    digest = sha256(archive)
    if digest != SHA256:
        archive.rename(archive.with_suffix(".rejected"))
        raise RuntimeError(f"{archive.name} has SHA-256 {digest}, expected {SHA256}; moved aside")
    return archive


def _archive(raw: Path) -> Path:
    a = raw / ARCHIVE
    if not a.exists():
        raise FileNotFoundError(f"{a} missing: run `behavlab fetch` (or `make data`) first")
    return a


@lru_cache(maxsize=4)
def users(raw: Path = RAW) -> tuple[str, ...]:
    with zipfile.ZipFile(_archive(raw)) as z:
        return tuple(sorted(n.split(".")[0] for n in z.namelist() if n.endswith(".features_labels.csv.gz")))


@dataclass
class UserData:
    """One person's synchronised streams. Rows are minutes in time order."""

    uuid: str
    ts: NDArray[np.int64]  # Unix seconds (UTC)
    local: list[datetime]  # local wall-clock time
    features: dict[str, Array]  # modality -> (minutes, features), NaN where missing
    feature_names: dict[str, list[str]]
    available: dict[str, NDArray[np.bool_]]  # modality -> minute has the modality
    labels: dict[str, NDArray[np.int8]]  # label -> 1 / 0 / -1 (not reported)
    tod_flags: NDArray[np.float64]  # dataset's own time-of-day flags, for the timezone check
    gap_before: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))  # minutes since previous record

    @property
    def n(self) -> int:
        return len(self.ts)

    def main_activity(self) -> NDArray[np.int64]:
        """Index into MAIN of the reported main activity, or -1 if none or ambiguous."""
        m = np.stack([self.labels[k] == 1 for k in MAIN], axis=1)
        out = np.where(m.sum(1) == 1, m.argmax(1), -1)
        return out.astype(np.int64)

    def day(self) -> NDArray[np.int64]:
        """Local calendar day index (days since the first record's local date)."""
        d0 = self.local[0].date()
        return np.array([(t.date() - d0).days for t in self.local], dtype=np.int64)


def _float(v: str) -> float:
    return float(v) if v not in ("", "nan", "NaN") else float("nan")


@lru_cache(maxsize=64)
def load_user(uuid: str, raw: Path = RAW) -> UserData:
    with zipfile.ZipFile(_archive(raw)) as z, z.open(f"{uuid}.features_labels.csv.gz") as fz:
        text = io.TextIOWrapper(gzip.GzipFile(fileobj=fz), encoding="utf-8")
        reader = csv.reader(text)
        header = next(reader)
        rows = list(reader)
    col = {c: i for i, c in enumerate(header)}
    data = np.array([[_float(v) for v in r] for r in rows], dtype=np.float64)
    ts = data[:, 0].astype(np.int64)
    order = np.argsort(ts, kind="stable")
    keep = order[np.concatenate([[True], np.diff(ts[order]) > 0])]  # one record per timestamp
    data, ts = data[keep], ts[keep]
    feats, names, avail = {}, {}, {}
    for m, prefixes in MODALITY_PREFIX.items():
        idx = [i for c, i in col.items() if c.startswith(prefixes)]
        names[m] = [header[i] for i in idx]
        feats[m] = data[:, idx]
        avail[m] = np.isfinite(feats[m]).any(axis=1)
    labels = {}
    for c, i in col.items():
        if c.startswith("label:"):
            v = data[:, i]
            labels[c.removeprefix("label:")] = np.where(np.isfinite(v), v, -1).astype(np.int8)
    tod = data[:, [col[f"discrete:time_of_day:{b}"] for b in TIME_OF_DAY]]
    local = [datetime.fromtimestamp(int(t), TZ) for t in ts]
    gap = np.concatenate([[np.inf], np.diff(ts) / 60.0])
    return UserData(uuid, ts, local, feats, names, avail, labels, tod, gap)


def temporal_features(u: UserData) -> tuple[Array, list[str]]:
    """Time of day on the circle. Weekday is left out: with four or so reference days per person a
    weekly pattern cannot be learned, and a test day of the week never seen in the reference would
    look anomalous by construction (DECISIONS D5)."""
    hour = np.array([t.hour + t.minute / 60 for t in u.local])
    return np.stack([np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)], axis=1), ["hour_sin", "hour_cos"]


def timezone_agreement(u: UserData) -> float:
    """Share of minutes whose local hour falls in exactly the time-of-day bins the dataset flags."""
    bins = [(0, 6), (3, 9), (6, 12), (9, 15), (12, 18), (15, 21), (18, 24), (21, 27)]
    ok = n = 0
    for t, flags in zip(u.local, u.tod_flags, strict=True):
        if not np.isfinite(flags).all():
            continue
        h = t.hour
        pred = np.array([a <= h < b or a <= h + 24 < b for a, b in bins])
        ok += bool((pred == (flags == 1)).all())
        n += 1
    return ok / n if n else float("nan")


def subset() -> int | None:
    """How many users ``BEHAVLAB_USERS`` limits runs to (the first N by id), or None for all of them."""
    v = os.environ.get("BEHAVLAB_USERS", "").strip()
    return int(v) if v else None


def selected_users(raw: Path = RAW) -> tuple[str, ...]:
    n = subset()
    return users(raw)[:n] if n else users(raw)
