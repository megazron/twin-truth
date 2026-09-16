"""A node that carries its own copy of the pose. twin-truth scan flags this."""

class Bridge:
    def __init__(self):
        # "keep in step with config/home_positions_left.txt" -- a comment cannot fail.
        self.home = {
            "left": [0.0, 0.2618, 3.1000, -2.2689, 0.0, 0.9599, 1.5708],
            "right": [0.0, -0.2618, -3.1000, -2.2689, 0.0, -0.9599, -1.6449],
        }
        # an offset FROM home, different length: not a copy, not flagged
        self.start_offset_deg = [5.0, -5.0, 5.0]
