"""Find copies of the truth that live outside the truth file.

Two detectors, because the two ways a copy appears are different:

* **Python, by syntax tree.** A literal list of N floats assigned to a name
  containing home/pose/q0/initial is a copy of a pose whatever its numbers
  are -- matching on the OLD numbers would pass the moment someone pasted the
  NEW pose in, which is exactly the failure being prevented. Also flagged: any
  list literal (anywhere: assignment, dict value, call argument) whose values
  match a declared pose within its tolerance.
* **Text, by number.** A literal number equal to a declared scalar within its
  tolerance, in .py .xacro .urdf .yaml .yml .json .launch.py .cfg .txt. Only
  constants with >= 4 significant digits (or `scan: true`) are searched for,
  so `1.0` does not light up the whole repository.

Generated files, the truth file itself and anything matched by the truth
file's `allow:` globs are skipped.
"""
from __future__ import annotations

import ast
import fnmatch
import os
import re
from dataclasses import dataclass

from .generate import BANNER
from .schema import Constant, Truth

TEXT_EXT = {".py", ".xacro", ".urdf", ".yaml", ".yml", ".json", ".cfg", ".txt", ".launch", ".srdf", ".xml"}
POSE_NAME_RE = re.compile(r"(home|pose|q0|initial)", re.IGNORECASE)
NUM_RE = re.compile(r"(?<![\w.])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?(?![\w.])")
DEFAULT_EXCLUDES = ("build", "install", "log", ".git", "__pycache__", "*.egg-info", ".venv", "venv", "node_modules")
BANNER_MARK = BANNER.split(" BY ")[0].split("{src}")[0].strip()   # "GENERATED FROM"


@dataclass
class Finding:
    path: str
    line: int
    constant: str
    detail: str
    delta: float | None = None

    def __str__(self) -> str:
        d = "" if self.delta is None else f" (delta {self.delta:+.4g})"
        return f"{self.path}:{self.line}: copy of `{self.constant}`{d} -- {self.detail}"


# ---------------------------------------------------------------- walking
def _is_generated(path: str) -> bool:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(600)
    except OSError:
        return False
    return BANNER_MARK in head and "twin-truth" in head


def _allowed(rel: str, patterns: list[str]) -> bool:
    rel = rel.replace(os.sep, "/")
    for p in patterns:
        p = p.replace(os.sep, "/")
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(os.path.basename(rel), p):
            return True
        # "docs/**" should also match "docs/x/y" and "docs/x"
        if p.endswith("/**") and (rel.startswith(p[:-3] + "/") or rel == p[:-3]):
            return True
    return False


def iter_files(root: str, excludes: list[str], allow: list[str], truth_path: str | None = None):
    root = os.path.abspath(root)
    truth_abs = os.path.abspath(truth_path) if truth_path else None
    ex = list(DEFAULT_EXCLUDES) + [e.rstrip("/") for e in excludes]
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir
        dirnames[:] = sorted(
            d for d in dirnames
            if not any(fnmatch.fnmatch(d, e) or fnmatch.fnmatch(os.path.join(rel_dir, d), e) for e in ex)
        )
        for fn in sorted(filenames):
            path = os.path.join(dirpath, fn)
            rel = os.path.join(rel_dir, fn) if rel_dir else fn
            if truth_abs and os.path.abspath(path) == truth_abs:
                continue
            if any(fnmatch.fnmatch(rel, e) or fnmatch.fnmatch(fn, e) for e in ex):
                continue
            if _allowed(rel, allow):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if fn.endswith(".launch.py"):
                ext = ".py"
            if ext not in TEXT_EXT:
                continue
            if _is_generated(path):
                continue
            yield path, rel


# ------------------------------------------------------------ python (AST)
def _float_list(node: ast.AST) -> list[float] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    out = []
    for el in node.elts:
        if isinstance(el, ast.UnaryOp) and isinstance(el.op, ast.USub) and isinstance(el.operand, ast.Constant):
            v = el.operand.value
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return None
            out.append(-float(v))
        elif isinstance(el, ast.Constant) and isinstance(el.value, (int, float)) and not isinstance(el.value, bool):
            out.append(float(el.value))
        else:
            return None
    return out


def _target_names(node: ast.AST) -> list[str]:
    names = []
    if isinstance(node, ast.Name):
        names.append(node.id)
    elif isinstance(node, ast.Attribute):
        names.append(node.attr)
    elif isinstance(node, ast.Subscript):
        names += _target_names(node.value)
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            names.append(node.slice.value)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for e in node.elts:
            names += _target_names(e)
    return names


def _match_pose(vals: list[float], poses: list[Constant]) -> tuple[Constant, float] | None:
    for p in poses:
        if len(p.values) != len(vals):
            continue
        worst = max(abs(a - b) for a, b in zip(vals, p.values))
        if worst <= (p.tolerance or 0.0):
            return p, worst
    return None


def scan_python(path: str, rel: str, poses: list[Constant]) -> list[Finding]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        tree = ast.parse(src, filename=path)
    except (SyntaxError, ValueError):
        return []
    lengths = {len(p.values) for p in poses}
    found: list[Finding] = []
    seen: set[tuple[int, int]] = set()

    def flag(node, const, detail, delta=None):
        key = (node.lineno, node.col_offset)
        if key in seen:
            return
        seen.add(key)
        found.append(Finding(rel, node.lineno, const, detail, delta))

    # (a) pose-shaped list assigned to a pose-like name
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [n for t in targets for n in _target_names(t)]
            value = node.value
            if value is None:
                continue
            candidates = []
            lst = _float_list(value)
            if lst is not None:
                candidates.append((lst, names, value))
            if isinstance(value, ast.Dict):
                for k, v in zip(value.keys, value.values):
                    l2 = _float_list(v)
                    if l2 is not None:
                        kname = k.value if isinstance(k, ast.Constant) and isinstance(k.value, str) else ""
                        candidates.append((l2, names + [kname], v))
            for lst, nms, node_ in candidates:
                if len(lst) in lengths and any(POSE_NAME_RE.search(n or "") for n in nms):
                    label = "/".join(n for n in nms if n)
                    m = _match_pose(lst, poses)
                    if m:
                        flag(node_, m[0].name, f"{len(lst)}-value literal assigned to a pose-like name ({label}) and equal to the truth within tolerance", m[1])
                    else:
                        flag(node_, "<declared joint_pose>",
                             f"{len(lst)}-value literal assigned to a pose-like name ({label}); a pose belongs in the truth file, not in code")
    # (b) any list literal that equals a declared pose within tolerance
    for node in ast.walk(tree):
        lst = _float_list(node)
        if lst is None or len(lst) not in lengths:
            continue
        m = _match_pose(lst, poses)
        if m:
            flag(node, m[0].name, "list literal equal to the truth within tolerance", m[1])
    return found


# --------------------------------------------------------------- text (num)
def scan_text(path: str, rel: str, scalars: list[Constant]) -> list[Finding]:
    scalars = [c for c in scalars if c.scannable()]
    if not scalars:
        return []
    found = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("<!--"):
            continue
        for m in NUM_RE.finditer(line):
            tok = m.group(0)
            if not re.search(r"[.eE]", tok):
                # bare integers are too common to be evidence; require a decimal point unless
                # the constant itself is an integer with >= 4 digits
                try:
                    iv = float(tok)
                except ValueError:
                    continue
                for c in scalars:
                    if float(c.value).is_integer() and abs(float(c.value)) >= 1000 and abs(iv - c.value) <= c.tolerance:
                        found.append(Finding(rel, i, c.name, f"literal {tok} in {os.path.splitext(rel)[1] or 'text'}", iv - c.value))
                continue
            try:
                v = float(tok)
            except ValueError:
                continue
            for c in scalars:
                # a literal is a copy only if it is written to at least the constant's precision
                if abs(v - c.value) <= c.tolerance and _sig(tok) >= min(c.significant_digits, 4):
                    found.append(Finding(rel, i, c.name, f"literal {tok} in {os.path.splitext(rel)[1] or 'text'}", v - c.value))
    return found


def _sig(tok: str) -> int:
    s = tok.lstrip("+-").split("e")[0].split("E")[0].replace(".", "").lstrip("0").rstrip("0")
    return len(s) if s else 1


# --------------------------------------------------------------------- run
def scan(t: Truth, root: str, excludes: list[str] | None = None) -> list[Finding]:
    """Every copy of a truth constant found under root, sorted by path and line."""
    excludes = list(excludes or [])
    poses = t.poses()
    scalars = t.scalars()
    findings: list[Finding] = []
    for path, rel in iter_files(root, excludes, t.allow, t.source or None):
        if rel.endswith(".py"):
            findings += scan_python(path, rel, poses)
        findings += scan_text(path, rel, scalars)
    findings.sort(key=lambda f: (f.path, f.line, f.constant))
    return findings


def report(findings: list[Finding], root: str) -> list[str]:
    if not findings:
        return [f"no copies of the truth found under {root}"]
    lines = [f"{len(findings)} copy(ies) of the truth found under {root} -- each must load the generated file instead:"]
    lines += ["  " + str(f) for f in findings]
    return lines
