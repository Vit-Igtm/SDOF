"""Small shared helpers for the Project Strikers engine."""
import math


def seg_dist(px, py, x1, y1, x2, y2):
    """Distance from point (px, py) to the segment (x1, y1)-(x2, y2)."""
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy or 1
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def abbr(name):
    w = name.replace("'", "").split()
    return (w[0][0] + w[1][0]) if len(w) > 1 else name[:2]


def calc_damage_reduction(defense):
    """0-100 defense: 0.5%/pt (to 50%), 100-200: 0.25%/pt (to 75%), then capped."""
    if defense <= 100:
        r = defense * 0.5
    elif defense <= 200:
        r = 50 + (defense - 100) * 0.25
    else:
        r = 75
    return r / 100.0


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def wrap_angle(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a
