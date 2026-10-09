"""Geometry engine for the Crane Graph working-range diagram.

Pure Python (no Qt) so it can be unit tested. All lengths are metres.
Angles are degrees measured counter-clockwise from the +X axis; the Y
axis points up, y = 0 is ground level.

The crane sits at a pivot point (crane_x, crane_y) on the XY axis. The
boom rises from the pivot at a boom angle. In the jib configurations a
jib (or extended jib) is pinned to the boom tip at a fixed offset angle,
so the whole boom + jib assembly is a rigid body that rotates about the
pivot; the tip therefore always traces a circular arc centred on the
pivot as the boom angle sweeps its envelope.
"""

import math

__all__ = [
    "GeometryError",
    "CONFIGS",
    "CONFIG_BOOM",
    "CONFIG_BOOM_JIB",
    "CONFIG_BOOM_EXT_JIB",
    "CONFIG_LABELS",
    "ANGLE_MIN",
    "ANGLE_MAX",
    "DEFAULT_STATE",
    "clamp",
    "normalize_angle",
    "effective_jib_length",
    "boom_tip",
    "assembly_tip",
    "tip_offset_from_pivot",
    "envelope_radius",
    "envelope_points",
    "angle_for_tip",
    "working_radius",
    "tip_height",
    "tip_for_state",
    "readouts",
]


class GeometryError(ValueError):
    """Raised for invalid inputs so the GUI can show a friendly message."""


CONFIG_BOOM = "boom"
CONFIG_BOOM_JIB = "boom_jib"
CONFIG_BOOM_EXT_JIB = "boom_ext_jib"

CONFIGS = (CONFIG_BOOM, CONFIG_BOOM_JIB, CONFIG_BOOM_EXT_JIB)

CONFIG_LABELS = {
    CONFIG_BOOM: "Boom length",
    CONFIG_BOOM_JIB: "Boom length + jib",
    CONFIG_BOOM_EXT_JIB: "Boom length + extended jib",
}

# Absolute mechanical limits of the boom angle (deg from horizontal).
ANGLE_MIN = 0.0
ANGLE_MAX = 85.0

DEFAULT_STATE = {
    "config": CONFIG_BOOM,
    "boom_length": 30.0,
    "jib_length": 12.0,
    "ext_jib_length": 24.0,
    "jib_offset": 0.0,
    "angle": 45.0,
    "env_min": 0.0,
    "env_max": 80.0,
    "crane_x": 0.0,
    "crane_y": 0.0,
}


def clamp(value, lo, hi):
    """Constrain `value` to the inclusive range [lo, hi]."""
    if lo > hi:
        raise GeometryError("clamp: lower bound exceeds upper bound.")
    return lo if value < lo else hi if value > hi else value


def normalize_angle(angle_deg):
    """Wrap an angle to the range [-180, 180)."""
    return (angle_deg + 180.0) % 360.0 - 180.0


def effective_jib_length(config, jib_length, ext_jib_length):
    """Jib length in metres for the selected boom configuration.

    boom            -> 0 (no jib fitted)
    boom_jib        -> jib_length
    boom_ext_jib    -> ext_jib_length
    """
    if config == CONFIG_BOOM:
        return 0.0
    if config == CONFIG_BOOM_JIB:
        length = float(jib_length)
    elif config == CONFIG_BOOM_EXT_JIB:
        length = float(ext_jib_length)
    else:
        raise GeometryError(f"Unknown configuration: {config!r}")
    if length < 0:
        raise GeometryError("Jib length cannot be negative.")
    return length


def boom_tip(pivot, boom_length, angle_deg):
    """World coordinates of the boom tip."""
    if boom_length < 0:
        raise GeometryError("Boom length cannot be negative.")
    a = math.radians(angle_deg)
    return (pivot[0] + boom_length * math.cos(a),
            pivot[1] + boom_length * math.sin(a))


def assembly_tip(pivot, boom_length, jib_length, jib_offset_deg, angle_deg):
    """World coordinates of the free end of the boom + jib assembly.

    With no jib this is the boom tip; otherwise it is the jib tip, the
    jib being pinned at the boom tip at `jib_offset_deg` relative to the
    boom axis.
    """
    tip = boom_tip(pivot, boom_length, angle_deg)
    if jib_length <= 0:
        return tip
    a = math.radians(angle_deg + jib_offset_deg)
    return (tip[0] + jib_length * math.cos(a),
            tip[1] + jib_length * math.sin(a))


def tip_offset_from_pivot(boom_length, jib_length, jib_offset_deg):
    """Tip position relative to the pivot at boom angle 0 (assembly frame).

    Because the boom + jib assembly is rigid, the world tip is simply
    this offset rotated by the boom angle.
    """
    if boom_length < 0 or jib_length < 0:
        raise GeometryError("Boom and jib lengths cannot be negative.")
    a = math.radians(jib_offset_deg)
    return (boom_length + jib_length * math.cos(a),
            jib_length * math.sin(a))


def envelope_radius(boom_length, jib_length, jib_offset_deg):
    """Distance from pivot to the assembly tip = envelope arc radius (m)."""
    vx, vy = tip_offset_from_pivot(boom_length, jib_length, jib_offset_deg)
    return math.hypot(vx, vy)


def envelope_points(pivot, radius, angle_min, angle_max, steps=72):
    """Points along the tip envelope arc from angle_min to angle_max."""
    if radius < 0:
        raise GeometryError("Envelope radius cannot be negative.")
    if steps < 1:
        raise GeometryError("Envelope needs at least one step.")
    pts = []
    for i in range(steps + 1):
        a = math.radians(angle_min + (angle_max - angle_min) * i / steps)
        pts.append((pivot[0] + radius * math.cos(a),
                    pivot[1] + radius * math.sin(a)))
    return pts


def angle_for_tip(pivot, boom_length, jib_length, jib_offset_deg, target):
    """Boom angle (deg) that places the assembly tip on `target`.

    Inverse of `assembly_tip`, used when the user drags the tip handle
    on the graph. The result is normalized to [-180, 180); callers
    should clamp it to [ANGLE_MIN, ANGLE_MAX].
    """
    vx, vy = tip_offset_from_pivot(boom_length, jib_length, jib_offset_deg)
    if math.hypot(vx, vy) < 1e-9:
        raise GeometryError("Boom length must be greater than 0.")
    base = math.degrees(math.atan2(vy, vx))
    target_ang = math.degrees(math.atan2(target[1] - pivot[1],
                                          target[0] - pivot[0]))
    return normalize_angle(target_ang - base)


def working_radius(pivot, tip):
    """Working radius (m) = horizontal distance from crane to tip."""
    return abs(tip[0] - pivot[0])


def tip_height(tip):
    """Tip height (m) above ground level (y = 0)."""
    return tip[1]


def tip_for_state(state):
    """World coordinates of the active tip for a full state dict."""
    pivot = (state["crane_x"], state["crane_y"])
    jib = effective_jib_length(state["config"], state["jib_length"],
                               state["ext_jib_length"])
    return assembly_tip(pivot, state["boom_length"], jib,
                        state["jib_offset"], state["angle"])


def readouts(state):
    """Derived values for the readout panel.

    Returns a dict with the active jib length, assembly tip position,
    working radius, heights and envelope radius.
    """
    pivot = (state["crane_x"], state["crane_y"])
    jib = effective_jib_length(state["config"], state["jib_length"],
                               state["ext_jib_length"])
    tip = assembly_tip(pivot, state["boom_length"], jib,
                       state["jib_offset"], state["angle"])
    boom_end = boom_tip(pivot, state["boom_length"], state["angle"])
    return {
        "config": state["config"],
        "jib_active": jib > 0,
        "jib_length": jib,
        "pivot": pivot,
        "boom_end": boom_end,
        "tip": tip,
        "working_radius": working_radius(pivot, tip),
        "tip_height": tip_height(tip),
        "boom_tip_height": tip_height(boom_end),
        "height_above_crane": tip[1] - pivot[1],
        "envelope_radius": envelope_radius(
            state["boom_length"], jib, state["jib_offset"]),
        "below_ground": tip[1] < 0,
    }
