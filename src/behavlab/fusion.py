"""Feature extraction and multimodal fusion.

A *model* (arm of the ablation) is a list of modalities. Each modality's per-minute features are
imputed with the reference median, robust-standardised with the reference median and IQR, clipped,
and then scaled so that every modality block carries the same weight: its mean squared norm over
the reference minutes is 1. Without that, a modality with 26 features would outweigh one with 2
simply by count (DECISIONS D4). Only reference minutes are used to fit any
transform, so test minutes never inform their own scaling.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from behavlab.data import UserData, temporal_features

Array = NDArray[np.float64]

# The spec's three models, then the extensions this study adds (labelled as such in the report).
MODELS: dict[str, tuple[str, ...]] = {
    "A": ("acc",),
    "B": ("acc", "gyro"),
    "C": ("acc", "gyro", "time"),
    "A+time": ("acc", "time"),
    "C+location": ("acc", "gyro", "time", "location"),
}
MODEL_LABEL = {
    "A": "A · accelerometer",
    "B": "B · accelerometer + gyroscope",
    "C": "C · accelerometer + gyroscope + time",
    "A+time": "accelerometer + time",
    "C+location": "C + location",
}
CLIP = 10.0


def modality(u: UserData, name: str) -> tuple[Array, list[str]]:
    if name == "time":
        return temporal_features(u)
    return u.features[name], u.feature_names[name]


def available(u: UserData, mods: tuple[str, ...]) -> NDArray[np.bool_]:
    ok = np.ones(u.n, dtype=bool)
    for m in mods:
        if m != "time":
            ok &= u.available[m]
    return ok


@dataclass
class Fused:
    X: Array  # (minutes, features) after fusion
    blocks: dict[str, slice]  # modality -> its columns in X
    names: list[str]


def fuse(u: UserData, mods: tuple[str, ...], fit_rows: NDArray[np.bool_], block_weighting: bool = True) -> Fused:
    parts, blocks, names, col = [], {}, [], 0
    for m in mods:
        raw, fnames = modality(u, m)
        ref = raw[fit_rows]
        keep = np.isfinite(ref).any(axis=0)  # drop features never observed in the reference
        raw, ref = raw[:, keep], ref[:, keep]
        fnames = [f for f, k in zip(fnames, keep, strict=True) if k]
        med = np.nanmedian(ref, axis=0)
        q75, q25 = np.nanpercentile(ref, 75, axis=0), np.nanpercentile(ref, 25, axis=0)
        iqr = q75 - q25
        sd = np.nanstd(ref, axis=0)
        scale = np.where(iqr > 1e-9, iqr / 1.349, np.where(sd > 1e-9, sd, 1.0))
        x = np.where(np.isfinite(raw), raw, med)
        x = np.clip((x - med) / scale, -CLIP, CLIP)
        if block_weighting:  # every block gets mean squared norm 1 on the reference minutes
            x = x / max(float(np.sqrt((x[fit_rows] ** 2).sum(axis=1).mean())), 1e-9)
        parts.append(x)
        blocks[m] = slice(col, col + x.shape[1])
        names += [f"{m}:{f}" for f in fnames]
        col += x.shape[1]
    return Fused(np.concatenate(parts, axis=1), blocks, names)
