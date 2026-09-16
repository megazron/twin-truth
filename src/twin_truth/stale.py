"""Which constants are claims with an old date, or no date at all.

A statement about the physical world is a fact WITH A DATE. On the rig this
tool comes from, "domain 0's shared memory is polluted" and "the right arm's
home has never been read from hardware" were both carried forward as standing
truths and both were false when re-measured. A workaround built on a stale
claim outlives its cause. So: re-measure before building on anything older
than the window, and never build on an undated value.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from .schema import Truth


@dataclass
class StaleEntry:
    name: str
    age_days: int | None        # None = undated
    measured_on: _dt.date | None
    method: str

    @property
    def status(self) -> str:
        return "UNDATED" if self.age_days is None else "STALE"


def stale(t: Truth, days: int = 30, today: _dt.date | None = None) -> list[StaleEntry]:
    today = today or _dt.date.today()
    out = []
    for c in t:
        if c.measured_on is None:
            out.append(StaleEntry(c.name, None, None, c.method))
            continue
        age = (today - c.measured_on).days
        if age > days:
            out.append(StaleEntry(c.name, age, c.measured_on, c.method))
    out.sort(key=lambda e: (-1 if e.age_days is None else 0, -(e.age_days or 0)))
    return out


def report(entries: list[StaleEntry], days: int) -> list[str]:
    if not entries:
        return [f"every constant was measured within the last {days} day(s)"]
    lines = [f"{len(entries)} constant(s) older than {days} day(s) or undated -- re-measure before building on them:"]
    for e in entries:
        when = "no measured_on" if e.age_days is None else f"{e.age_days} days old ({e.measured_on})"
        how = f"  method: {e.method}" if e.method else ""
        lines.append(f"  {e.status:<8} {e.name:<28} {when}{how}")
    return lines
