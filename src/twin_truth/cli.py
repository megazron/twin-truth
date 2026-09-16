"""twin-truth command line.

    twin-truth validate  truth.yaml
    twin-truth generate  truth.yaml --out-dir generated/ [--formats xacro,python,json,yaml,c]
    twin-truth scan      truth.yaml --root . [--exclude build/]...
    twin-truth urdf-diff truth.yaml robot.urdf [--base-link base_link]
    twin-truth stale     truth.yaml [--days 30]
    twin-truth check     truth.yaml --root . [--days 30] [--exclude ...]

Exit codes: 0 clean, 1 a finding (copy found / urdf FAIL / validation error), 2 usage.
"""
from __future__ import annotations

import argparse
import sys

from . import generate as _gen
from . import scan as _scan
from . import stale as _stale
from . import urdf as _urdf
from .schema import TruthError, load_truth, validate


def _p(lines):
    for ln in lines:
        print(ln)


def cmd_validate(a) -> int:
    try:
        _p(validate(a.truth))
    except TruthError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_generate(a) -> int:
    try:
        t = load_truth(a.truth)
    except TruthError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    formats = [f.strip() for f in a.formats.split(",") if f.strip()]
    try:
        paths = _gen.generate(t, a.out_dir, formats)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    for p in paths:
        print(f"wrote {p}")
    return 0


def cmd_scan(a) -> int:
    try:
        t = load_truth(a.truth)
    except TruthError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    findings = _scan.scan(t, a.root, a.exclude)
    _p(_scan.report(findings, a.root))
    return 1 if findings else 0


def cmd_urdf_diff(a) -> int:
    try:
        t = load_truth(a.truth)
        rows = _urdf.urdf_diff(t, a.urdf, a.base_link)
    except (TruthError, _urdf.UrdfError) as e:
        print(str(e), file=sys.stderr)
        return 1
    _p(_urdf.report(rows, a.urdf))
    return 0 if all(r.ok for r in rows) else 1


def cmd_stale(a) -> int:
    try:
        t = load_truth(a.truth)
    except TruthError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    entries = _stale.stale(t, a.days)
    _p(_stale.report(entries, a.days))
    return 1 if (entries and a.strict) else 0


def cmd_check(a) -> int:
    rc = 0
    print("== validate")
    try:
        _p(validate(a.truth))
        t = load_truth(a.truth)
    except TruthError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print("\n== scan")
    findings = _scan.scan(t, a.root, a.exclude)
    _p(_scan.report(findings, a.root))
    if findings:
        rc = 1
    print("\n== stale (warning only)")
    _p(_stale.report(_stale.stale(t, a.days), a.days))
    print("\n" + ("CHECK FAILED" if rc else "CHECK PASSED"))
    return rc


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="twin-truth", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("validate", help="schema, units, wrapped continuous joints, dates, tolerances")
    s.add_argument("truth")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("generate", help="emit xacro/python/json/yaml/c from the truth file")
    s.add_argument("truth")
    s.add_argument("--out-dir", default="generated")
    s.add_argument("--formats", default=",".join(_gen.FORMATS))
    s.set_defaults(fn=cmd_generate)

    s = sub.add_parser("scan", help="find copies of the truth outside the truth file")
    s.add_argument("truth")
    s.add_argument("--root", default=".")
    s.add_argument("--exclude", action="append", default=[], help="glob relative to root; repeatable")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("urdf-diff", help="compare URDF joint geometry with measured lengths")
    s.add_argument("truth")
    s.add_argument("urdf")
    s.add_argument("--base-link", default=None)
    s.set_defaults(fn=cmd_urdf_diff)

    s = sub.add_parser("stale", help="constants older than N days, or undated")
    s.add_argument("truth")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--strict", action="store_true", help="exit 1 if anything is stale")
    s.set_defaults(fn=cmd_stale)

    s = sub.add_parser("check", help="validate + scan + stale, for CI")
    s.add_argument("truth")
    s.add_argument("--root", default=".")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--exclude", action="append", default=[])
    s.set_defaults(fn=cmd_check)
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
