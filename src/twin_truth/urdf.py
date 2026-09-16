"""Compare a URDF's joint geometry with the measured lengths in the truth file.

Two comparisons, and they are not equally honest:

* **Consecutive joint origins** (`urdf_joints: [joint_a, joint_b]`): the
  distance from joint_a's origin to joint_b's origin, walking the chain. Where
  a roll joint sits ALONG its own axis is a modelling convention, so a
  per-link delta can be an artefact of where the designer put a frame.
* **Convention-free spans** (`urdf_span: [joint_2, joint_4]`): the distance
  between two bend axes. A bend axis is a line at a definite place in space,
  so this number does not depend on any frame choice. It is the comparison a
  tape measure on the built arm can be trusted against.

Plain URDF only. For a xacro, run `xacro robot.urdf.xacro > robot.urdf` first.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .schema import Truth

UNIT_TO_M = {"m": 1.0, "mm": 1e-3, "cm": 1e-2}


class UrdfError(ValueError):
    pass


@dataclass
class Joint:
    name: str
    parent: str
    child: str
    xyz: tuple[float, float, float]
    rpy: tuple[float, float, float]
    jtype: str


def _mat(rpy):
    r, p, y = rpy
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    # ZYX convention as URDF: R = Rz(y) Ry(p) Rx(r)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def _mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _apply(R, v):
    return tuple(sum(R[i][k] * v[k] for k in range(3)) for i in range(3))


def parse_urdf(path: str) -> dict[str, Joint]:
    if path.endswith(".xacro"):
        raise UrdfError(f"{path} is a xacro; run `xacro {path} > robot.urdf` first and pass the plain URDF")
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise UrdfError(f"{path}: not valid XML: {e}") from e
    root = tree.getroot()
    if root.tag != "robot":
        raise UrdfError(f"{path}: root element is <{root.tag}>, expected <robot>")
    if "xacro" in (root.attrib.get("xmlns:xacro", "") + "".join(root.attrib)) or any(
            el.tag.startswith("{http://www.ros.org/wiki/xacro}") for el in root.iter()):
        raise UrdfError(f"{path} contains xacro elements; run `xacro` first and pass the plain URDF")
    joints = {}
    for j in root.findall("joint"):
        name = j.attrib.get("name")
        parent = j.find("parent").attrib["link"]
        child = j.find("child").attrib["link"]
        o = j.find("origin")
        xyz = tuple(float(x) for x in (o.attrib.get("xyz", "0 0 0").split() if o is not None else "0 0 0".split()))
        rpy = tuple(float(x) for x in (o.attrib.get("rpy", "0 0 0").split() if o is not None else "0 0 0".split()))
        joints[name] = Joint(name, parent, child, xyz, rpy, j.attrib.get("type", "fixed"))
    if not joints:
        raise UrdfError(f"{path}: no <joint> elements")
    return joints


def joint_origins_world(joints: dict[str, Joint], base_link: str | None = None) -> dict[str, tuple[float, float, float]]:
    """World position of every joint origin, chaining from the root link (or base_link)."""
    by_child = {j.child: j for j in joints.values()}
    children = {}
    for j in joints.values():
        children.setdefault(j.parent, []).append(j)
    links = set(by_child) | set(children)
    roots = [l for l in links if l not in by_child]
    start = base_link or (roots[0] if roots else None)
    if start is None:
        raise UrdfError("could not find a root link (every link has a parent -- is there a loop?)")
    pos: dict[str, tuple[float, float, float]] = {}
    stack = [(start, (0.0, 0.0, 0.0), [[1, 0, 0], [0, 1, 0], [0, 0, 1]])]
    while stack:
        link, p, R = stack.pop()
        for j in children.get(link, []):
            off = _apply(R, j.xyz)
            pj = (p[0] + off[0], p[1] + off[1], p[2] + off[2])
            pos[j.name] = pj
            stack.append((j.child, pj, _mul(R, _mat(j.rpy))))
    return pos


def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


@dataclass
class Row:
    name: str
    kind: str            # "link" or "span"
    joints: tuple[str, str]
    measured: float
    urdf: float
    unit: str
    tolerance: float

    @property
    def delta(self) -> float:
        return self.urdf - self.measured

    @property
    def ok(self) -> bool:
        return abs(self.delta) <= self.tolerance


def urdf_diff(t: Truth, urdf_path: str, base_link: str | None = None) -> list[Row]:
    joints = parse_urdf(urdf_path)
    pos = joint_origins_world(joints, base_link)
    rows = []
    for c in t:
        for fld, kind in (("urdf_joints", "link"), ("urdf_span", "span")):
            pair = getattr(c, fld)
            if not pair:
                continue
            a, b = pair
            for jn in (a, b):
                if jn not in pos:
                    raise UrdfError(f"{c.name}.{fld}: joint {jn!r} is not in {urdf_path} (have: {sorted(pos)})")
            scale = UNIT_TO_M.get(c.unit.lower())
            if scale is None:
                raise UrdfError(f"{c.name}: unit {c.unit!r} is not a length unit (m, mm, cm)")
            d_m = _dist(pos[a], pos[b])
            rows.append(Row(c.name, kind, (a, b), float(c.value), d_m / scale, c.unit, float(c.tolerance)))
    if not rows:
        raise UrdfError("no constant declares urdf_joints or urdf_span; nothing to compare")
    rows.sort(key=lambda r: (r.kind != "span", r.name))
    return rows


def report(rows: list[Row], urdf_path: str) -> list[str]:
    lines = [f"URDF {urdf_path} against the truth file", ""]
    w = max(len(r.name) for r in rows)
    lines.append(f"  {'constant':<{w}}  {'kind':<4}  {'joints':<28} {'measured':>10} {'urdf':>10} {'delta':>9}  verdict")
    for r in rows:
        js = f"{r.joints[0]} -> {r.joints[1]}"
        lines.append(f"  {r.name:<{w}}  {r.kind:<4}  {js:<28} {r.measured:>10.3f} {r.urdf:>10.3f} {r.delta:>+9.3f}  "
                     f"{'PASS' if r.ok else 'FAIL'} (tol {r.tolerance:g} {r.unit})")
    n_bad = sum(not r.ok for r in rows)
    spans = [r for r in rows if r.kind == "span"]
    lines.append("")
    if spans:
        lines.append("  spans are convention-free (bend axis to bend axis); trust them over per-link deltas,")
        lines.append("  which move with where a roll joint's frame was placed along its own axis.")
    lines.append(f"  {len(rows) - n_bad} of {len(rows)} within tolerance" + ("" if not n_bad else f"; {n_bad} FAILED"))
    return lines
