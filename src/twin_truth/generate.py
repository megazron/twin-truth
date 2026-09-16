"""Generate the consumer files from the truth file.

Every generated file carries a banner naming its source so nobody edits it by
hand, and every generator is deterministic: same truth in, byte-identical
files out. Formats: xacro, python, json, yaml, c.
"""
from __future__ import annotations

import json
import os

import yaml

from .schema import Truth

BANNER = "GENERATED FROM {src} BY twin-truth. DO NOT EDIT. Edit the truth file and regenerate."
FORMATS = ("xacro", "python", "json", "yaml", "c")


def _src(t: Truth) -> str:
    return os.path.basename(t.source) if t.source else "truth.yaml"


def _fmt(v: float) -> str:
    return repr(float(v))


def gen_xacro(t: Truth) -> str:
    lines = [
        '<?xml version="1.0"?>',
        f"<!-- {BANNER.format(src=_src(t))} -->",
        '<robot xmlns:xacro="http://www.ros.org/wiki/xacro">',
    ]
    for c in sorted(t, key=lambda c: c.name):
        meta = f"{c.unit}; measured {c.measured_on or 'UNDATED'}; {c.method}".strip("; ")
        lines.append(f"  <!-- {c.name}: {meta} -->")
        if c.is_list:
            lines.append(f'  <xacro:property name="{c.name}" value="{" ".join(_fmt(v) for v in c.values)}"/>')
            for i, v in enumerate(c.values):
                lines.append(f'  <xacro:property name="{c.name}_{i}" value="{_fmt(v)}"/>')
        else:
            lines.append(f'  <xacro:property name="{c.name}" value="{_fmt(c.value)}"/>')
    lines.append("</robot>")
    return "\n".join(lines) + "\n"


def gen_python(t: Truth) -> str:
    lines = [
        f'"""{BANNER.format(src=_src(t))}"""',
        "from __future__ import annotations",
        "",
        "import math as _math",
        "",
    ]
    meta = {}
    for c in sorted(t, key=lambda c: c.name):
        lines.append(f"{c.name.upper()} = {c.value!r}  # {c.unit}, measured {c.measured_on or 'UNDATED'}")
        meta[c.name] = {
            "unit": c.unit, "kind": c.kind, "tolerance": c.tolerance,
            "measured_on": c.measured_on.isoformat() if c.measured_on else None,
            "method": c.method, "continuous_joints": c.continuous_joints,
        }
    lines += [
        "",
        "META = " + json.dumps(meta, indent=4, sort_keys=True),
        "",
        "",
        "def get(name: str):",
        '    """Value of a constant by its truth-file name."""',
        "    return globals()[name.upper()]",
        "",
        "",
        "def meta(name: str) -> dict:",
        '    """Unit, kind, tolerance, date and method of a constant."""',
        "    return META[name]",
        "",
        "",
        "def as_rad(name: str):",
        '    """A joint_pose or angle in radians whatever unit it was declared in."""',
        "    v, m = get(name), META[name]",
        '    if m["unit"].lower() == "deg":',
        "        return [_math.radians(x) for x in v] if isinstance(v, list) else _math.radians(v)",
        "    return v",
        "",
    ]
    return "\n".join(lines)


def _doc(t: Truth) -> dict:
    out = {"_generated": BANNER.format(src=_src(t)), "constants": {}}
    for c in sorted(t, key=lambda c: c.name):
        out["constants"][c.name] = {
            "value": c.value, "unit": c.unit, "kind": c.kind,
            "tolerance": c.tolerance,
            "measured_on": c.measured_on.isoformat() if c.measured_on else None,
            "method": c.method, "continuous_joints": c.continuous_joints,
        }
    return out


def gen_json(t: Truth) -> str:
    return json.dumps(_doc(t), indent=2, sort_keys=True) + "\n"


def gen_yaml(t: Truth) -> str:
    return f"# {BANNER.format(src=_src(t))}\n" + yaml.safe_dump(_doc(t), sort_keys=True, default_flow_style=None)


def gen_c(t: Truth) -> str:
    guard = "TWIN_TRUTH_GENERATED_H"
    lines = [f"/* {BANNER.format(src=_src(t))} */", f"#ifndef {guard}", f"#define {guard}", ""]
    for c in sorted(t, key=lambda c: c.name):
        up = c.name.upper()
        lines.append(f"/* {c.name}: {c.unit}; measured {c.measured_on or 'UNDATED'}; {c.method} */")
        if c.is_list:
            lines.append(f"#define {up}_N {len(c.values)}")
            lines.append(f"static const double {up}[{len(c.values)}] = {{{', '.join(_fmt(v) for v in c.values)}}};")
        else:
            lines.append(f"#define {up} {_fmt(c.value)}")
        lines.append(f"#define {up}_TOL {_fmt(c.tolerance)}")
        lines.append("")
    lines.append(f"#endif /* {guard} */")
    return "\n".join(lines) + "\n"


GENERATORS = {
    "xacro": ("truth.xacro", gen_xacro),
    "python": ("truth.py", gen_python),
    "json": ("truth.json", gen_json),
    "yaml": ("truth.generated.yaml", gen_yaml),
    "c": ("truth.h", gen_c),
}


def generate(t: Truth, out_dir: str, formats=FORMATS) -> list[str]:
    """Write the requested formats into out_dir; return the paths written."""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for f in formats:
        if f not in GENERATORS:
            raise ValueError(f"unknown format {f!r}; choose from {FORMATS}")
        fname, fn = GENERATORS[f]
        path = os.path.join(out_dir, fname)
        content = fn(t)
        try:
            with open(path, encoding="utf-8") as fh:
                if fh.read() == content:
                    written.append(path)
                    continue
        except FileNotFoundError:
            pass
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(path)
    return written
