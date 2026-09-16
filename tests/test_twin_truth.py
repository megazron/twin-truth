import datetime as dt
import math
import os
import textwrap

import pytest
import yaml

from twin_truth import cli, generate, scan, stale, urdf
from twin_truth.schema import TruthError, load_truth, parse_truth

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(os.path.dirname(HERE), "examples")

POSE = [0.0, 0.2618, 3.1, -2.2689, 0.0, 0.9599, 1.5708]


def base_doc(**extra):
    doc = {
        "version": 1,
        "constants": {
            "home_pose_left": {
                "value": list(POSE), "unit": "rad", "kind": "joint_pose",
                "continuous_joints": [0, 2, 4, 6], "measured_on": "2026-08-29",
                "method": "captured", "tolerance": 0.001,
            },
            "work_plane_m": {"value": 1.100, "unit": "m", "kind": "height",
                             "measured_on": "2026-08-18", "tolerance": 0.005, "scan": True},
            "wearer_upper_arm_mm": {"value": 300.0, "unit": "mm", "kind": "size",
                                    "measured_on": "2026-08-15", "tolerance": 5.0},
        },
    }
    doc.update(extra)
    return doc


def write_truth(tmp_path, doc, name="truth.yaml"):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(doc))
    return str(p)


# ------------------------------------------------------------------ schema
def test_valid_file_loads(tmp_path):
    t = load_truth(write_truth(tmp_path, base_doc()))
    assert set(t.constants) == {"home_pose_left", "work_plane_m", "wearer_upper_arm_mm"}
    assert t["home_pose_left"].is_list and t["work_plane_m"].value == 1.1
    assert t["home_pose_left"].measured_on == dt.date(2026, 8, 29)


@pytest.mark.parametrize("mutate, needle", [
    (lambda d: d["constants"]["work_plane_m"].pop("tolerance"), "missing tolerance"),
    (lambda d: d["constants"]["work_plane_m"].pop("unit"), "missing unit"),
    (lambda d: d["constants"]["work_plane_m"].update(unit="furlong"), "not a known unit"),
    (lambda d: d["constants"]["work_plane_m"].update(kind="banana"), "must be one of"),
    (lambda d: d["constants"]["work_plane_m"].update(measured_on="yesterday"), "not an ISO date"),
    (lambda d: d["constants"]["work_plane_m"].update(bogus=1), "unknown field"),
    (lambda d: d["constants"]["work_plane_m"].update(value="1.1"), "must be a number"),
    (lambda d: d["constants"]["work_plane_m"].update(continuous_joints=[0]), "only meaningful for kind: joint_pose"),
    (lambda d: d["constants"]["home_pose_left"].update(value=1.0), "must be a list"),
    (lambda d: d["constants"].update({"Bad-Name": {"value": 1, "unit": "m", "tolerance": 0.1}}), "lower_snake_case"),
    (lambda d: d.update(version=2), "not supported"),
])
def test_validation_errors_name_the_key(tmp_path, mutate, needle):
    d = base_doc()
    mutate(d)
    with pytest.raises(TruthError) as ei:
        load_truth(write_truth(tmp_path, d))
    assert needle in str(ei.value)


def test_continuous_joint_outside_pi_is_refused_and_told_the_wrapped_value(tmp_path):
    d = base_doc()
    d["constants"]["home_pose_left"]["unit"] = "deg"
    d["constants"]["home_pose_left"]["value"] = [0, 15, 177, -130, 0, 55, 265.75]
    with pytest.raises(TruthError) as ei:
        load_truth(write_truth(tmp_path, d))
    msg = str(ei.value)
    assert "joint index 6" in msg and "265.75" in msg and "-94.25" in msg


def test_continuous_joint_check_ignores_non_continuous_joints(tmp_path):
    d = base_doc()
    d["constants"]["home_pose_left"]["value"] = [0.0, 0.2618, 3.1, -2.2689, 0.0, 4.0, 1.5708]  # idx 5 not continuous
    load_truth(write_truth(tmp_path, d))  # no raise


# ---------------------------------------------------------------- generate
def test_generate_every_format_is_deterministic_and_bannered(tmp_path):
    t = load_truth(write_truth(tmp_path, base_doc()))
    out = tmp_path / "gen"
    paths = generate.generate(t, str(out))
    assert sorted(os.path.basename(p) for p in paths) == sorted(
        ["truth.xacro", "truth.py", "truth.json", "truth.generated.yaml", "truth.h"])
    first = {p: open(p).read() for p in paths}
    generate.generate(t, str(out))
    assert {p: open(p).read() for p in paths} == first
    for content in first.values():
        assert "GENERATED FROM truth.yaml" in content and "DO NOT EDIT" in content


def test_generated_xacro_has_list_and_per_element_properties(tmp_path):
    t = load_truth(write_truth(tmp_path, base_doc()))
    x = generate.gen_xacro(t)
    assert '<xacro:property name="home_pose_left" value="0.0 0.2618 3.1 -2.2689 0.0 0.9599 1.5708"/>' in x
    assert '<xacro:property name="home_pose_left_6" value="1.5708"/>' in x
    assert '<xacro:property name="work_plane_m" value="1.1"/>' in x


def test_generated_python_module_imports_and_converts(tmp_path):
    t = load_truth(write_truth(tmp_path, base_doc()))
    src = generate.gen_python(t)
    ns = {}
    exec(compile(src, "truth.py", "exec"), ns)
    assert ns["HOME_POSE_LEFT"] == POSE and ns["get"]("work_plane_m") == 1.1
    assert ns["meta"]("home_pose_left")["continuous_joints"] == [0, 2, 4, 6]
    assert ns["as_rad"]("home_pose_left") == POSE


def test_generated_c_header(tmp_path):
    t = load_truth(write_truth(tmp_path, base_doc()))
    h = generate.gen_c(t)
    assert "#define HOME_POSE_LEFT_N 7" in h
    assert "static const double HOME_POSE_LEFT[7] = {0.0, 0.2618, 3.1, -2.2689, 0.0, 0.9599, 1.5708};" in h
    assert "#define WORK_PLANE_M 1.1" in h and "#define WORK_PLANE_M_TOL 0.005" in h


def test_generated_json_roundtrips(tmp_path):
    import json
    t = load_truth(write_truth(tmp_path, base_doc()))
    d = json.loads(generate.gen_json(t))
    assert d["constants"]["home_pose_left"]["value"] == POSE
    assert d["constants"]["work_plane_m"]["measured_on"] == "2026-08-18"


# -------------------------------------------------------------------- scan
def make_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "build").mkdir()
    return repo


def test_ast_scan_catches_home_dict_value_and_ignores_offsets(tmp_path):
    truth = write_truth(tmp_path, base_doc())
    repo = make_repo(tmp_path)
    (repo / "src" / "bridge.py").write_text(textwrap.dedent("""
        class B:
            def __init__(self):
                self.home = {"left": [0.0, 0.2618, 3.1, -2.2689, 0.0, 0.9599, 1.5708]}
                self.start_offset_deg = [5.0, -5.0, 5.0, 0.0, 0.0, 0.0, 0.0]
                other = [0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
    """))
    t = load_truth(truth)
    f = scan.scan(t, str(repo))
    assert len(f) == 1
    assert f[0].constant == "home_pose_left" and f[0].line == 4 and f[0].path == "src/bridge.py"


def test_ast_scan_flags_pose_shaped_list_under_pose_name_even_with_new_numbers(tmp_path):
    """Structural: a NEW pose pasted under a pose-like name still fires."""
    t = load_truth(write_truth(tmp_path, base_doc()))
    repo = make_repo(tmp_path)
    (repo / "src" / "n.py").write_text("HOME_Q = [1.0, 2.0, 3.0, -1.0, 0.5, 0.25, 0.125]\n")
    f = scan.scan(t, str(repo))
    assert len(f) == 1 and f[0].constant == "<declared joint_pose>"


def test_ast_scan_does_not_fire_on_values_outside_tolerance_under_neutral_name(tmp_path):
    t = load_truth(write_truth(tmp_path, base_doc()))
    repo = make_repo(tmp_path)
    (repo / "src" / "n.py").write_text("waypoint = [0.0, 0.30, 3.1, -2.2689, 0.0, 0.9599, 1.5708]\n")
    assert scan.scan(t, str(repo)) == []


def test_ast_scan_flags_matching_literal_passed_as_argument(tmp_path):
    t = load_truth(write_truth(tmp_path, base_doc()))
    repo = make_repo(tmp_path)
    (repo / "src" / "n.py").write_text("send([0.0, 0.2618, 3.1, -2.2689, 0.0, 0.9599, 1.5708])\n")
    f = scan.scan(t, str(repo))
    assert len(f) == 1 and f[0].constant == "home_pose_left"


def test_text_scan_catches_height_in_xacro_and_respects_allow_exclude_and_generated(tmp_path):
    d = base_doc(allow=["docs/**"])
    t = load_truth(write_truth(tmp_path, d))
    repo = make_repo(tmp_path)
    (repo / "src" / "table.xacro").write_text('<origin xyz="0 0 1.100"/>\n<!-- 1.100 in a comment -->\n')
    (repo / "docs" / "notes.txt").write_text("the plane is at 1.100 m\n")
    (repo / "build" / "x.yaml").write_text("z: 1.100\n")
    (repo / "src" / "vendor.yaml").write_text("z: 1.100\n")
    gen = repo / "src" / "truth.xacro"
    gen.write_text("<!-- GENERATED FROM truth.yaml BY twin-truth. DO NOT EDIT. -->\n<x v='1.100'/>\n")
    f = scan.scan(t, str(repo), excludes=["src/vendor.yaml"])
    assert [(x.path, x.line, x.constant) for x in f] == [("src/table.xacro", 1, "work_plane_m")]


def test_text_scan_skips_low_precision_constants_unless_scan_true(tmp_path):
    d = base_doc()
    d["constants"]["work_plane_m"].pop("scan")   # 1.1 has 2 significant digits
    t = load_truth(write_truth(tmp_path, d))
    repo = make_repo(tmp_path)
    (repo / "src" / "a.yaml").write_text("gain: 1.1\nlen: 300.0\n")
    assert scan.scan(t, str(repo)) == []


def test_text_scan_uses_tolerance(tmp_path):
    t = load_truth(write_truth(tmp_path, base_doc()))
    repo = make_repo(tmp_path)
    (repo / "src" / "a.yaml").write_text("z: 1.103\nw: 1.120\n")   # tol 0.005
    f = scan.scan(t, str(repo))
    assert len(f) == 1 and f[0].line == 1 and abs(f[0].delta - 0.003) < 1e-9


# -------------------------------------------------------------------- urdf
URDF = """<?xml version="1.0"?>
<robot name="t">
  <link name="base"/><link name="a"/><link name="b"/><link name="c"/>
  <joint name="j1" type="continuous"><parent link="base"/><child link="a"/><origin xyz="0 0 0.030"/></joint>
  <joint name="j2" type="revolute"><parent link="a"/><child link="b"/><origin xyz="0 0 0.040" rpy="0 1.5707963 0"/></joint>
  <joint name="j3" type="revolute"><parent link="b"/><child link="c"/><origin xyz="0 0 0.050"/></joint>
</robot>
"""


def test_urdf_diff_spans_follow_rotated_frames(tmp_path):
    u = tmp_path / "r.urdf"
    u.write_text(URDF)
    d = {"version": 1, "constants": {
        "span_j1_j3_mm": {"value": 64.0, "unit": "mm", "kind": "length", "tolerance": 1.0,
                          "measured_on": "2026-09-01", "urdf_span": ["j1", "j3"]},
        "link_j1_j2_mm": {"value": 41.0, "unit": "mm", "kind": "length", "tolerance": 0.5,
                          "measured_on": "2026-09-01", "urdf_joints": ["j1", "j2"]},
    }}
    t = load_truth(write_truth(tmp_path, d))
    rows = urdf.urdf_diff(t, str(u))
    by = {r.name: r for r in rows}
    # j2 rotates 90 deg about y, so j3's 0.05 along local z becomes world +x: sqrt(40^2 + 50^2) = 64.03
    assert abs(by["span_j1_j3_mm"].urdf - math.hypot(40, 50)) < 1e-6 and by["span_j1_j3_mm"].ok
    assert abs(by["link_j1_j2_mm"].urdf - 40.0) < 1e-9 and not by["link_j1_j2_mm"].ok
    assert rows[0].kind == "span"   # spans reported first


def test_urdf_diff_refuses_xacro_and_unknown_joint(tmp_path):
    x = tmp_path / "r.urdf.xacro"
    x.write_text(URDF)
    d = {"version": 1, "constants": {"s": {"value": 1, "unit": "mm", "kind": "length", "tolerance": 1,
                                           "measured_on": "2026-09-01", "urdf_span": ["j1", "nope"]}}}
    t = load_truth(write_truth(tmp_path, d))
    with pytest.raises(urdf.UrdfError, match="xacro"):
        urdf.urdf_diff(t, str(x))
    u = tmp_path / "r.urdf"
    u.write_text(URDF)
    with pytest.raises(urdf.UrdfError, match="nope"):
        urdf.urdf_diff(t, str(u))


# ------------------------------------------------------------------- stale
def test_stale_classification():
    t = parse_truth({"version": 1, "constants": {
        "fresh": {"value": 1.234, "unit": "m", "tolerance": 0.1, "measured_on": "2026-09-10"},
        "old": {"value": 1.234, "unit": "m", "tolerance": 0.1, "measured_on": "2026-06-01"},
        "undated": {"value": 1.234, "unit": "m", "tolerance": 0.1},
    }})
    e = stale.stale(t, days=30, today=dt.date(2026, 9, 16))
    assert [(x.name, x.status) for x in e] == [("undated", "UNDATED"), ("old", "STALE")]
    assert e[1].age_days == 107


# --------------------------------------------------------------------- cli
def test_cli_check_exit_codes_on_examples(capsys):
    truth = os.path.join(EXAMPLES, "truth.yaml")
    root = os.path.join(EXAMPLES, "demo_repo")
    assert cli.main(["validate", truth]) == 0
    assert cli.main(["check", truth, "--root", root]) == 1
    out = capsys.readouterr().out
    assert "legacy_bridge.py:7" in out and "table.xacro:5" in out and "CHECK FAILED" in out
    assert cli.main(["check", truth, "--root", root, "--exclude", "src/nodes/legacy_bridge.py",
                     "--exclude", "urdf/table.xacro"]) == 0
    assert cli.main(["urdf-diff", truth, os.path.join(root, "urdf", "master_arm.urdf")]) == 0


def test_cli_invalid_truth_is_exit_1(tmp_path, capsys):
    d = base_doc()
    d["constants"]["work_plane_m"].pop("tolerance")
    p = write_truth(tmp_path, d)
    assert cli.main(["validate", p]) == 1
    assert "INVALID" in capsys.readouterr().err


def test_cli_generate_writes_requested_formats(tmp_path):
    p = write_truth(tmp_path, base_doc())
    out = tmp_path / "g"
    assert cli.main(["generate", p, "--out-dir", str(out), "--formats", "xacro,python"]) == 0
    assert sorted(os.listdir(out)) == ["truth.py", "truth.xacro"]
    assert cli.main(["generate", p, "--out-dir", str(out), "--formats", "cobol"]) == 2
