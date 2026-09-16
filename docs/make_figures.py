#!/usr/bin/env python3
"""Regenerate every figure under docs/img/.

    python3 docs/make_figures.py

Needs matplotlib for the PNGs. `five_places.svg` is written directly.
`scan_demo.png` runs the real `twin-truth check` on the example repo and
renders whatever it printed, so the picture cannot drift from the tool.
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "img")
os.makedirs(OUT, exist_ok=True)

# one palette
INK = "#1f2933"
MUTED = "#7b8794"
ACCENT = "#0b7285"      # teal: the truth / measured
ACCENT2 = "#e8590c"     # orange: the copy / the fault
LIGHT = "#e3fafc"
GRID = "#e5e9ee"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "savefig.dpi": 150,
})


# --------------------------------------------------------------------- 1
def five_places():
    """BEFORE / AFTER diagram, written as SVG by hand."""
    W, H = 1180, 560
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="DejaVu Sans, Helvetica, Arial, sans-serif" font-size="13">',
         f'<rect width="{W}" height="{H}" fill="white"/>',
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
         f'<path d="M0 0L10 5L0 10z" fill="{MUTED}"/></marker>'
         '<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
         f'<path d="M0 0L10 5L0 10z" fill="{ACCENT2}"/></marker>'
         '<marker id="ag" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">'
         f'<path d="M0 0L10 5L0 10z" fill="{ACCENT}"/></marker></defs>']

    def box(x, y, w, h, title, sub="", stroke=MUTED, fill="white", bold=False, dash=False):
        d = ' stroke-dasharray="6 4"' if dash else ""
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"{d}/>')
        fw = ' font-weight="bold"' if bold else ""
        s.append(f'<text x="{x+w/2}" y="{y+ (h/2 - 4 if sub else h/2 + 5)}" text-anchor="middle" fill="{INK}"{fw}>{title}</text>')
        if sub:
            s.append(f'<text x="{x+w/2}" y="{y+h/2+14}" text-anchor="middle" fill="{MUTED}" font-size="11">{sub}</text>')

    def arrow(x1, y1, x2, y2, color=MUTED, marker="a", dash=False, width=1.5):
        d = ' stroke-dasharray="5 4"' if dash else ""
        s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" marker-end="url(#{marker})"{d}/>')

    def label(x, y, t, color=INK, size=13, anchor="start", bold=False, italic=False):
        fw = ' font-weight="bold"' if bold else ""
        fi = ' font-style="italic"' if italic else ""
        s.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" text-anchor="{anchor}"{fw}{fi}>{t}</text>')

    # ---- BEFORE (left half) ----
    label(30, 36, "BEFORE: the home pose typed into five places", bold=True, size=15)
    label(30, 56, "each copy guarded by a comment: \"keep in step with the config file\"", color=MUTED, size=12, italic=True)
    places = [
        (40, 90, "config/home_positions_*.txt", "declared source, 5 consumers", False),
        (40, 160, "srl_dual.urdf.xacro (left)", "initial_positions block", False),
        (40, 230, "srl_dual.urdf.xacro (right)", "initial_positions block", False),
        (40, 300, "pot_bridge.py", "hard-coded copy", True),
        (40, 370, "srl_teleop_node.py", "hard-coded copy", True),
    ]
    for x, y, t, sub, bad in places:
        box(x, y, 250, 52, t, sub, stroke=ACCENT2 if bad else MUTED, fill="#fff4e6" if bad else "white")
    # "keep in step" dashed comments between them
    for y in (142, 212, 282, 352):
        arrow(165, y + 0, 165, y + 18, color=MUTED, dash=True)
    s.append(f'<text x="176" y="156" fill="{MUTED}" font-size="10" font-style="italic"># keep these in step</text>')
    # arm controllers
    box(360, 315, 180, 52, "arm controllers", "/left_arm_controller ...", stroke=ACCENT2, bold=True)
    arrow(290, 326, 360, 334, color=ACCENT2, marker="ar", width=2)
    arrow(290, 396, 360, 352, color=ACCENT2, marker="ar", width=2)
    label(365, 300, "publish straight to the metal", color=ACCENT2, size=11, bold=True)
    # the event
    s.append(f'<rect x="40" y="445" width="500" height="70" rx="6" fill="#fff4e6" stroke="{ACCENT2}"/>')
    label(56, 468, "2026-08-15: home moved after the task set was re-measured.", color=INK, size=12, bold=True)
    label(56, 486, "Two of the five copies were installed executables no launch file referenced.", color=INK, size=12)
    label(56, 503, "Nothing exercised them; each was one `ros2 run` away from driving the superseded pose.", color=INK, size=12)

    # divider
    s.append(f'<line x1="590" y1="30" x2="590" y2="530" stroke="{GRID}" stroke-width="2"/>')

    # ---- AFTER (right half) ----
    label(620, 36, "AFTER: one dated owner, generated everywhere, drift is a red build", bold=True, size=15)
    box(620, 80, 230, 110, "", "", stroke=ACCENT, fill=LIGHT)
    label(735, 100, "truth.yaml", anchor="middle", bold=True)
    for i, t in enumerate(["value: [0.0, 0.26, 3.10, ...]", "unit: rad   tolerance: 0.001",
                           "measured_on: 2026-08-29", "method: \"captured on the arm\""]):
        s.append(f'<text x="632" y="{124 + i*16}" fill="{INK}" font-size="11" font-family="DejaVu Sans Mono, monospace">{t}</text>')
    # generate
    arrow(850, 135, 905, 135, color=ACCENT, marker="ag", width=2)
    label(858, 124, "twin-truth", color=ACCENT, size=10, bold=True)
    label(858, 150, "generate", color=ACCENT, size=10, bold=True)
    outs = ["truth.xacro", "truth.py", "truth.json", "truth.h"]
    for i, t in enumerate(outs):
        y = 68 + i * 40
        box(910, y, 130, 30, t, stroke=ACCENT, fill="white")
        s.append(f'<text x="1046" y="{y+20}" fill="{MUTED}" font-size="10">DO NOT EDIT</text>')
    # consumers
    box(910, 240, 240, 34, "URDF, nodes, launch files, firmware", "", stroke=MUTED)
    arrow(975, 218, 975, 240, color=MUTED)
    label(1160, 262, "", size=1)
    # check
    box(620, 250, 230, 60, "twin-truth check", "scan + validate + stale", stroke=ACCENT, fill=LIGHT, bold=True)
    s.append(f'<rect x="620" y="340" width="530" height="120" rx="6" fill="#f8f9fa" stroke="{MUTED}"/>')
    label(636, 362, "the whole repo, every commit (CI)", color=MUTED, size=11, italic=True)
    for i, (t, bad) in enumerate([("src/nodes/homing_node.py      loads generated/truth.py         ok", False),
                                  ("src/nodes/legacy_bridge.py:7  copy of home_pose_left           FAIL", True),
                                  ("urdf/table.xacro:5            literal 1.100 = work_plane_m     FAIL", True)]):
        s.append(f'<text x="636" y="{388 + i*22}" fill="{ACCENT2 if bad else INK}" font-size="11.5" '
                 f'font-family="DejaVu Sans Mono, monospace"{" font-weight=\"bold\"" if bad else ""}>{t}</text>')
    arrow(735, 310, 735, 340, color=ACCENT, marker="ag", width=2)
    s.append(f'<rect x="620" y="480" width="530" height="40" rx="6" fill="#fff4e6" stroke="{ACCENT2}"/>')
    label(636, 505, "exit 1: a pasted pose or a retyped height is a red build with a file and a line number.", color=INK, size=12, bold=True)
    s.append("</svg>")
    open(os.path.join(OUT, "five_places.svg"), "w").write("\n".join(s))


# --------------------------------------------------------------------- 2
def cad_vs_measured():
    links = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]
    meas = [43, 37, 43, 37, 43, 36, 33]
    cad = [28.0, 37.7, 42.3, 36.7, 40.3, 38.7, 41.3]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [2.2, 1]})
    x = np.arange(len(links))
    w = 0.38
    ax1.bar(x - w/2, meas, w, color=ACCENT, label="measured (tape, the URDF source)")
    ax1.bar(x + w/2, cad, w, color="#c3d6db", edgecolor=ACCENT, label="CAD-inferred")
    for i, (m, c) in enumerate(zip(meas, cad)):
        d = c - m
        ax1.text(i, max(m, c) + 0.8, f"{d:+.1f}", ha="center", fontsize=9,
                 color=ACCENT2 if abs(d) > 5 else MUTED, fontweight="bold" if abs(d) > 5 else None)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{l}\n{j}" for l, j in zip(links, ["base→J1", "J1→J2", "J2→J3", "J3→J4", "J4→J5", "J5→J6", "J6→J7"])], fontsize=9)
    ax1.set_ylabel("link length (mm)")
    ax1.set_ylim(0, 53)
    ax1.set_title("Per-link lengths: convention-dependent at the roll joints", fontsize=11, loc="left")
    ax1.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    ax1.grid(axis="y", color=GRID)
    ax1.set_axisbelow(True)
    ax1.annotate("where a ROLL frame sits along its own\naxis is a drawing convention, so L1 and L7\nabsorb most of the 7 mm chain difference",
                 xy=(6.2, 41.3), xytext=(1.6, 46.0), fontsize=8.5, color=INK,
                 arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))

    spans = ["J2 → J4", "J4 → J6"]
    sm = [80.0, 79.0]
    sc = [79.0, 79.0]
    x2 = np.arange(2)
    ax2.bar(x2 - w/2, sm, w, color=ACCENT)
    ax2.bar(x2 + w/2, sc, w, color="#c3d6db", edgecolor=ACCENT)
    for i, (m, c) in enumerate(zip(sm, sc)):
        ax2.text(i, max(m, c) + 1.0, f"{c - m:+.1f} mm", ha="center", fontsize=9, color=MUTED)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(spans)
    ax2.set_ylim(0, 92)
    ax2.set_title("Bend-to-bend spans: convention-free", fontsize=11, loc="left")
    ax2.grid(axis="y", color=GRID)
    ax2.set_axisbelow(True)
    ax2.text(0.5, 8, "a bend axis is a line at a definite place;\nthe distance between two of them does not\ndepend on any frame choice. Tape and CAD\nagree to about 1 %.",
             ha="center", fontsize=8.5, color=INK, transform=ax2.transData)
    fig.suptitle("The built master arm against its CAD: what `urdf-diff` compares first", fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "cad_vs_measured.png"))
    plt.close(fig)


# --------------------------------------------------------------------- 3
def scan_demo():
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    p = subprocess.run([sys.executable, "-m", "twin_truth.cli", "check", "examples/truth.yaml",
                        "--root", "examples/demo_repo"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    text = (p.stdout + p.stderr).rstrip("\n")
    lines = ["$ twin-truth check examples/truth.yaml --root examples/demo_repo"] + text.splitlines() + [f"$ echo $?", str(p.returncode)]
    n = len(lines)
    fig = plt.figure(figsize=(12.5, 0.26 * n + 0.9))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, color="#1e1e1e", transform=ax.transAxes))
    y0 = 1 - 0.55 / (0.26 * n + 0.9)
    step = 0.26 / (0.26 * n + 0.9)
    for i, ln in enumerate(lines):
        y = y0 - i * step
        if ln.startswith("$ "):
            color, weight = "#9cdcfe", "bold"
        elif "copy of" in ln:
            color, weight = "#ff8a65", "bold"
            ax.add_patch(plt.Rectangle((0.005, y - step * 0.75), 0.99, step * 0.98, color="#3a2a22", transform=ax.transAxes))
        elif "CHECK FAILED" in ln or ln.strip() == "1":
            color, weight = "#ff5252", "bold"
        elif ln.startswith("=="):
            color, weight = "#dcdcaa", "bold"
        elif "STALE" in ln:
            color, weight = "#ffd54f", "normal"
        else:
            color, weight = "#d4d4d4", "normal"
        ax.text(0.012, y, ln.replace("$", r"\$"), family="DejaVu Sans Mono", fontsize=8.6, color=color,
                fontweight=weight, transform=ax.transAxes, va="baseline")
    fig.savefig(os.path.join(OUT, "scan_demo.png"))
    plt.close(fig)


# --------------------------------------------------------------------- 4
def wrap_seam():
    fig, ax = plt.subplots(figsize=(6.4, 6.0), subplot_kw={"projection": "polar"})
    ax.set_theta_zero_location("E")
    ax.set_theta_direction(1)
    ax.set_rticks([])
    ax.set_thetagrids(range(0, 360, 45), labels=[f"{d}°" if d <= 180 else f"{d-360}°" for d in range(0, 360, 45)], fontsize=9)
    ax.grid(color=GRID)
    ax.spines["polar"].set_color(MUTED)
    th = np.radians(265.75)
    th_w = np.radians(-94.25)
    # the seam
    ax.plot([np.pi, np.pi], [0, 1.0], color=ACCENT2, lw=2.5)
    ax.text(np.radians(163), 1.02, "±π seam\n(stored range\nends here)", ha="center", va="center", fontsize=8.5, color=ACCENT2, fontweight="bold")
    # the pose (same physical angle)
    ax.plot([0, th], [0, 0.9], color=ACCENT, lw=3)
    ax.plot(th, 0.9, "o", color=ACCENT, ms=9)
    ax.text(th, 1.0, "the pose", ha="center", fontsize=10, color=ACCENT, fontweight="bold")
    # the wrong route: from 0 going +265.75 (long way)
    a1 = np.linspace(0, th, 120)
    ax.plot(a1, np.full_like(a1, 0.55), color=ACCENT2, lw=2, ls="--")
    ax.annotate("", xy=(th, 0.55), xytext=(a1[-6], 0.55), arrowprops=dict(arrowstyle="-|>", color=ACCENT2, lw=2))
    ax.text(np.radians(135), 0.44, "stored as +265.75°:\nthe controller travels\n265.75° the long way\nround, through the seam",
            ha="center", va="center", fontsize=8.5, color=ACCENT2)
    # the right route: from 0 going -94.25 (short way)
    a2 = np.linspace(0, th_w, 80)
    ax.plot(a2, np.full_like(a2, 0.72), color=ACCENT, lw=2)
    ax.annotate("", xy=(th_w, 0.72), xytext=(a2[-6], 0.72), arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=2))
    ax.text(np.radians(-40), 0.86, "stored as −94.25°:\nthe short way,\ninside ±π", ha="center", va="center", fontsize=8.5, color=ACCENT)
    ax.plot(0, 0, "o", color=INK, ms=6)
    ax.text(0.02, 0.06, "0°", fontsize=9, color=INK)
    ax.set_rmax(1.25)
    fig.suptitle("Continuous joints are stored wrapped inside ±π, or the validator refuses",
                 fontsize=11, x=0.02, ha="left")
    fig.text(0.02, 0.02, "Same physical pose, two encodings. On the real arm the unwrapped one either blocks bring-up\n"
             "or is commanded as a 360° move at every start. The rig stored a right-arm joint_7 at 265.75° once.",
             fontsize=8.5, color=INK)
    fig.subplots_adjust(top=0.9, bottom=0.12)
    fig.savefig(os.path.join(OUT, "wrap_seam.png"))
    plt.close(fig)


# --------------------------------------------------------------------- 5
def stale_claims():
    import yaml
    truth = yaml.safe_load(open(os.path.join(ROOT, "examples", "truth.yaml")))
    today = dt.date(2026, 9, 16)      # the day the example was written; fixed so the figure is reproducible
    days = 30
    rows = []
    for name, c in truth["constants"].items():
        d = c.get("measured_on")
        if isinstance(d, str):
            d = dt.date.fromisoformat(d)
        rows.append((name, d, c.get("method", "")))
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(11, 4.4))
    start = today - dt.timedelta(days=45)
    thresh = today - dt.timedelta(days=days)
    ax.axvspan(start, thresh, color="#fff4e6", zorder=0)
    ax.axvspan(thresh, today, color=LIGHT, zorder=0)
    ax.axvline(thresh, color=ACCENT2, lw=2)
    ax.text(thresh, len(rows) - 0.35, f"  stale after {days} days", color=ACCENT2, fontsize=9, fontweight="bold", va="center")
    ax.axvline(today, color=INK, lw=1)
    ax.text(today, len(rows) - 0.35, " today  ", color=INK, fontsize=9, ha="right", va="center")
    for i, (name, d, method) in enumerate(rows):
        stale = d < thresh
        col = ACCENT2 if stale else ACCENT
        ax.hlines(i, d, today, color=col, lw=6, alpha=0.25)
        ax.plot(d, i, "o", color=col, ms=9, zorder=3)
        ax.text(d, i + 0.28, d.isoformat(), fontsize=8, color=col, ha="center")
        ax.text(start + dt.timedelta(days=0.5), i, name, fontsize=9.5, va="center", ha="left",
                color=INK, fontweight="bold" if stale else None)
        ax.text(today + dt.timedelta(days=0.6), i, ("STALE, re-measure  " if stale else "fresh  ") + f"({(today - d).days} d)",
                fontsize=8.5, va="center", color=col)
    ax.set_yticks([])
    ax.set_ylim(-1.9, len(rows) - 0.1)
    ax.set_xlim(start, today + dt.timedelta(days=12))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    ax.spines["left"].set_visible(False)
    ax.set_title("A claim about the physical world is a fact with a date: `twin-truth stale --days 30`", fontsize=11, loc="left")
    ax.text(start, -1.8, "Two standing claims on the rig, \"domain 0 is polluted\" and \"the right arm's home was never read from hardware\", "
            "were both false when finally re-measured.\nA workaround built on the first split the system in half for weeks. Undated claims are listed too.",
            fontsize=8.2, color=INK, va="bottom")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "stale_claims.png"))
    plt.close(fig)


if __name__ == "__main__":
    five_places()
    cad_vs_measured()
    scan_demo()
    wrap_seam()
    stale_claims()
    print("wrote", sorted(os.listdir(OUT)))
