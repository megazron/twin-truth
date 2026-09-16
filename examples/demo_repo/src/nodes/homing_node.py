"""Loads home from the generated module. This is the right way."""
from generated.truth import HOME_POSE_LEFT, as_rad

def target():
    return list(as_rad("home_pose_left"))
