# VigiWatch - Driver Drowsiness Detection (PERCLOS edition)
#
# WHAT CHANGED FROM THE OLD VERSION
#   * All Arduino / pyserial / buzzer code removed.
#   * Drowsiness is now scored with PERCLOS (P80) instead of a raw EAR
#     threshold plus a consecutive-frame counter.
#
# WHY PERCLOS IS MORE ACCURATE THAN A BARE EAR THRESHOLD
#   EAR is still the raw signal -- PERCLOS is built on top of it. What changes
#   is the decision logic. The old rule was "is EAR below 0.3 for 30 frames in
#   a row?", which breaks in three ways:
#     1. 0.3 is one fixed number for every face. Eye shape, glasses, and how
#        far you sit from the camera all shift EAR, so the same number is too
#        strict for one person and too loose for another.
#     2. "30 frames" is not a fixed amount of time. At 30 fps that is 1 second;
#        at 10 fps it is 3 seconds. The alert speed changes with the webcam.
#     3. A normal blink dips EAR below 0.3, so the counter kept getting nudged
#        by ordinary blinking.
#   PERCLOS fixes all three. Each driver's own open-eye EAR is measured at
#   startup, closure is expressed as a percentage of THAT person's eye opening,
#   and the score is the fraction of TIME (not frames) the eyes were at least
#   80% closed across a rolling window. A 150 ms blink adds about 0.5% to a
#   30 s window, so blinks no longer register as drowsiness.
#
#   Run:  python vigiwatch.py --webcam 0
#   Keys: q = quit, c = recalibrate

import argparse
import os
import time
from collections import deque
from datetime import datetime, timedelta
from threading import Thread

import cv2
import dlib
import numpy as np
from imutils import face_utils
from scipy.spatial import distance as dist

try:
    import pywhatkit
except ImportError:
    pywhatkit = None


# ---------------------------------------------------------------- tuning ----
# Camera / processing
PROC_WIDTH = 640          # width we run detection at. Bigger = better landmark
                          # precision (so a cleaner EAR signal), but slower.
                          # The old code used 450; 640 gives noticeably steadier
                          # eye landmarks, and PERCLOS is time-based so a lower
                          # frame rate does not distort the score.

# PERCLOS
PERCLOS_WINDOW = 30.0     # seconds of history the score is measured over.
                          # Research standard is 60 s; 30 s reacts faster, which
                          # is better for a live demo.
PERCLOS_CLOSED_LEVEL = 0.20   # P80: eye counts as "closed" at <= 20% open.
PERCLOS_WARN = 0.08       # 8% of the window closed -> early fatigue warning
PERCLOS_ALERT = 0.15      # 15% -> drowsy, sound the alarm
PERCLOS_MIN_COVERAGE = 10.0   # need this many seconds of data before scoring

# Microsleep catch. PERCLOS is a slow average, so eyes slamming shut for a few
# straight seconds would only move it a little. This is the fast path.
MICROSLEEP_SECONDS = 1.5

# Calibration
CALIB_SECONDS = 8.0       # how long we watch the driver's normal open eyes
CALIB_MIN_SAMPLES = 40
EAR_OPEN_FALLBACK = 0.30      # used if calibration never saw a face
EAR_CLOSED_FALLBACK = 0.08
CLOSED_RATIO_OF_OPEN = 0.25   # assumed closed EAR when the driver never blinked
                              # hard during calibration
EAR_SMOOTH_N = 3          # median filter length, kills landmark jitter

# Yawn / no-face (unchanged behaviour from the old version)
YAWN_THRESH = 35
NO_FACE_TIMEOUT = 20
YAWN_COOLDOWN = 5
DROWSY_COOLDOWN = 5

WHATSAPP_NUMBER = "+639670092434"
WHATSAPP_EVERY_N_ALERTS = 5


# ------------------------------------------------------------ file paths ----
# The 68-landmark model is about 100 MB so it is not committed to the repo.
# Look in a few sensible places instead of hard-coding one machine's path.
SEARCH_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"),
    os.path.dirname(os.path.abspath(__file__)),
    r"C:\Users\Abbwie\PycharmProjects\drowsiness detection\models",
]


def find_file(*names):
    """Return the first of the given names that exists in a known model dir."""
    for directory in SEARCH_DIRS:
        for name in names:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
    return None


# -------------------------------------------------------------- metrics -----
def eye_aspect_ratio(eye):
    """Vertical eye opening divided by horizontal eye width."""
    a = dist.euclidean(eye[1], eye[5])
    b = dist.euclidean(eye[2], eye[4])
    c = dist.euclidean(eye[0], eye[3])
    if c == 0:
        return 0.0
    return (a + b) / (2.0 * c)


def compute_ear(shape):
    (l_start, l_end) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
    (r_start, r_end) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
    left_eye = shape[l_start:l_end]
    right_eye = shape[r_start:r_end]
    ear = (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2.0
    return ear, left_eye, right_eye


def lip_distance(shape):
    top_lip = np.concatenate((shape[50:53], shape[61:64]))
    low_lip = np.concatenate((shape[56:59], shape[65:68]))
    return abs(np.mean(top_lip, axis=0)[1] - np.mean(low_lip, axis=0)[1])


# ---------------------------------------------------------- calibration -----
class EyeCalibration:
    """
    Learns this specific driver's open-eye EAR so closure can be measured as a
    percentage of their own eyes rather than against a fixed 0.3.

    ear_open   -- 85th percentile of the samples. A percentile rather than the
                  mean so that blinks during calibration do not drag it down.
    ear_closed -- the lower of (5th percentile seen, 25% of ear_open). If the
                  driver blinked during calibration the 5th percentile is a real
                  measurement of their closed eye; if they did not, the 25%
                  estimate keeps the threshold conservative.
    """

    def __init__(self, duration=CALIB_SECONDS):
        self.duration = duration
        self.reset()

    def reset(self):
        self.samples = []
        self.started_at = None
        self.done = False
        self.ear_open = EAR_OPEN_FALLBACK
        self.ear_closed = EAR_CLOSED_FALLBACK

    def add(self, ear, now):
        if self.started_at is None:
            self.started_at = now
        self.samples.append(ear)

    def elapsed(self, now):
        if self.started_at is None:
            return 0.0
        return now - self.started_at

    def maybe_finish(self, now):
        """Close out calibration once we have enough time AND enough samples."""
        if self.done or self.started_at is None:
            return False
        if self.elapsed(now) < self.duration:
            return False
        if len(self.samples) < CALIB_MIN_SAMPLES:
            return False   # face was mostly missing -- keep collecting

        arr = np.asarray(self.samples, dtype=float)
        ear_open = float(np.percentile(arr, 85))
        if ear_open < 0.15:
            # Almost certainly calibrated with the eyes shut or a bad face box.
            print("Calibration looked wrong (eyes closed?) - using defaults.")
            ear_open = EAR_OPEN_FALLBACK

        ear_closed = min(float(np.percentile(arr, 5)), CLOSED_RATIO_OF_OPEN * ear_open)
        ear_closed = max(ear_closed, 0.03)              # landmarks never fully collapse
        ear_closed = min(ear_closed, ear_open - 0.05)   # keep a usable range

        self.ear_open = ear_open
        self.ear_closed = ear_closed
        self.done = True
        print("Calibrated: open EAR={:.3f}  closed EAR={:.3f}  -> P80 trips below EAR {:.3f}"
              .format(ear_open, ear_closed, self.closed_ear_threshold()))
        return True

    def openness(self, ear):
        """Map a raw EAR to 0.0 (fully closed) .. 1.0 (fully open)."""
        span = self.ear_open - self.ear_closed
        if span <= 0:
            return 1.0
        return float(np.clip((ear - self.ear_closed) / span, 0.0, 1.0))

    def closed_ear_threshold(self):
        """The absolute EAR that P80 works out to, shown on screen for sanity."""
        return self.ear_closed + PERCLOS_CLOSED_LEVEL * (self.ear_open - self.ear_closed)


# ------------------------------------------------------------- PERCLOS ------
class PerclosTracker:
    """
    Rolling, time-weighted percentage of eye closure.

    Each frame contributes its own duration rather than a count of 1, so a
    stuttering webcam cannot skew the score. Frames are dropped once they fall
    out of the window.
    """

    def __init__(self, window=PERCLOS_WINDOW, closed_level=PERCLOS_CLOSED_LEVEL):
        self.window = window
        self.closed_level = closed_level
        self.samples = deque()      # (timestamp, is_closed)

    def update(self, now, openness):
        self.samples.append((now, openness <= self.closed_level))
        cutoff = now - self.window
        while len(self.samples) > 1 and self.samples[0][0] < cutoff:
            self.samples.popleft()

    def clear(self):
        self.samples.clear()

    def coverage(self):
        """Seconds of history currently held."""
        if len(self.samples) < 2:
            return 0.0
        return self.samples[-1][0] - self.samples[0][0]

    def value(self):
        """Fraction of the window spent with the eyes at least 80% closed."""
        if len(self.samples) < 2:
            return 0.0
        closed_time = 0.0
        total_time = 0.0
        for i in range(1, len(self.samples)):
            t_prev, was_closed = self.samples[i - 1]
            dt = self.samples[i][0] - t_prev
            if dt <= 0 or dt > 1.0:
                continue        # a stall or a paused window is not evidence
            total_time += dt
            if was_closed:
                closed_time += dt
        if total_time <= 0:
            return 0.0
        return closed_time / total_time


# ------------------------------------------------------------------ HUD -----
# Everything on screen is pinned to the left or right edge so the middle of the
# frame -- the driver's face -- is never covered.
FONT = cv2.FONT_HERSHEY_SIMPLEX
DISPLAY_W, DISPLAY_H = 1280, 720
HUD_MARGIN = 24


def fit_letterbox(frame, out_w=DISPLAY_W, out_h=DISPLAY_H):
    """
    Scale the frame into the window without distorting it, centred on black.

    A 4:3 webcam stretched into a 16:9 window makes every face look wide and
    the eye outlines look wrong. EAR is computed before this step so the score
    was never affected, but the picture was misleading to look at.

    Returns the canvas plus the scale and offsets needed to map a frame
    coordinate onto it.
    """
    h, w = frame.shape[:2]
    s = min(out_w / float(w), out_h / float(h))
    new_w, new_h = int(round(w * s)), int(round(h * s))
    canvas = np.zeros((out_h, out_w, 3), np.uint8)
    off_x, off_y = (out_w - new_w) // 2, (out_h - new_h) // 2
    canvas[off_y:off_y + new_h, off_x:off_x + new_w] = cv2.resize(frame, (new_w, new_h))
    return canvas, s, off_x, off_y


def draw_text(img, text, x, y, scale=0.6, colour=(235, 235, 235), thickness=1,
              align="left"):
    """
    Draw text with a dark outline. The outline is what keeps it readable over a
    bright shirt or a sunlit window without needing a solid panel behind it.
    """
    (text_w, _), _ = cv2.getTextSize(text, FONT, scale, thickness)
    if align == "right":
        x -= text_w
    cv2.putText(img, text, (x, y), FONT, scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), FONT, scale, colour, thickness, cv2.LINE_AA)


def draw_hud(img, state, colour, score, coverage, calib, calib_elapsed,
             ear, openness, mouth_opening, fps):
    """Status down the left edge, live numbers down the right edge."""
    h, w = img.shape[:2]
    left = HUD_MARGIN
    right = w - HUD_MARGIN

    # ---- left edge: what the system currently thinks ----
    draw_text(img, state, left, 48, 1.0, colour, 2)

    if calib.done:
        bar_y, bar_w, bar_h = 66, 250, 16
        cv2.rectangle(img, (left, bar_y), (left + bar_w, bar_y + bar_h), (25, 25, 25), -1)
        fill = int(min(score / PERCLOS_ALERT, 1.0) * (bar_w - 2))
        if fill > 0:
            cv2.rectangle(img, (left + 1, bar_y + 1),
                          (left + 1 + fill, bar_y + bar_h - 1), colour, -1)
        # tick marking where the fatigue warning line sits
        warn_x = left + int((PERCLOS_WARN / PERCLOS_ALERT) * (bar_w - 2))
        cv2.line(img, (warn_x, bar_y), (warn_x, bar_y + bar_h), (0, 165, 255), 1)
        cv2.rectangle(img, (left, bar_y), (left + bar_w, bar_y + bar_h), (110, 110, 110), 1)
        draw_text(img, "PERCLOS {:.1f}%   {:.0f}/{:.0f}s window".format(
            score * 100, coverage, PERCLOS_WINDOW), left, bar_y + bar_h + 22, 0.55)
    else:
        draw_text(img, "Keep your eyes open  {:.1f}/{:.0f}s".format(
            calib_elapsed, CALIB_SECONDS), left, 78, 0.6, (0, 200, 255))

    # ---- right edge: the raw numbers, right-aligned ----
    rows = []
    if ear is not None:
        rows.append(("EAR", "{:.3f}".format(ear)))
        rows.append(("OPEN", "{:.0f}%".format(openness * 100)))
        rows.append(("MOUTH", "{:.1f}".format(mouth_opening)))
    if calib.done:
        rows.append(("P80", "<{:.3f}".format(calib.closed_ear_threshold())))
    rows.append(("FPS", "{:.1f}".format(fps)))

    y = 44
    for label, value in rows:
        draw_text(img, "{}  {}".format(label, value), right, y, 0.6, align="right")
        y += 28

    draw_text(img, "q quit    c recalibrate", left, h - HUD_MARGIN, 0.5, (170, 170, 170))


# --------------------------------------------------------------- alerts -----
def speak(msg):
    print(msg)
    try:
        os.system('espeak "{}"'.format(msg))
    except Exception:
        print("Text-to-speech not available")


def send_whatsapp(phone_number, message):
    if pywhatkit is None:
        print("pywhatkit not installed; skipping WhatsApp")
        return

    def send():
        try:
            now = datetime.now() + timedelta(minutes=1)
            pywhatkit.sendwhatmsg(phone_number, message, now.hour, now.minute)
            print("WhatsApp message scheduled")
        except Exception as exc:
            print("Failed to send WhatsApp message: {}".format(exc))

    Thread(target=send, daemon=True).start()


# ----------------------------------------------------------------- main -----
def main():
    ap = argparse.ArgumentParser(description="VigiWatch drowsiness detector (PERCLOS)")
    ap.add_argument("-w", "--webcam", type=int, default=0, help="webcam index")
    args = ap.parse_args()

    cascade_path = find_file("haarcascade_frontalface_default.xml",
                             "haarcascade_frontalface_default (2).xml")
    predictor_path = find_file("shape_predictor_68_face_landmarks.dat")

    if cascade_path is None or predictor_path is None:
        print("Could not find the model files. Looked in:")
        for d in SEARCH_DIRS:
            print("  " + d)
        print("Need: haarcascade_frontalface_default.xml and "
              "shape_predictor_68_face_landmarks.dat")
        return

    print("Loading face detector and predictor...")
    detector = cv2.CascadeClassifier(cascade_path)
    predictor = dlib.shape_predictor(predictor_path)

    cap = cv2.VideoCapture(args.webcam, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("Error: could not open webcam {}".format(args.webcam))
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    time.sleep(1.0)

    calib = EyeCalibration()
    perclos = PerclosTracker()
    ear_history = deque(maxlen=EAR_SMOOTH_N)

    closed_since = None          # start of the current run of closed frames
    sleepy_sets = 0
    last_drowsy_alert = 0.0
    last_yawn_alert = 0.0
    last_no_face_alert = 0.0
    no_face_start = None
    fps = 0.0
    last_frame_time = time.time()

    cv2.namedWindow("VigiWatch", cv2.WINDOW_NORMAL)
    print("Starting VigiWatch. Look at the camera with your eyes open normally.")
    print("Calibrating for {:.0f} seconds...  (q = quit, c = recalibrate)"
          .format(CALIB_SECONDS))

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Failed to grab frame")
                break

            now = time.time()
            dt = now - last_frame_time
            last_frame_time = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps else 1.0 / dt

            scale = PROC_WIDTH / frame.shape[1]
            frame = cv2.resize(frame, (PROC_WIDTH, int(frame.shape[0] * scale)))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Equalised copy for detection only -- it helps Haar find faces in
            # poor light, but the landmark predictor is more accurate on the
            # untouched image.
            faces = detector.detectMultiScale(cv2.equalizeHist(gray), scaleFactor=1.1,
                                              minNeighbors=5, minSize=(60, 60))

            ear = None
            mouth_opening = 0.0
            openness = 1.0
            contours = []

            if len(faces) > 0:
                no_face_start = None
                # Only track the largest face -- that is the driver. The old
                # version looped over every face while sharing one counter, so
                # a passenger could reset the driver's state.
                x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
                rect = dlib.rectangle(int(x), int(y), int(x + w), int(y + h))
                shape = face_utils.shape_to_np(predictor(gray, rect))

                raw_ear, left_eye, right_eye = compute_ear(shape)
                ear_history.append(raw_ear)
                ear = float(np.median(ear_history))     # smooth out landmark jitter
                mouth_opening = lip_distance(shape)

                # Kept as points and drawn on the full-size frame later, so the
                # outlines stay sharp instead of being upscaled with the image.
                contours = [cv2.convexHull(left_eye), cv2.convexHull(right_eye),
                            shape[48:60]]

                if not calib.done:
                    calib.add(ear, now)
                    calib.maybe_finish(now)
                else:
                    openness = calib.openness(ear)
                    perclos.update(now, openness)

                    # Track how long the eyes have been continuously shut.
                    if openness <= PERCLOS_CLOSED_LEVEL:
                        if closed_since is None:
                            closed_since = now
                    else:
                        closed_since = None
            else:
                closed_since = None
                if no_face_start is None:
                    no_face_start = now
                elif (now - no_face_start > NO_FACE_TIMEOUT
                      and now - last_no_face_alert >= NO_FACE_TIMEOUT):
                    last_no_face_alert = now
                    Thread(target=speak, args=("Driver not detected! Stay alert!",),
                           daemon=True).start()

            # ---------- drowsiness decision ----------
            score = perclos.value()
            coverage = perclos.coverage()
            eyes_shut_for = (now - closed_since) if closed_since else 0.0

            if not calib.done:
                state, colour = "CALIBRATING", (0, 200, 255)
            elif eyes_shut_for >= MICROSLEEP_SECONDS:
                state, colour = "MICROSLEEP", (0, 0, 255)
            elif coverage < PERCLOS_MIN_COVERAGE:
                state, colour = "WARMING UP", (0, 200, 255)
            elif score >= PERCLOS_ALERT:
                state, colour = "DROWSY", (0, 0, 255)
            elif score >= PERCLOS_WARN:
                state, colour = "FATIGUE WARNING", (0, 165, 255)
            else:
                state, colour = "ALERT", (0, 255, 0)

            if state in ("DROWSY", "MICROSLEEP") and now - last_drowsy_alert >= DROWSY_COOLDOWN:
                last_drowsy_alert = now
                sleepy_sets += 1
                Thread(target=speak, args=("Wake up! Keep your eyes on the road!",),
                       daemon=True).start()
                if sleepy_sets % WHATSAPP_EVERY_N_ALERTS == 0:
                    send_whatsapp(WHATSAPP_NUMBER, "Driver appears drowsy! Please check.")

            # ---------- yawn ----------
            if mouth_opening > YAWN_THRESH and now - last_yawn_alert >= YAWN_COOLDOWN:
                last_yawn_alert = now
                Thread(target=speak, args=("Stop yawning! Stay focused!",),
                       daemon=True).start()

            # ---------- draw ----------
            display, disp_scale, off_x, off_y = fit_letterbox(frame)
            for pts in contours:
                scaled = np.round(pts.reshape(-1, 2) * disp_scale
                                  + (off_x, off_y)).astype(np.int32)
                cv2.drawContours(display, [scaled], -1, (0, 255, 0), 1, cv2.LINE_AA)

            draw_hud(display, state, colour, score, coverage, calib,
                     calib.elapsed(now), ear, openness, mouth_opening, fps)

            cv2.imshow("VigiWatch", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                print("Recalibrating - look at the camera with your eyes open.")
                calib.reset()
                perclos.clear()
                ear_history.clear()
                closed_since = None

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("VigiWatch terminated")


if __name__ == "__main__":
    main()
