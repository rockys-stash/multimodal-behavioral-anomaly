import numpy as np
import pytest

from behavlab import detectors
from behavlab.evaluate import k_of_n, measure, score_user
from behavlab.fusion import fuse
from behavlab.stats import holm, mean_ci, paired
from behavlab.truth import ground_truth
from tests.conftest import synthetic_user


def test_fusion_fits_on_reference_only_and_weights_blocks_equally(user) -> None:  # type: ignore[no-untyped-def]
    t = ground_truth(user)
    f1 = fuse(user, ("acc", "gyro", "time"), t.reference)
    user.features["acc"][t.test] += 100.0  # a change on test minutes must not move the scaling
    f2 = fuse(user, ("acc", "gyro", "time"), t.reference)
    ref = t.reference
    assert np.allclose(f1.X[ref], f2.X[ref])
    norms = {m: float((f1.X[ref][:, s] ** 2).sum(axis=1).mean()) for m, s in f1.blocks.items()}
    assert all(abs(v - 1.0) < 1e-9 for v in norms.values())  # equal weight despite 4 vs 3 vs 2 columns


def test_knn_contributions_sum_to_one_and_match_the_distance() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 6))
    knn = detectors.KNN(k=5).fit(X)
    q = rng.normal(size=(20, 6)) * 3
    c = knn.contributions(q, {"a": slice(0, 2), "b": slice(2, 6)})
    assert np.allclose(c["a"] + c["b"], 1.0)
    big = q.copy()
    big[:, :2] += 50  # an outlier in block a only
    assert (knn.contributions(big, {"a": slice(0, 2), "b": slice(2, 6)})["a"] > 0.9).all()


@pytest.mark.parametrize("name", detectors.DETECTORS)
def test_threshold_gives_about_the_nominal_alarm_rate_on_normal_data(name: str) -> None:
    rng = np.random.default_rng(1)
    X = rng.normal(size=(1200, 5))
    half = np.arange(1200) < 600
    thr = detectors.threshold(name, X, half)
    fresh = rng.normal(size=(4000, 5))
    rate = (detectors.make(name).fit(X).score(fresh) > thr).mean()
    assert 0.01 < rate < 0.12


def test_scoring_detects_an_injected_novel_activity() -> None:
    u = synthetic_user()
    test_day = np.flatnonzero(u.day() == 5)
    run = test_day[58:63]  # five minutes around noon
    from behavlab.data import MAIN

    for k in MAIN:
        u.labels[k][run] = 0
    u.labels["FIX_running"][run] = 1
    u.ts[run] = u.ts[run[0]] + 60 * np.arange(len(run))  # consecutive minutes: one event
    u.features["acc"][run] = 5.0
    u.features["gyro"][run] = 3.0
    sc = score_user(u, "C", "knn", explain=True)
    assert sc is not None and sc.contributions is not None
    m = measure(sc, u.ts)
    assert m["events"] == 1 and m["event_recall"] == 1.0 and m["auroc"] > 0.95
    assert m["latency_min"] == 0.0


def test_k_of_n_needs_persistence() -> None:
    over = np.array([True, False, True, True, False, False, True])
    ts = np.arange(7) * 60
    assert k_of_n(over, ts, 1, 1).tolist() == over.tolist()
    assert k_of_n(over, ts, 2, 3).tolist() == [False, False, True, True, True, False, False]


def test_stats_helpers() -> None:
    assert holm([0.01, 0.04, None, 0.03]) == [0.03, 0.06, None, 0.06]
    ci = mean_ci([0.5, 0.6, 0.7, None])
    assert ci["n"] == 3 and abs(ci["mean"] - 0.6) < 1e-9 and ci["lo"] <= 0.6 <= ci["hi"]
    a = {str(i): 0.5 for i in range(10)}
    b = {str(i): 0.6 + i * 0.01 for i in range(10)}
    t = paired(a, b)
    assert t["better"] == 10 and t["p"] < 0.01
