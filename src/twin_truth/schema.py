"""The truth file: schema, loading and validation.

A truth file declares every physical constant of a robot ONCE, with a unit,
a date it was measured on, how it was measured and a tolerance. Everything
else in the repository is generated from it or checked against it.

    version: 1
    allow: ["docs/**"]                 # globs the scanner may skip
    constants:
      home_pose_left:
        value: [0.0, 0.26, 3.14, -2.27, 0.0, 0.96, 1.57]
        unit: rad
        kind: joint_pose
        continuous_joints: [0, 2, 4, 6]
        measured_on: 2026-08-15
        method: "IK search; captured on the arm 2026-08-29"
        tolerance: 0.001
      work_plane_m:
        {value: 1.100, unit: m, kind: height, measured_on: 2026-08-18,
         method: tape, tolerance: 0.005}
"""
from __future__ import annotations

import datetime as _dt
import math
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

KINDS = ("joint_pose", "length", "height", "offset", "angle", "size", "other")
UNITS = {
    "rad", "deg", "m", "mm", "cm", "kg", "g", "s", "ms", "hz", "n", "nm",
    "ratio", "count", "1", "",
}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class TruthError(ValueError):
    """The truth file is not usable. The message says which key and why."""


@dataclass
class Constant:
    name: str
    value: Any                      # float or list[float]
    unit: str
    kind: str = "other"
    measured_on: _dt.date | None = None
    method: str = ""
    tolerance: float | None = None
    continuous_joints: list[int] = field(default_factory=list)
    consumers: list[str] = field(default_factory=list)
    urdf_joints: list[str] | None = None
    urdf_span: list[str] | None = None
    scan: bool | None = None
    note: str = ""

    # ---- derived
    @property
    def is_list(self) -> bool:
        return isinstance(self.value, list)

    @property
    def values(self) -> list[float]:
        return list(self.value) if self.is_list else [self.value]

    @property
    def significant_digits(self) -> int:
        """Significant digits of the value as written (max over a list)."""
        return max(_sig_digits(v) for v in self.values)

    def scannable(self) -> bool:
        """Whether the text scanner should look for this constant's literal.

        Explicit `scan:` wins. Otherwise only constants with four or more
        significant digits are searched for, so `1.0` does not light up an
        entire repository.
        """
        if self.scan is not None:
            return self.scan
        return self.significant_digits >= 4 or self.is_list


@dataclass
class Truth:
    constants: dict[str, Constant]
    allow: list[str] = field(default_factory=list)
    version: int = 1
    source: str = ""

    def __getitem__(self, name: str) -> Constant:
        return self.constants[name]

    def __iter__(self):
        return iter(self.constants.values())

    def poses(self) -> list[Constant]:
        return [c for c in self if c.kind == "joint_pose"]

    def scalars(self) -> list[Constant]:
        return [c for c in self if not c.is_list]


# ----------------------------------------------------------------- helpers
def _sig_digits(v: Any) -> int:
    s = repr(float(v))
    if "e" in s or "E" in s:
        s = s.split("e")[0].split("E")[0]
    s = s.lstrip("-").replace(".", "").lstrip("0").rstrip("0")
    return len(s) if s else 1


def _parse_date(raw: Any, key: str) -> _dt.date | None:
    if raw is None:
        return None
    if isinstance(raw, _dt.datetime):
        return raw.date()
    if isinstance(raw, _dt.date):
        return raw
    try:
        return _dt.date.fromisoformat(str(raw))
    except ValueError as e:
        raise TruthError(f"{key}.measured_on: {raw!r} is not an ISO date (YYYY-MM-DD)") from e


def _num(raw: Any, key: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise TruthError(f"{key}: value must be a number or a list of numbers, got {raw!r}")
    v = float(raw)
    if math.isnan(v) or math.isinf(v):
        raise TruthError(f"{key}: value must be finite, got {raw!r}")
    return v


def wrapped(a: float) -> float:
    """Angle wrapped into (-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


# ------------------------------------------------------------------ parsing
def parse_constant(name: str, raw: Any) -> Constant:
    key = f"constants.{name}"
    if not NAME_RE.match(name):
        raise TruthError(f"{key}: names are lower_snake_case identifiers")
    if not isinstance(raw, dict):
        raise TruthError(f"{key}: must be a mapping with at least value and unit")
    unknown = set(raw) - {
        "value", "unit", "kind", "measured_on", "method", "tolerance",
        "continuous_joints", "consumers", "urdf_joints", "urdf_span", "scan", "note",
    }
    if unknown:
        raise TruthError(f"{key}: unknown field(s) {sorted(unknown)}")
    if "value" not in raw:
        raise TruthError(f"{key}: missing value")
    if "unit" not in raw:
        raise TruthError(f"{key}: missing unit (use rad, deg, m, mm, ...)")

    v = raw["value"]
    if isinstance(v, list):
        if not v:
            raise TruthError(f"{key}: value list is empty")
        value: Any = [_num(x, f"{key}.value[{i}]") for i, x in enumerate(v)]
    else:
        value = _num(v, f"{key}.value")

    unit = str(raw["unit"]).strip()
    if unit.lower() not in UNITS:
        raise TruthError(f"{key}.unit: {unit!r} is not a known unit ({sorted(u for u in UNITS if u)})")

    kind = str(raw.get("kind", "other"))
    if kind not in KINDS:
        raise TruthError(f"{key}.kind: {kind!r} must be one of {KINDS}")

    tol = raw.get("tolerance")
    if tol is None:
        raise TruthError(f"{key}: missing tolerance -- a physical constant without a tolerance cannot be checked")
    tol = _num(tol, f"{key}.tolerance")
    if tol < 0:
        raise TruthError(f"{key}.tolerance: must be >= 0")

    cj = raw.get("continuous_joints", [])
    if cj and kind != "joint_pose":
        raise TruthError(f"{key}: continuous_joints is only meaningful for kind: joint_pose")
    if not isinstance(cj, list) or any(not isinstance(i, int) or isinstance(i, bool) for i in cj):
        raise TruthError(f"{key}.continuous_joints: must be a list of integer joint indices")

    if kind == "joint_pose":
        if not isinstance(value, list):
            raise TruthError(f"{key}: a joint_pose value must be a list of joint angles")
        if unit.lower() not in ("rad", "deg"):
            raise TruthError(f"{key}: a joint_pose is in rad or deg, not {unit!r}")
        for i in cj:
            if i < 0 or i >= len(value):
                raise TruthError(f"{key}.continuous_joints: index {i} is outside the {len(value)}-joint pose")
            a = value[i] if unit.lower() == "rad" else math.radians(value[i])
            if abs(a) > math.pi + max(tol if unit.lower() == 'rad' else math.radians(tol), 1e-9):
                wrapped_val = wrapped(a) if unit.lower() == "rad" else math.degrees(wrapped(a))
                raise TruthError(
                    f"{key}: joint index {i} is continuous and stored at {value[i]:g} {unit}, "
                    f"outside +/-pi. Store it wrapped as {wrapped_val:.4g} {unit}. "
                    "A home stored outside the seam either blocks real bring-up or commands a "
                    "360 deg move at every start.")

    for fld in ("urdf_joints", "urdf_span"):
        lst = raw.get(fld)
        if lst is not None:
            if not isinstance(lst, list) or len(lst) != 2 or not all(isinstance(s, str) for s in lst):
                raise TruthError(f"{key}.{fld}: must be a list of exactly two joint names")
            if kind not in ("length", "offset", "height", "size"):
                raise TruthError(f"{key}.{fld}: only meaningful for a length-like constant")

    consumers = raw.get("consumers", [])
    if not isinstance(consumers, list):
        raise TruthError(f"{key}.consumers: must be a list")

    scan = raw.get("scan")
    if scan is not None and not isinstance(scan, bool):
        raise TruthError(f"{key}.scan: must be true or false")

    return Constant(
        name=name, value=value, unit=unit, kind=kind,
        measured_on=_parse_date(raw.get("measured_on"), key),
        method=str(raw.get("method", "") or ""),
        tolerance=tol,
        continuous_joints=list(cj),
        consumers=[str(c) for c in consumers],
        urdf_joints=raw.get("urdf_joints"),
        urdf_span=raw.get("urdf_span"),
        scan=scan,
        note=str(raw.get("note", "") or ""),
    )


def parse_truth(doc: Any, source: str = "") -> Truth:
    if not isinstance(doc, dict):
        raise TruthError("truth file must be a mapping with `version` and `constants`")
    version = doc.get("version", 1)
    if version != 1:
        raise TruthError(f"version {version!r} is not supported (this tool reads version 1)")
    consts = doc.get("constants")
    if not isinstance(consts, dict) or not consts:
        raise TruthError("`constants` must be a non-empty mapping")
    allow = doc.get("allow", []) or []
    if not isinstance(allow, list) or not all(isinstance(a, str) for a in allow):
        raise TruthError("`allow` must be a list of glob patterns")
    unknown = set(doc) - {"version", "constants", "allow"}
    if unknown:
        raise TruthError(f"unknown top-level key(s) {sorted(unknown)}")
    parsed = {name: parse_constant(str(name), raw) for name, raw in consts.items()}
    return Truth(constants=parsed, allow=list(allow), version=version, source=source)


def load_truth(path: str) -> Truth:
    """Load and validate a truth file. Raises TruthError with the key that is wrong."""
    with open(path, encoding="utf-8") as fh:
        try:
            doc = yaml.safe_load(fh)
        except yaml.YAMLError as e:
            raise TruthError(f"{path}: not valid YAML: {e}") from e
    return parse_truth(doc, source=path)


def validate(path: str) -> list[str]:
    """Return a list of human-readable statements about a valid file, or raise TruthError."""
    t = load_truth(path)
    out = [f"{len(t.constants)} constant(s) valid in {path}"]
    for c in t:
        when = c.measured_on.isoformat() if c.measured_on else "UNDATED"
        shape = f"{len(c.values)} values" if c.is_list else f"{c.value:g}"
        out.append(f"  {c.name:<28} {c.kind:<10} {shape} {c.unit}  tol {c.tolerance:g}  measured {when}")
    return out
