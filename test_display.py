"""A circle drawn in the source frame must still be a circle on screen."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from vigiwatch import fit_letterbox, draw_hud, EyeCalibration, DISPLAY_W, DISPLAY_H

fails = []
print("{:<16} {:>12} {:>16} {:>12} {:>10}".format(
    "source", "letterboxed", "bars", "circle w:h", "verdict"))
print("-" * 72)

for (w, h), label in (((640, 480), "4:3 webcam"),
                      ((1280, 720), "16:9 webcam"),
                      ((640, 360), "16:9 small"),
                      ((800, 600), "4:3 other")):
    src = np.zeros((h, w, 3), np.uint8)
    # a circle of known size, plus corner marks so we can find the video area
    r = min(w, h) // 4
    cv2.circle(src, (w // 2, h // 2), r, (255, 255, 255), -1)
    src[0, 0] = src[0, -1] = src[-1, 0] = src[-1, -1] = (40, 40, 40)

    canvas, s, ox, oy = fit_letterbox(src)

    white = np.all(canvas > 200, axis=2)
    ys, xs = np.where(white)
    cw, ch = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    ratio = cw / float(ch)

    video_w, video_h = int(round(w * s)), int(round(h * s))
    bars = "{}px side".format(ox) if ox else ("{}px top".format(oy) if oy else "none")

    ok = abs(ratio - 1.0) <= 0.02
    if not ok:
        fails.append("{}: circle came out {:.3f}:1".format(label, ratio))
    print("{:<16} {:>12} {:>16} {:>11.3f} {:>10}".format(
        "{} {}x{}".format(label, w, h), "{}x{}".format(video_w, video_h),
        bars, ratio, "round" if ok else "SQUASHED"))

    # the whole source must be visible, nothing cropped
    if video_w > DISPLAY_W or video_h > DISPLAY_H:
        fails.append("{}: video overflows the window".format(label))

# what the old code did, for comparison
src = np.zeros((480, 640, 3), np.uint8)
cv2.circle(src, (320, 240), 120, (255, 255, 255), -1)
old = cv2.resize(src, (DISPLAY_W, DISPLAY_H))
ys, xs = np.where(np.all(old > 200, axis=2))
old_ratio = (xs.max() - xs.min() + 1) / float(ys.max() - ys.min() + 1)
print()
print("old behaviour on the 4:3 camera: circle came out {:.3f}:1 "
      "({:.0f}% too wide)".format(old_ratio, (old_ratio - 1) * 100))

# HUD must still clear the centre once letterboxed
src = np.full((480, 640, 3), 90, np.uint8)
canvas, s, ox, oy = fit_letterbox(src)
before = canvas.copy()
calib = EyeCalibration()
calib.ear_open, calib.ear_closed, calib.done = 0.323, 0.081, True
draw_hud(canvas, "FATIGUE WARNING", (0, 165, 255), 0.101, 30.0, calib, 0.0,
         0.164, 0.34, 6.0, 27.1)
diff = np.any(before != canvas, axis=2)
centre = int(diff[:, int(DISPLAY_W * 0.30):int(DISPLAY_W * 0.70)].sum())
print("HUD pixels in the central 40% after letterboxing: {}".format(centre))
if centre:
    fails.append("HUD intrudes on the centre")

print()
print("FAILURES: " + ("; ".join(fails) if fails else "none - all checks passed"))
