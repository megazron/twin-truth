"""GENERATED FROM truth.yaml BY twin-truth. DO NOT EDIT. Edit the truth file and regenerate."""
from __future__ import annotations

import math as _math

HOME_POSE_LEFT = [0.0, 0.2618, 3.1, -2.2689, 0.0, 0.9599, 1.5708]  # rad, measured 2026-08-29
HOME_POSE_RIGHT = [0.0, -0.2618, -3.1, -2.2689, 0.0, -0.9599, -1.6449]  # rad, measured 2026-08-29
LINK_J1_J2_MM = 37.0  # mm, measured 2026-09-06
LINK_J2_J4_MM = 80.0  # mm, measured 2026-09-06
LINK_J4_J6_MM = 79.0  # mm, measured 2026-09-06
WEARER_UPPER_ARM_MM = 300.0  # mm, measured 2026-08-15
WORK_PLANE_M = 1.1  # m, measured 2026-08-18

META = {
    "home_pose_left": {
        "continuous_joints": [
            0,
            2,
            4,
            6
        ],
        "kind": "joint_pose",
        "measured_on": "2026-08-29",
        "method": "solved by IK search as the presentation pose (2026-08-15); captured on the left arm 2026-08-29",
        "tolerance": 0.001,
        "unit": "rad"
    },
    "home_pose_right": {
        "continuous_joints": [
            0,
            2,
            4,
            6
        ],
        "kind": "joint_pose",
        "measured_on": "2026-08-29",
        "method": "mirror of the left presentation pose; joint_7 stored wrapped (was 265.75 deg)",
        "tolerance": 0.001,
        "unit": "rad"
    },
    "link_j1_j2_mm": {
        "continuous_joints": [],
        "kind": "length",
        "measured_on": "2026-09-06",
        "method": "tape; convention-dependent because joint_1 is a roll",
        "tolerance": 1.5,
        "unit": "mm"
    },
    "link_j2_j4_mm": {
        "continuous_joints": [],
        "kind": "length",
        "measured_on": "2026-09-06",
        "method": "tape on the built master arm, bend axis to bend axis",
        "tolerance": 1.5,
        "unit": "mm"
    },
    "link_j4_j6_mm": {
        "continuous_joints": [],
        "kind": "length",
        "measured_on": "2026-09-06",
        "method": "tape on the built master arm, bend axis to bend axis",
        "tolerance": 1.5,
        "unit": "mm"
    },
    "wearer_upper_arm_mm": {
        "continuous_joints": [],
        "kind": "size",
        "measured_on": "2026-08-15",
        "method": "tape, acromion to lateral epicondyle, default wearer",
        "tolerance": 5.0,
        "unit": "mm"
    },
    "work_plane_m": {
        "continuous_joints": [],
        "kind": "height",
        "measured_on": "2026-08-18",
        "method": "tape from the floor to the table top with the rig standing",
        "tolerance": 0.005,
        "unit": "m"
    }
}


def get(name: str):
    """Value of a constant by its truth-file name."""
    return globals()[name.upper()]


def meta(name: str) -> dict:
    """Unit, kind, tolerance, date and method of a constant."""
    return META[name]


def as_rad(name: str):
    """A joint_pose or angle in radians whatever unit it was declared in."""
    v, m = get(name), META[name]
    if m["unit"].lower() == "deg":
        return [_math.radians(x) for x in v] if isinstance(v, list) else _math.radians(v)
    return v
