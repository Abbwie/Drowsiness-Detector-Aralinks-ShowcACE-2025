"""Feed synthetic EAR traces through the calibration + PERCLOS logic."""
import os
import sys, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# dlib is only used for face landmarks inside the live loop; stub it so the
# pure-Python PERCLOS and calibration classes can be tested without it.
sys.modules.setdefault("dlib", types.ModuleType("dlib"))

import numpy as np
from vigiwatch import (EyeCalibration, PerclosTracker, PERCLOS_WARN,
                       PERCLOS_ALERT, PERCLOS_CLOSED_LEVEL, MICROSLEEP_SECONDS)

FPS = 30.0
DT = 1.0 / FPS
rng = np.random.default_rng(0)


def blink_trace(seconds, open_ear, closed_ear, blink_every, blink_ms=150, jitter=0.012):
    """EAR samples for a driver blinking normally."""
    out = []
    n = int(seconds * FPS)
    blink_frames = max(1, int((blink_ms / 1000.0) * FPS))
    period = int(blink_every * FPS)
    for i in range(n):
        phase = i % period
        if phase < blink_frames:                      # cosine dip through the blink
            k = phase / blink_frames
            depth = 0.5 * (1 - np.cos(2 * np.pi * k))
            ear = open_ear - depth * (open_ear - closed_ear)
        else:
            ear = open_ear
        out.append(ear + rng.normal(0, jitter))
    return out


def long_closure_trace(seconds, open_ear, closed_ear, closed_every, closed_for, jitter=0.012):
    """A drowsy driver: eyes hang shut for whole seconds at a time."""
    out = []
    n = int(seconds * FPS)
    period = int(closed_every * FPS)
    shut = int(closed_for * FPS)
    for i in range(n):
        ear = closed_ear if (i % period) < shut else open_ear
        out.append(ear + rng.normal(0, jitter))
    return out


def score(trace, calib):
    """Run a trace through PERCLOS, return (final score, longest closed run)."""
    p = PerclosTracker()
    t = 0.0
    closed_since = None
    longest = 0.0
    for ear in trace:
        t += DT
        o = calib.openness(ear)
        p.update(t, o)
        if o <= PERCLOS_CLOSED_LEVEL:
            if closed_since is None:
                closed_since = t
            longest = max(longest, t - closed_since)
        else:
            closed_since = None
    return p.value(), longest


def old_system_fires(trace, thresh=0.3, consec=30):
    """The previous logic: EAR below a fixed 0.3 for 30 frames in a row."""
    counter = 0
    for ear in trace:
        counter = counter + 1 if ear < thresh else 0
        if counter >= consec:
            return True
    return False


OPEN, CLOSED = 0.31, 0.07

# --- calibrate on 8 s of a normally-blinking, awake driver -------------------
calib = EyeCalibration()
t = 0.0
for ear in blink_trace(9, OPEN, CLOSED, blink_every=4):
    t += DT
    calib.add(ear, t)
    calib.maybe_finish(t)
assert calib.done, "calibration did not complete"

print("open EAR  {:.3f}   closed EAR {:.3f}   P80 fires below EAR {:.3f}".format(
    calib.ear_open, calib.ear_closed, calib.closed_ear_threshold()))
print()

cases = [
    ("awake, blinks every 4 s", blink_trace(60, OPEN, CLOSED, 4)),
    ("awake, fast blinker (every 2 s)", blink_trace(60, OPEN, CLOSED, 2)),
    ("tired, 1 s closures every 10 s", long_closure_trace(60, OPEN, CLOSED, 10, 1.0)),
    ("drowsy, 3 s closures every 12 s", long_closure_trace(60, OPEN, CLOSED, 12, 3.0)),
    ("asleep, 6 s closures every 12 s", long_closure_trace(60, OPEN, CLOSED, 12, 6.0)),
]

print("{:<34} {:>9} {:>16} {:>12} {:>10}".format(
    "scenario", "PERCLOS", "new verdict", "longest shut", "old fires"))
print("-" * 86)

results = {}
for name, trace in cases:
    s, longest = score(trace, calib)
    micro = longest >= MICROSLEEP_SECONDS
    if micro:
        verdict = "MICROSLEEP"
    elif s >= PERCLOS_ALERT:
        verdict = "DROWSY"
    elif s >= PERCLOS_WARN:
        verdict = "WARNING"
    else:
        verdict = "ALERT (ok)"
    results[name] = verdict
    print("{:<34} {:>8.1f}% {:>16} {:>11.1f}s {:>10}".format(
        name, s * 100, verdict, longest, "YES" if old_system_fires(trace) else "no"))

print()
fails = []
if results["awake, blinks every 4 s"] != "ALERT (ok)":
    fails.append("normal blinking triggered an alert")
if results["awake, fast blinker (every 2 s)"] != "ALERT (ok)":
    fails.append("fast blinking triggered an alert")
if results["drowsy, 3 s closures every 12 s"] not in ("DROWSY", "MICROSLEEP"):
    fails.append("real drowsiness was missed")
if results["asleep, 6 s closures every 12 s"] not in ("DROWSY", "MICROSLEEP"):
    fails.append("sleeping driver was missed")

# --- frame-rate independence ------------------------------------------------
# One fixed real-world event: over 30 s of wall clock the eyes are shut for
# 2 s out of every 10 s. The true answer is 20%, whatever the camera does.
def eyes_shut_at(t):
    return (t % 10.0) < 2.0


def sample_at(timestamps):
    p = PerclosTracker()
    for t in timestamps:
        p.update(t, 0.05 if eyes_shut_at(t) else 1.0)
    return p.value()


def naive_frame_count(timestamps):
    """What counting frames instead of weighting by time would report."""
    closed = sum(1 for t in timestamps if eyes_shut_at(t))
    return closed / len(timestamps)


steady_30 = [i / 30.0 for i in range(int(30 * 30))]
steady_8 = [i / 8.0 for i in range(int(30 * 8))]
# A realistic failure mode: landmark detection is less reliable on a closed eye,
# so 4 of every 5 frames go missing while the eyes are shut.
lossy = [t for i, t in enumerate(steady_30) if not eyes_shut_at(t) or i % 5 == 0]

print("frame-rate independence (true answer is 20.0%):")
for label, ts in (("steady 30 fps", steady_30), ("steady 8 fps", steady_8),
                  ("30 fps, frames dropped while eyes shut", lossy)):
    print("  {:<40} time-weighted {:5.1f}%   frame-count {:5.1f}%".format(
        label, sample_at(ts) * 100, naive_frame_count(ts) * 100))

if max(abs(sample_at(ts) - 0.20) for ts in (steady_30, steady_8, lossy)) > 0.02:
    fails.append("score drifted with frame rate")

# The old rule counted frames, so its time-to-alert moved with the frame rate.
# --- the case a fixed 0.3 threshold gets badly wrong -------------------------
# Plenty of people have a naturally open EAR below 0.3: narrower eyes, glasses,
# or simply sitting further from the camera. The old rule calls them drowsy the
# whole time. Calibration measures their real baseline instead.
NARROW_OPEN, NARROW_CLOSED = 0.24, 0.06
narrow_calib = EyeCalibration()
tn = 0.0
for ear in blink_trace(9, NARROW_OPEN, NARROW_CLOSED, blink_every=4):
    tn += DT
    narrow_calib.add(ear, tn)
    narrow_calib.maybe_finish(tn)

awake_narrow = blink_trace(60, NARROW_OPEN, NARROW_CLOSED, 4)
s_narrow, _ = score(awake_narrow, narrow_calib)
print()
print("wide-awake driver whose natural open EAR is {:.2f} (narrow eyes / glasses / sat back):"
      .format(NARROW_OPEN))
print("  old rule (fixed 0.3): {}".format(
    "FALSE ALARM" if old_system_fires(awake_narrow) else "no alert"))
print("  new rule (calibrated to {:.3f}): PERCLOS {:.1f}% -> {}".format(
    narrow_calib.ear_open, s_narrow * 100,
    "no alert" if s_narrow < PERCLOS_WARN else "ALERT"))
if s_narrow >= PERCLOS_WARN:
    fails.append("narrow-eyed awake driver triggered an alert")

print()
print("old rule, 30 consecutive frames below EAR 0.3 =")
for f in (30, 15, 8):
    print("  at {:>2} fps -> alerts after {:.1f} s of closed eyes".format(f, 30.0 / f))
print("new rule, microsleep = {:.1f} s of closed eyes at any frame rate"
      .format(MICROSLEEP_SECONDS))

print()
print("FAILURES: " + ("; ".join(fails) if fails else "none - all checks passed"))
