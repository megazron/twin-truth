/* GENERATED FROM truth.yaml BY twin-truth. DO NOT EDIT. Edit the truth file and regenerate. */
#ifndef TWIN_TRUTH_GENERATED_H
#define TWIN_TRUTH_GENERATED_H

/* home_pose_left: rad; measured 2026-08-29; solved by IK search as the presentation pose (2026-08-15); captured on the left arm 2026-08-29 */
#define HOME_POSE_LEFT_N 7
static const double HOME_POSE_LEFT[7] = {0.0, 0.2618, 3.1, -2.2689, 0.0, 0.9599, 1.5708};
#define HOME_POSE_LEFT_TOL 0.001

/* home_pose_right: rad; measured 2026-08-29; mirror of the left presentation pose; joint_7 stored wrapped (was 265.75 deg) */
#define HOME_POSE_RIGHT_N 7
static const double HOME_POSE_RIGHT[7] = {0.0, -0.2618, -3.1, -2.2689, 0.0, -0.9599, -1.6449};
#define HOME_POSE_RIGHT_TOL 0.001

/* link_j1_j2_mm: mm; measured 2026-09-06; tape; convention-dependent because joint_1 is a roll */
#define LINK_J1_J2_MM 37.0
#define LINK_J1_J2_MM_TOL 1.5

/* link_j2_j4_mm: mm; measured 2026-09-06; tape on the built master arm, bend axis to bend axis */
#define LINK_J2_J4_MM 80.0
#define LINK_J2_J4_MM_TOL 1.5

/* link_j4_j6_mm: mm; measured 2026-09-06; tape on the built master arm, bend axis to bend axis */
#define LINK_J4_J6_MM 79.0
#define LINK_J4_J6_MM_TOL 1.5

/* wearer_upper_arm_mm: mm; measured 2026-08-15; tape, acromion to lateral epicondyle, default wearer */
#define WEARER_UPPER_ARM_MM 300.0
#define WEARER_UPPER_ARM_MM_TOL 5.0

/* work_plane_m: m; measured 2026-08-18; tape from the floor to the table top with the rig standing */
#define WORK_PLANE_M 1.1
#define WORK_PLANE_M_TOL 0.005

#endif /* TWIN_TRUTH_GENERATED_H */
