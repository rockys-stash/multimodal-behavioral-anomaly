"""Run one job per person on worker processes."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from typing import Any, TypeVar

T = TypeVar("T")


def _init() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")


def run(fn: Callable[..., T], jobs: Iterable[tuple[Any, ...]], workers: int) -> list[T]:
    jobs = list(jobs)
    if workers <= 1:
        return [fn(*j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as ex:
        return [f.result() for f in [ex.submit(fn, *j) for j in jobs]]
