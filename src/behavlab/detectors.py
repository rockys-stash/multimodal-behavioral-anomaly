"""Anomaly detectors fitted on one person's reference minutes. Higher score = more anomalous.

- ``knn``: mean Euclidean distance to the k nearest reference minutes. Squared distance is a sum
  over features, so each score splits exactly into per-modality shares: the explanation shown for
  an event.
- ``iforest``: isolation forest (scikit-learn), seeded.
- ``gauss``: Mahalanobis distance under a Ledoit-Wolf shrunk covariance.

``threshold`` is set from reference data only: the detector is cross-fitted on the two halves of
the reference days, each half scored by the model fitted on the other, and the alarm threshold is
the (1 - ``ALARM_RATE``) quantile of those out-of-sample scores. No test label is used.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import NearestNeighbors

Array = NDArray[np.float64]
ALARM_RATE = 0.05
DETECTORS = ("knn", "iforest", "gauss")
DETECTOR_LABEL = {"knn": "k-nearest neighbours", "iforest": "Isolation forest", "gauss": "Gaussian (Mahalanobis)"}


class Detector(Protocol):
    def fit(self, X: Array) -> Detector: ...
    def score(self, X: Array) -> Array: ...


class KNN:
    def __init__(self, k: int = 10, seed: int = 0) -> None:
        self.k = k
        self._ref: Array | None = None

    def fit(self, X: Array) -> KNN:
        self._ref = X
        self._nn = NearestNeighbors(n_neighbors=min(self.k, len(X))).fit(X)
        return self

    def neighbours(self, X: Array) -> NDArray[np.int64]:
        return self._nn.kneighbors(X, return_distance=False)

    def score(self, X: Array) -> Array:
        d, _ = self._nn.kneighbors(X)
        return d.mean(axis=1)

    def contributions(self, X: Array, blocks: dict[str, slice]) -> dict[str, Array]:
        """Per-modality share of the mean squared distance to the k neighbours (rows sum to 1)."""
        assert self._ref is not None
        idx = self.neighbours(X)
        diff2 = (X[:, None, :] - self._ref[idx]) ** 2  # (n, k, features)
        parts = {m: diff2[:, :, s].sum(axis=2).mean(axis=1) for m, s in blocks.items()}
        total = np.maximum(sum(parts.values()), 1e-12)
        return {m: v / total for m, v in parts.items()}


class IForest:
    def __init__(self, seed: int = 0) -> None:
        self.model = IsolationForest(n_estimators=200, random_state=seed)

    def fit(self, X: Array) -> IForest:
        self.model.fit(X)
        return self

    def score(self, X: Array) -> Array:
        return -self.model.score_samples(X)


class Gauss:
    def __init__(self, seed: int = 0) -> None:
        self.cov = LedoitWolf()

    def fit(self, X: Array) -> Gauss:
        self.cov.fit(X)
        return self

    def score(self, X: Array) -> Array:
        return np.sqrt(np.maximum(self.cov.mahalanobis(X), 0.0))


def make(name: str, seed: int = 0, k: int = 10) -> KNN | IForest | Gauss:
    if name == "knn":
        return KNN(k=k, seed=seed)
    if name == "iforest":
        return IForest(seed=seed)
    if name == "gauss":
        return Gauss(seed=seed)
    raise ValueError(f"unknown detector {name!r}")


def reference_scores(name: str, X_ref: Array, half: NDArray[np.bool_], seed: int = 0, k: int = 10) -> Array:
    """Out-of-sample scores of the reference minutes: two-fold cross-fit over reference days."""
    scores = np.empty(len(X_ref))
    for fold in (True, False):
        train, held = half != fold, half == fold
        if train.sum() < 20 or held.sum() == 0:  # too little reference data to cross-fit: in-sample
            return make(name, seed, k).fit(X_ref).score(X_ref)
        scores[held] = make(name, seed, k).fit(X_ref[train]).score(X_ref[held])
    return scores


def threshold(name: str, X_ref: Array, half: NDArray[np.bool_], seed: int = 0, rate: float = ALARM_RATE) -> float:
    """Alarm threshold: the (1 - rate) quantile of the out-of-sample reference scores."""
    return float(np.quantile(reference_scores(name, X_ref, half, seed), 1 - rate))
