
import argparse
import os
import time
from collections import deque
from datetime import datetime, timedelta
from threading import Lock, Thread

import cv2
import dlib
import numpy as np
from imutils import face_utils
from scipy.spatial import distance as dist

try:
    import pywhatkit
except ImportError:
    pywhatkit = None

try:
    import requests
except ImportError:
    requests = None


try:

    import serial
    import serial.tools.list_ports
except ImportError:
    
    serial = None

try:
    from dotenv import load_dotenv


   
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass



# Camera / processing
PROC_WIDTH = 640          # width we measure at. Bigger = better landmarks, and
                          # the landmarks are what the EAR is built from.

# Detection
#
# dlib's HOG detector leads, with Haar behind it. Measured on this machine,
# HOG at 480 wide costs 20 ms against 29 ms for a loosened Haar pass, so the
# more robust of the two is also the cheaper one -- and HOG holds on to a
# tilted head long after Haar has lost it, which is most of what a driver's
# head does. Haar is kept because the two fail on different things: it still
# fires on some of the turned-away frames HOG drops.
CAMERA_BACKENDS = (("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF),
                   ("ANY", cv2.CAP_ANY))
                          # tried in this order. DSHOW first because it applies
                          # a resolution request more reliably and starts
                          # faster, but it is also the one that flatly refuses
                          # a busy device, so the others are worth having.
CAMERA_WARMUP_READS = 10  # a cold webcam can take a moment to hand over its
                          # first frame. Only after this many empty reads is it
                          # fair to call the device dead.

DETECT_WIDTH = 480        # width the detectors run at, independent of
                          # PROC_WIDTH. A face is still ~90 px across here,
                          # comfortably over the 80 px HOG's model needs.
FACE_COAST_SECONDS = 0.5  # how long the last known box stays usable when a
                          # frame finds nothing. A driver cannot leave the
                          # frame and return inside half a second, so a gap
                          # this short is the detector blinking, not the face
                          # going away -- and throwing the box away costs the
                          # EAR stream that PERCLOS is built out of. It is
                          # also deliberately under MICROSLEEP_SECONDS, so
                          # coasting alone can never raise a microsleep.
HAAR_TO_HOG = 0.86        # Haar boxes run wider and sit higher than the ones
                          # the 68-point predictor was trained on. Feeding one
                          # in raw puts the landmarks slightly off; because
                          # fallback frames are interleaved with HOG frames,
                          # that shows up as EAR jitter rather than the steady
                          # bias calibration would have absorbed.

# PERCLOS
#
# These were tightened after road testing: the first set let closures through
# that a driver should have been alerted for. The numbers are deliberately
# strict, because the two kinds of mistake are not equal here -- a false alarm
# is a moment of annoyance, a missed one is a car with nobody watching the road.
PERCLOS_WINDOW = 30.0     # seconds of history the score is measured over.
                          # Research standard is 60 s; 30 s reacts faster, which
                          # is better for a live demo.

PERCLOS_CLOSED_LEVEL = 0.20   # P80: eye counts as "closed" at <= 20% open.
PERCLOS_WARN = 0.06       # was 0.08. Over a 30 s window this is 1.8 s of
                          # closure. Normal blinking runs about 3-4% (a 150 ms
                          # blink is ~0.5% of the window, at 15-20 blinks/min),
                          # so this sits just above resting and no lower --
                          # a warning that is always on is one you stop reading.
PERCLOS_ALERT = 0.10      # was 0.15. 3.0 s of the last 30 spent with the eyes
                          # at least 80% shut, down from 4.5 s. At 100 km/h the
                          # old threshold meant 125 m travelled blind before the
                          # alarm; this one, 83 m.
PERCLOS_REARM = PERCLOS_WARN  # after a drowsy alert the score has to fall back
                          # to the warning line before the slow path may fire
                          # again. Without this, one closure sits in the 30 s
                          # window and re-alarms every cooldown until it ages
                          # out -- the same episode, alerted twenty times.
                          # Microsleep is exempt: a fresh run of shut eyes is
                          # new evidence, not the old one decaying.
PERCLOS_MIN_COVERAGE = 10.0   # need this many seconds of data before scoring.
                          # Left alone: it is a statistical-validity guard, not
                          # a sensitivity knob, and the microsleep path below
                          # already covers the warm-up gap.

# Microsleep catch. PERCLOS is a slow average, so eyes slamming shut for a few
# straight seconds would only move it a little. This is the fast path, and it
# runs during warm-up too, before there is enough history to score.
MICROSLEEP_SECONDS = 1.0  # was 1.5. A long blink is 300-400 ms, so a full
                          # second of closure is not a blink by any measure --
                          # it is 28 m of road at 100 km/h with the eyes shut.

# Head drop (nodding off)
#
# PERCLOS can only score eyes the camera can see, and the posture that matters
# most -- the head falling forward -- is the one that hides them. A nod used to
# take the face out of frame, which reset the closure timer and left the
# no-face path to mention it twenty seconds later. The eyes are the better
# signal while they are visible; this covers the moment they are not.
HEAD_DROP_RATIO = 0.80    # fraction of the calibrated upright nose-to-eye-line
                          # distance that counts as a dropped head. Pitching
                          # down foreshortens the face, so the distance closes.
HEAD_DROP_SECONDS = 0.8   # held this long before it counts. A glance at the
                          # dashboard or down at the gearstick is shorter.
HEAD_DROP_GRACE = 1.5     # once the face is lost, how long a head that was
                          # merely trending down goes on counting as dropped.
                          # Flicker length: this covers a face that blinks out
                          # for a frame or two mid-nod.
HEAD_SLUMP_HOLD = 15.0    # the same, for a drop that was already confirmed.
                          # A head far enough down hides the eyes behind the
                          # brow and the face stops being detectable at all,
                          # so the detector has to hold a verdict it can no
                          # longer re-measure. Fifteen seconds keeps the alarm
                          # going through a real slump; after that the honest
                          # answer is NO FACE, which is not a reassuring one.

# Timeline strip
TIMELINE_SECONDS = 60.0   # history the graph shows. Wider than the PERCLOS
                          # window on purpose, so the climb towards the
                          # threshold is visible instead of filling the strip.

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

# Cloud relay -- the FastAPI service on Railway that the phone app reads from.
# Set both in .env at the repo root (gitignored, so the key never lands in git).
# Leave them unset and the detector runs exactly as before, reporting nowhere.
#   API_URL=https://your-app.up.railway.app
#   API_KEY=...
API_URL = os.environ.get("API_URL", "").strip().rstrip("/")
API_KEY = os.environ.get("API_KEY", "").strip()

# Railway displays the domain with no scheme and it is easy to paste it that
# way. requests rejects that, so fill in the https:// instead of failing with
# an obscure "No connection adapters were found".
if API_URL and not API_URL.startswith(("http://", "https://")):
    API_URL = "https://" + API_URL

STATUS_EVERY = 1.0        # seconds between heartbeats to the relay
SETTINGS_EVERY = 5.0      # seconds between reads of the app's alert switches.
                          # Slower than the heartbeat because nobody flips a
                          # switch twice a second, and every poll is a request
                          # the free Railway tier has to serve.

# Arduino (vigiwatch.ino: buzzer on D2, LED on D4)
BUZZ_SECONDS = 5.0        # how long one alert sounds for. Ten was long enough
                          # to be punishing rather than rousing, and a driver
                          # fumbling to silence it is a driver not steering.
                          # Timed here rather than in the sketch so it can be
                          # changed without re-flashing the board; the sketch's
                          # own timer stays as the backstop for a laptop that
                          # crashes mid-buzz.
BUZZ_COOLDOWN = 30.0      # minimum seconds between one buzz STARTING and the
                          # next. At a 5 s burst on a 5 s alert cooldown the
                          # next one began the moment the last ended, so the
                          # buzzer simply ran continuously for as long as the
                          # score stayed up -- painful, and nothing you can
                          # drive through. This guarantees 25 s of quiet
                          # between bursts. The voice alert is not held back;
                          # it is the buzzer that hurts.
ARDUINO_BAUD = 9600
ARDUINO_KEYWORDS = ("ARDUINO", "CH340", "CH341", "CP210", "FT232",
                    "USB-SERIAL", "USB SERIAL")


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


# ------------------------------------------------------------ detection -----
def _haar_to_hog_box(x1, y1, x2, y2):
    """Reshape a Haar box into the proportions dlib's predictor expects."""
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    w = (x2 - x1) * HAAR_TO_HOG
    h = (y2 - y1) * HAAR_TO_HOG
    cy += h * 0.06        # Haar sits high: it takes in forehead the training
                          # boxes did not.
    return cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0


class FaceTracker:
    """
    Finds the driver's face, and rides out the frames where nothing is found.

    Three passes, in order of how often they earn their keep: HOG gets the face
    on almost every frame, Haar picks up a share of what HOG drops, and the
    last known box covers the rest for a moment. Only when all three come up
    empty does the caller hear that there is no face.

    The old code ran one strict Haar pass and treated any miss as the driver
    being gone. Missing a frame is not the same as the driver leaving, and the
    difference matters: every dropped frame is an EAR sample PERCLOS never
    sees, and a run of them resets the closure timer that catches microsleep.
    """

    def __init__(self, cascade_path):
        self.hog = dlib.get_frontal_face_detector()
        self.haar = cv2.CascadeClassifier(cascade_path)
        # Local contrast, not global. equalizeHist works off the whole frame,
        # so a bright window behind the driver drags the face down into a
        # handful of grey levels; CLAHE equalises in tiles and leaves it alone.
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.last_box = None
        self.last_seen = 0.0
        self.source = "none"

    def coasting(self):
        """True if the current box is remembered rather than freshly found."""
        return self.source == "coast"

    def find(self, gray, now):
        """Return the driver's face box in `gray` coordinates, or None."""
        h, w = gray.shape[:2]
        if w > DETECT_WIDTH:
            small = cv2.resize(gray, (DETECT_WIDTH,
                                      int(round(h * DETECT_WIDTH / float(w)))))
        else:
            small = gray
        scale = small.shape[1] / float(w)       # measured, not assumed: the
                                                # resize rounds to whole pixels
        lit = self.clahe.apply(small)

        # Corners throughout, never width/height: a dlib rectangle spans both
        # of its end pixels, so w = right - left + 1, and round-tripping a box
        # out through width() and back through x + w grows it every time.
        boxes = [(r.left(), r.top(), r.right(), r.bottom())
                 for r in self.hog(lit, 0)]
        source = "hog"

        if not boxes:
            # Only worth its cost on the frames HOG has already given up on.
            # minNeighbors 4 and a 40 px floor rather than 5 and 60: a face
            # further from the camera than arm's length used to fall under the
            # old floor and simply stop existing.
            boxes = [(x, y, x + w, y + h) for x, y, w, h in
                     self.haar.detectMultiScale(lit, scaleFactor=1.05,
                                                minNeighbors=4,
                                                minSize=(40, 40))]
            source = "haar"

        if len(boxes) > 0:
            # Largest only -- that is the driver. A passenger leaning in must
            # not become the face the alerts are measured against.
            x1, y1, x2, y2 = max(boxes, key=lambda b: (b[2] - b[0])
                                 * (b[3] - b[1]))
            if source == "haar":
                x1, y1, x2, y2 = _haar_to_hog_box(x1, y1, x2, y2)
            box = dlib.rectangle(int(round(x1 / scale)), int(round(y1 / scale)),
                                 int(round(x2 / scale)), int(round(y2 / scale)))
            self.last_box, self.last_seen, self.source = box, now, source
            return box

        if (self.last_box is not None
                and now - self.last_seen <= FACE_COAST_SECONDS):
            self.source = "coast"
            return self.last_box

        self.last_box, self.source = None, "none"
        return None


def _pitch_ratio(shape):
    """Eye-line-to-nose-tip distance over the distance between the eyes.

    Scale free, so leaning towards the camera does not read as lifting the
    head -- both distances grow together and the ratio holds.
    """
    left = shape[36:42].mean(axis=0)
    right = shape[42:48].mean(axis=0)
    interocular = float(np.hypot(right[0] - left[0], right[1] - left[1]))
    if interocular <= 1.0:
        return None                     # degenerate box, no usable geometry
    eye_mid_y = (left[1] + right[1]) / 2.0
    return (float(shape[30][1]) - eye_mid_y) / interocular


class HeadTracker:
    """
    Watches for the head pitching forward, and remembers that it was.

    Upright is learned per driver during the same eight seconds that calibrate
    the eyes, because necks, seats and camera angles all differ -- a fixed
    number would read one driver's normal posture as a nod and miss another's.

    It only ever adds evidence. Nothing here can clear a closure or cancel an
    alert, so the worst a mistuned baseline can do is raise a false alarm,
    never swallow a real one.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.baseline = None
        self.samples = []
        self.ratio = None
        self.down_since = None
        self.last_down_seen = 0.0
        self.confirmed_down = False

    # -- calibration -----------------------------------------------------
    def add_sample(self, shape):
        ratio = _pitch_ratio(shape)
        if ratio is not None:
            self.samples.append(ratio)

    def finish_calibration(self):
        """Lock in the upright baseline.

        Median rather than mean: a driver who glanced down once during the
        eight seconds should not drag the posture that the rest of the drive
        is measured against.
        """
        if len(self.samples) >= CALIB_MIN_SAMPLES:
            self.baseline = float(np.median(self.samples))
            print("Head baseline: nose sits {:.2f} eye-widths below the eyes"
                  .format(self.baseline))

    # -- live ------------------------------------------------------------
    def update(self, shape, now):
        """Feed a frame that has a face in it. True if the head is down."""
        self.ratio = _pitch_ratio(shape)
        if self.baseline is None or self.ratio is None:
            return False
        if self.ratio < self.baseline * HEAD_DROP_RATIO:
            if self.down_since is None:
                self.down_since = now
            self.last_down_seen = now
            # Confirmed once it has been held long enough to be a nod rather
            # than a glance at the gearstick. Only a confirmed drop earns the
            # long hold if the face then disappears.
            if now - self.down_since >= HEAD_DROP_SECONDS:
                self.confirmed_down = True
            return True
        self.down_since = None
        self.confirmed_down = False
        return False

    def update_no_face(self, now):
        """Feed a frame with no face in it.

        Two different situations arrive here and they do not deserve the same
        answer. A face lost while the head was already confirmed down has one
        obvious explanation: the head kept going, and a camera cannot see past
        a brow. A face lost from an upright head means something else -- the
        driver turned away, got out, or covered the lens.

        So a confirmed drop holds for HEAD_SLUMP_HOLD and a merely trending
        one holds for the flicker-length grace. The grace alone was built for
        a face that drops out for a frame and came nowhere near a driver who
        is actually slumped: after a second and a half it cleared, the eye
        timer had already been reset by the no-face branch, and a PERCLOS
        score frozen at its last value read as ALERT. Green, on a slumped
        driver, until the no-face alert eighteen seconds later.
        """
        if self.down_since is None:
            return False
        hold = HEAD_SLUMP_HOLD if self.confirmed_down else HEAD_DROP_GRACE
        if now - self.last_down_seen <= hold:
            return True
        self.down_since = None
        self.confirmed_down = False
        return False

    def down_for(self, now):
        """Seconds the head has been continuously down, 0.0 if it is not."""
        return (now - self.down_since) if self.down_since else 0.0


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
    elif align == "center":
        x -= text_w // 2
    cv2.putText(img, text, (x, y), FONT, scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), FONT, scale, colour, thickness, cv2.LINE_AA)


def draw_hud(img, state, colour, score, coverage, calib, calib_elapsed,
             ear, openness, mouth_opening, fps, arduino_ok=None,
             head_ratio=None, head_baseline=None, reason=""):
    """Status down the left edge, live numbers down the right edge."""
    h, w = img.shape[:2]
    left = HUD_MARGIN
    right = w - HUD_MARGIN

    # ---- left edge: what the system currently thinks ----
    # On a panel, not just the outline. Video compression eats thin light text
    # over a moving background, and this is the one word that has to survive.
    (sw, sh), _ = cv2.getTextSize(state, FONT, 1.1, 3)
    cv2.rectangle(img, (left - 10, 48 - sh - 12), (left + sw + 14, 48 + 13),
                  (18, 18, 18), -1)
    cv2.rectangle(img, (left - 10, 48 - sh - 12), (left - 5, 48 + 13),
                  colour, -1)
    draw_text(img, state, left, 48, 1.1, colour, 3)

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
            calib_elapsed, CALIB_SECONDS), left, 82, 0.6, (0, 200, 255))

    # The sentence under the verdict. The HUD has always carried the numbers
    # and never the reason, and the reason is the part a person reads.
    if reason:
        draw_text(img, reason, left, 132, 0.52, (215, 215, 215))

    # ---- right edge: the raw numbers, right-aligned ----
    rows = []
    if ear is not None:
        rows.append(("EAR", "{:.3f}".format(ear)))
        rows.append(("OPEN", "{:.0f}%".format(openness * 100)))
        rows.append(("MOUTH", "{:.1f}".format(mouth_opening)))
    if head_ratio is not None and head_baseline:
        # Posture as a percentage of this driver's own upright. Worth a row
        # next to the eye numbers: it is the second, independent channel, and
        # on screen it is the only sign the head is being watched at all.
        rows.append(("HEAD", "{:.0f}%".format(100.0 * head_ratio / head_baseline)))
    if calib.done:
        rows.append(("P80", "<{:.3f}".format(calib.closed_ear_threshold())))
    rows.append(("FPS", "{:.1f}".format(fps)))

    y = 44
    for label, value in rows:
        draw_text(img, "{}  {}".format(label, value), right, y, 0.6, align="right")
        y += 28

    # s is only listed when there is a board to silence.
    hints = "q quit    c recalibrate    m mesh"
    if arduino_ok is not None:
        hints += "    s silence buzzer"
    draw_text(img, hints, left, h - HUD_MARGIN, 0.5, (170, 170, 170))

    # Bottom right, opposite the key hints: whether the buzzer and LED can
    # actually be reached. Amber rather than red when it is missing -- a board
    # that is not there degrades the alert, it is not an alarm in itself.
    # None means --no-arduino, so there is nothing to report.
    if arduino_ok is not None:
        draw_text(img, "Arduino: {}".format("connected" if arduino_ok else "no board"),
                  right, h - HUD_MARGIN, 0.5,
                  (140, 220, 140) if arduino_ok else (0, 165, 255), align="right")


def draw_timeline(img, perclos, score_history, now, x, y, width,
                  band_h=16, graph_h=68):
    """
    The last TIMELINE_SECONDS of evidence, and the score drawn from it.

    A figure climbing from 0.07 to 0.10 tells a viewer nothing. The same climb
    drawn against the line it is heading for tells them everything at a
    glance, which is the difference between a number on a screen and being
    able to watch the thing reason.

    Two strips: where the eyes actually were, and what PERCLOS made of it.
    """
    t0 = now - TIMELINE_SECONDS

    # Darken what is behind the strips. The outline trick the text uses is not
    # enough for a graph -- thin lines need a settled background to read on.
    pad = 8
    x0 = max(x - pad, 0)
    y0 = max(y - pad, 0)
    x1 = min(x + width + pad, img.shape[1])
    y1 = min(y + band_h + graph_h + pad + 20, img.shape[0])
    roi = img[y0:y1, x0:x1]
    if roi.size:
        roi[:] = (roi * 0.35).astype(roi.dtype)

    def px(t):
        frac = max(0.0, min(1.0, (t - t0) / TIMELINE_SECONDS))
        return int(x + frac * width)

    # ---- closure band: where the eyes were, frame by frame ----
    cv2.rectangle(img, (x, y), (x + width, y + band_h), (45, 45, 45), -1)
    samples = list(perclos.samples)
    for i in range(1, len(samples)):
        t_prev, was_closed = samples[i - 1]
        if not was_closed or t_prev < t0:
            continue
        xa = px(t_prev)
        xb = px(samples[i][0])
        cv2.rectangle(img, (xa, y), (max(xb, xa + 1), y + band_h),
                      (0, 0, 255), -1)
    cv2.rectangle(img, (x, y), (x + width, y + band_h), (130, 130, 130), 1)

    # ---- score curve, against the lines that decide ----
    gy = y + band_h + 6
    top = PERCLOS_ALERT * 2.0       # puts the alert line mid-height, with room
    cv2.rectangle(img, (x, gy), (x + width, gy + graph_h), (30, 30, 30), -1)

    for level, col, label in ((PERCLOS_WARN, (0, 165, 255), "warn"),
                              (PERCLOS_ALERT, (0, 0, 255), "alert")):
        ly = gy + graph_h - int((level / top) * graph_h)
        cv2.line(img, (x, ly), (x + width, ly), col, 1)
        draw_text(img, label, x + width - 4, ly - 4, 0.4, col, 1, align="right")

    pts = [(px(t), gy + graph_h - int(min(s / top, 1.0) * graph_h))
           for t, s in score_history if t >= t0]
    if len(pts) > 1:
        cv2.polylines(img, [np.array(pts, dtype=np.int32)], False,
                      (120, 255, 160), 2, cv2.LINE_AA)
    cv2.rectangle(img, (x, gy), (x + width, gy + graph_h), (130, 130, 130), 1)

    draw_text(img, "eye closure  /  PERCLOS, last {:.0f}s".format(
        TIMELINE_SECONDS), x, gy + graph_h + 15, 0.44, (175, 175, 175))


def draw_landmarks(img, shape, scale, off_x, off_y, head_down=False):
    """
    The face the detector is actually working from, drawn on the frame.

    The eye and mouth outlines were already here; the rest of the mesh was
    not, and anyone watching two green outlines has no way to tell perception
    from a guess. The jaw, brows and nose cost nothing to draw and they are
    what makes it obvious that a model is reading a face rather than a motion
    detector tripping on a shadow.

    The line down to the nose is the head-drop measurement itself -- the
    quantity HEAD_DROP_RATIO is a fraction of. Worth drawing because it is the
    part of this detector that is ours rather than dlib's.
    """
    def pt(i):
        return (int(round(shape[i][0] * scale + off_x)),
                int(round(shape[i][1] * scale + off_y)))

    # The usual 68-point groups: jaw, both brows, the bridge, the nostrils.
    for a, b in ((0, 17), (17, 22), (22, 27), (27, 31), (31, 36)):
        pts = np.array([pt(i) for i in range(a, b)], dtype=np.int32)
        cv2.polylines(img, [pts], False, (95, 175, 95), 1, cv2.LINE_AA)

    # The head-drop geometry: the eye line, and the drop from it to the nose.
    left = shape[36:42].mean(axis=0)
    right = shape[42:48].mean(axis=0)
    lp = (int(round(left[0] * scale + off_x)), int(round(left[1] * scale + off_y)))
    rp = (int(round(right[0] * scale + off_x)), int(round(right[1] * scale + off_y)))
    mid = ((lp[0] + rp[0]) // 2, (lp[1] + rp[1]) // 2)
    nose = pt(30)
    col = (0, 0, 255) if head_down else (165, 165, 165)
    cv2.line(img, lp, rp, col, 1, cv2.LINE_AA)
    cv2.line(img, mid, nose, col, 1, cv2.LINE_AA)
    cv2.circle(img, nose, 3, col, -1, cv2.LINE_AA)


def draw_alert_frame(img, colour):
    """A border in the alert colour.

    The state word changes and the buzzer sounds, but a recording loses the
    buzzer and a viewer reading the road, not the HUD, can miss the word. A
    border is the one thing that cannot be missed on a screen or on film.
    """
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, 0), (w - 1, h - 1), colour, 14)


def write_session_summary(source, started, ended, episodes, peak_score,
                          longest_closure, path="last_session.txt"):
    """
    Print the drive, and leave a copy on disk.

    All of this was already being tracked and then dropped when the window
    closed. These are the numbers a write-up or a demo wants afterwards, and
    nobody stops to note them down while the alarm is going off.
    """
    if started is None:
        print("\nNo calibrated session to summarise.")
        return
    minutes = max(ended - started, 0.0) / 60.0
    lines = ["Sentra session summary",
             "  source            {}".format(source),
             "  monitored         {:.1f} min".format(minutes),
             "  peak PERCLOS      {:.1f}%".format(peak_score * 100),
             "  longest closure   {:.2f} s".format(longest_closure)]
    if episodes:
        for kind in sorted(episodes):
            lines.append("  {:<17} {}".format(kind.lower(), episodes[kind]))
        if minutes > 0:
            lines.append("  events/hour       {:.1f}".format(
                sum(episodes.values()) / minutes * 60.0))
    else:
        lines.append("  no alerts raised")
    text = "\n".join(lines)
    print("\n" + text)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("  written to        {}".format(path))
    except (IOError, OSError) as exc:
        print("  (could not write {}: {})".format(path, exc))


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


def _post(path, payload):
    """Fire-and-forget POST to the relay.

    Runs on its own thread and swallows every error: the frame loop must not
    stall on a slow request, and wifi dropping out must not take the detector
    down mid-drive.
    """
    if not API_URL or requests is None:
        return

    def send():
        try:
            requests.post(API_URL + path, json=payload,
                          headers={"X-API-Key": API_KEY}, timeout=4)
        except Exception as exc:
            print("Relay unreachable: {}".format(exc))

    Thread(target=send, daemon=True).start()


def report_event(kind, seconds):
    """One episode, for the app's history page."""
    _post("/events", {"kind": kind, "seconds": round(max(seconds, 0.0), 2)})


def report_status(state, score):
    """Heartbeat, so the app can show the live state."""
    _post("/status", {"state": state, "perclos": round(score, 4)})


# --------------------------------------------------------- app settings -----
# The switches on the phone's Settings page. Seeded with everything on, so a
# detector that has never reached the relay still gives the driver every alert
# it can -- failing quiet would be the wrong way round for a safety feature.
_settings_lock = Lock()
_settings = {"buzzer_on": True, "voice_alert_on": True}


def setting(name):
    """Read one switch. Cheap enough to call from the frame loop."""
    with _settings_lock:
        return _settings.get(name, True)


def _poll_settings():
    """Keep the local copy of the switches fresh, forever.

    On its own thread: a request to a relay that has gone away takes seconds to
    time out, and the frame loop cannot afford to wait on that. A failed poll is
    ignored rather than reset to defaults, so a wifi blip does not flip the
    driver's choices back on behind their back.
    """
    global _settings
    while True:
        try:
            res = requests.get(API_URL + "/settings",
                               headers={"X-API-Key": API_KEY}, timeout=4)
            if res.status_code == 200:
                body = res.json()
                fresh = {"buzzer_on": bool(body.get("buzzer_on", True)),
                         "voice_alert_on": bool(body.get("voice_alert_on", True))}
                with _settings_lock:
                    # Replaced wholesale rather than updated key by key, so the
                    # frame loop can never read a half-applied pair.
                    _settings = fresh
        except Exception:
            pass        # last known good values stay in force
        time.sleep(SETTINGS_EVERY)


def start_settings_poll():
    if not API_URL or requests is None:
        return          # nothing to poll; the defaults above stand
    Thread(target=_poll_settings, daemon=True).start()


# -------------------------------------------------------------- arduino -----
# The board runs vigiwatch.ino: buzzer on D2, LED on D4, 9600 baud, one
# newline-terminated command per line -- BUZZ, BUZZOFF, LEDON, LEDOFF, OFF and
# PING. Ported from sdsd.py, the pre-PERCLOS version, which is where this code
# earned each of its comments.
#
# Writes are locked because the buzzer fires from its own thread while the main
# loop drives the LED, and two interleaved writes reach the board as one
# unparseable line.
_serial_lock = Lock()
_ser = None
_led_on = False           # mirrors the board, so we only write on a change
_reconnecting = False     # one rescan at a time, not one per failed write


def open_arduino(port, baudrate=ARDUINO_BAUD):
    """Open a port and make whoever answers identify itself.

    Windows lists its Bluetooth COM ports right next to the Nano and those open
    perfectly well, so without the PING check VigiWatch would report itself
    connected to a port that never reaches the buzzer.
    """
    s = None
    try:
        print("Arduino: trying {}...".format(port))
        s = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2.0)             # opening the port resets the board
        s.reset_input_buffer()
        # Ask more than once. A Nano still finishing its bootloader swallows the
        # first line, and one missed reply would write the real board off.
        for _ in range(3):          # readline blocks up to 1 s per try
            s.write(b"PING\n")
            s.flush()
            if s.readline().decode(errors="ignore").strip() == "VIGIWATCH":
                return s
        print("Arduino: {} did not answer PING - not the Sentra board"
              .format(port))
    except Exception as exc:
        print("Arduino: {} failed: {}".format(port, exc))

    # Every path that did not return has to hand the port back, or it stays
    # locked against the next attempt.
    if s is not None:
        try:
            s.close()
        except Exception:
            pass
    return None


def connect_arduino(preferred=""):
    """Find the board and keep it. Returns True if one answered."""
    global _ser, _led_on

    if serial is None:
        print("Arduino: pyserial not installed (pip install pyserial) - "
              "buzzer and LED disabled")
        return False

    if preferred:
        candidates = [preferred]
    else:
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("Arduino: no serial ports found - buzzer and LED disabled")
            return False
        # Ports that name a USB-serial chip first. Bluetooth is never the Nano
        # and each wasted probe costs about three seconds of startup.
        named = [p.device for p in ports
                 if any(k in p.description.upper() for k in ARDUINO_KEYWORDS)]
        candidates = named + [p.device for p in ports
                              if p.device not in named
                              and "BLUETOOTH" not in p.description.upper()]

    for port in candidates:
        found = open_arduino(port)
        if found is not None:
            with _serial_lock:
                _ser = found
                # That open just reset the board, so its LED is off again. The
                # mirror has to agree, or set_led(True) sees no change and the
                # LED never lights again for the rest of the run.
                _led_on = False
            print("Arduino: connected on {}".format(port))
            return True

    print("Arduino: no board answered. Check the USB cable, close the Arduino "
          "IDE, and make sure vigiwatch.ino is the sketch on the board.")
    return False


def arduino_connected():
    with _serial_lock:
        return _ser is not None and _ser.is_open


def _reconnect_async():
    """Rescan without stalling whoever noticed the board was gone."""
    global _reconnecting
    try:
        connect_arduino()
    finally:
        with _serial_lock:
            _reconnecting = False


def send_arduino(cmd):
    """Send one command. Returns True if it went out."""
    global _ser, _reconnecting

    with _serial_lock:
        if _ser is None or not _ser.is_open:
            return False
        try:
            _ser.write(cmd.encode() + b"\n")
            _ser.flush()
            return True
        except Exception as exc:
            print("Arduino: '{}' failed: {}".format(cmd, exc))
            try:
                _ser.close()
            except Exception:
                pass
            _ser = None

    # The cable came out mid-run. Rescan off the main thread: probing a port
    # costs seconds each and there is still a video feed to draw.
    with _serial_lock:
        if _reconnecting:
            return False
        _reconnecting = True
    print("Arduino: reconnecting...")
    Thread(target=_reconnect_async, daemon=True).start()
    return False


# Bumped whenever a buzz starts or is silenced. A timer only ever stops the
# buzz it started: without this, an alert firing while the previous one was
# still counting down would be cut short by the older thread.
_buzz_lock = Lock()
_buzz_token = 0


def trigger_buzzer():
    """Sound the buzzer for BUZZ_SECONDS, then silence it.

    Always call this on its own thread -- it sleeps for the duration. The
    sketch runs a timer of its own as well, so even a crash on this side cannot
    leave the buzzer latched on; that is exactly what the old board used to do.
    """
    global _buzz_token
    if not send_arduino("BUZZ"):
        return

    with _buzz_lock:
        # Claimed after the write, not before. A BUZZ that never reached the
        # board must not invalidate the timer of a buzz that is still running,
        # or that one loses its BUZZOFF and rides the sketch's timer instead.
        _buzz_token += 1
        mine = _buzz_token
    print("Buzzer on for {:.0f} s (s to silence)".format(BUZZ_SECONDS))

    time.sleep(BUZZ_SECONDS)
    with _buzz_lock:
        if mine != _buzz_token:
            return          # superseded by a newer alert, or already silenced
    send_arduino("BUZZOFF")


def stop_buzzer():
    """Cut the buzzer now -- the s key, or the driver coming round early."""
    global _buzz_token
    with _buzz_lock:
        _buzz_token += 1    # any timer still counting down is now stale
    send_arduino("BUZZOFF")


def set_led(on):
    """Drive the LED, lit for as long as the driver reads as drowsy.

    Edge-triggered: the frame loop calls this every frame and 9600 baud will not
    carry a command per frame.
    """
    global _led_on
    if on == _led_on:
        return
    if send_arduino("LEDON" if on else "LEDOFF"):
        _led_on = on


def close_arduino():
    """Everything off, port released. Nothing stays lit or sounding after quit."""
    global _ser
    send_arduino("OFF")
    with _serial_lock:
        if _ser is not None:
            try:
                _ser.close()
            except Exception:
                pass
            _ser = None


# ---------------------------------------------------------------- camera -----
def open_camera(index):
    """Open a webcam and prove it actually delivers frames.

    isOpened() is not enough on Windows. A camera that is disabled in Device
    Manager, or already held by another program, still opens cleanly through
    Media Foundation and then returns nothing for as long as you ask -- which
    from inside the loop is indistinguishable from a driver who never sat down.
    Failing here, by name, beats running blind and blaming the detector.
    """
    for name, api in CAMERA_BACKENDS:
        cap = cv2.VideoCapture(index, api)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        for _ in range(CAMERA_WARMUP_READS):
            ok, frame = cap.read()
            if ok and frame is not None:
                print("Camera {} open on {}, {}x{}".format(
                    index, name, frame.shape[1], frame.shape[0]))
                return cap
            time.sleep(0.1)
        print("  camera {} opened on {} but sent no frames".format(index, name))
        cap.release()
    return None


# ----------------------------------------------------------------- main -----
def main():
    ap = argparse.ArgumentParser(description="Sentra drowsiness detector (PERCLOS)")
    ap.add_argument("-w", "--webcam", type=int, default=0, help="webcam index")
    ap.add_argument("--arduino-port", default=os.environ.get("ARDUINO_PORT", ""),
                    help="serial port of the board, e.g. COM5. Default: scan "
                         "for it, which costs a few seconds at startup.")
    ap.add_argument("--no-arduino", action="store_true",
                    help="skip the board entirely; screen and voice alerts only")
    ap.add_argument("--video", default="",
                    help="read a clip instead of the camera. Timing comes off "
                         "the clip's frame rate, so a run is repeatable.")
    ap.add_argument("--fast", action="store_true",
                    help="with --video, do not pace playback to real time")
    ap.add_argument("--no-head-drop", action="store_true",
                    help="disable head-drop detection, leaving eyes only")
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
    tracker = FaceTracker(cascade_path)
    predictor = dlib.shape_predictor(predictor_path)

    # A clip instead of the camera. Worth having for two separate reasons:
    # the same footage can be replayed while the thresholds are being judged,
    # which a live face cannot do, and a demo stops depending on a webcam
    # working in a room nobody has tested.
    src_fps = None
    if args.video:
        cap = cv2.VideoCapture(args.video)
        if not cap.isOpened():
            print("Error: could not open video {}".format(args.video))
            return
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if not 1.0 <= src_fps <= 240.0:
            src_fps = 30.0
            print("Clip reports no usable frame rate; assuming {:.0f} fps"
                  .format(src_fps))
        print("Reading {} at {:.0f} fps".format(args.video, src_fps))
    else:
        cap = open_camera(args.webcam)
        if cap is None:
            print("Error: no frames from webcam {}. Check, in order:".format(
                args.webcam))
            print("  - another program has the camera. This detector already "
                  "running in another window is the usual culprit.")
            print("  - the camera is enabled: Device Manager > Cameras")
            print("  - Settings > Privacy & security > Camera allows desktop apps")
            print("  - a different camera is on another index: --webcam 1")
            print("  - or skip the camera entirely: --video clip.mp4")
            return

    # Hardware and switches. Both are optional and both fail quietly: no board
    # and no relay just means the alerts stay on this screen.
    arduino_enabled = not args.no_arduino
    if arduino_enabled:
        connect_arduino(args.arduino_port)
    start_settings_poll()

    calib = EyeCalibration()
    perclos = PerclosTracker()
    ear_history = deque(maxlen=EAR_SMOOTH_N)
    head = HeadTracker()
    head_drop_enabled = not args.no_head_drop
    score_history = deque()      # (timestamp, score), for the timeline strip
    frame_index = 0

    closed_since = None          # start of the current run of closed frames
    was_drowsy = False           # previous frame's verdict, for the LED edge
    perclos_armed = True         # False once the slow path has alerted, until
                                 # the score falls back to PERCLOS_REARM
    buzzer_muted = False         # s pressed; clears when the episode ends
    # Long ago, rather than zero. Reading a clip starts the clock near zero,
    # and a cooldown measured from 0.0 would swallow every alert in the first
    # few seconds of footage.
    long_ago = -1e9
    last_buzz = long_ago
    sleepy_sets = 0
    last_drowsy_alert = long_ago
    last_yawn_alert = long_ago
    last_no_face_alert = long_ago
    last_status_post = long_ago
    no_face_start = None
    fps = 0.0
    last_frame_time = 0.0 if src_fps is not None else time.time()

    # Session tally. All of it was already being computed and then thrown
    # away when the window closed.
    session_start = None
    peak_score = 0.0
    longest_closure = 0.0
    episodes = {}

    # Filming wants both: the mesh on, to show the model reading the face,
    # and off, for a clean shot of the driver. Cheaper as a key than as two
    # takes.
    show_mesh = True

    cv2.namedWindow("Sentra", cv2.WINDOW_NORMAL)
    print("\n  Sentra - Keeps You in Sight\n")
    print("Look at the camera with your eyes open normally.")
    print("Calibrating for {:.0f} seconds...  (q = quit, c = recalibrate{})"
          .format(CALIB_SECONDS, ", s = silence buzzer" if arduino_enabled else ""))

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("End of clip" if src_fps is not None
                      else "Failed to grab frame")
                break

            # Time comes off the clip's own frame rate when reading a file.
            # Every window in here -- PERCLOS, the calibration, the cooldowns
            # -- is measured in seconds, so playing footage faster or slower
            # than life would otherwise change the verdict it reaches.
            if src_fps is not None:
                frame_index += 1
                now = frame_index / src_fps
            else:
                now = time.time()
            dt = now - last_frame_time
            last_frame_time = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps else 1.0 / dt

            scale = PROC_WIDTH / frame.shape[1]
            frame = cv2.resize(frame, (PROC_WIDTH, int(frame.shape[0] * scale)))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # The tracker equalises its own copy for detection. The landmark
            # predictor is more accurate on the untouched image, so it gets
            # this one.
            rect = tracker.find(gray, now)

            ear = None
            mouth_opening = 0.0
            openness = 1.0
            head_down = False
            contours = []
            landmarks = None

            if rect is not None:
                no_face_start = None
                shape = face_utils.shape_to_np(predictor(gray, rect))

                raw_ear, left_eye, right_eye = compute_ear(shape)
                ear_history.append(raw_ear)
                ear = float(np.median(ear_history))     # smooth out landmark jitter
                mouth_opening = lip_distance(shape)

                # Kept as points and drawn on the full-size frame later, so the
                # outlines stay sharp instead of being upscaled with the image.
                contours = [cv2.convexHull(left_eye), cv2.convexHull(right_eye),
                            shape[48:60]]
                landmarks = shape

                if not calib.done:
                    # Coasted frames sit this one out. Calibration is a
                    # one-shot measurement that fixes the thresholds for the
                    # whole run, so landmarks taken off a remembered box skew
                    # far more here than the same frame ever would mid-drive.
                    if not tracker.coasting():
                        calib.add(ear, now)
                        head.add_sample(shape)
                    if calib.maybe_finish(now):
                        head.finish_calibration()
                        session_start = now
                else:
                    openness = calib.openness(ear)
                    perclos.update(now, openness)
                    # Eye openness only, deliberately. PERCLOS is a measure of
                    # eye closure and nothing else; mixing posture into it
                    # would make the number mean something the research it
                    # comes from never meant. Posture is tracked beside it.
                    head_down = head_drop_enabled and head.update(shape, now)

                    # Track how long the eyes have been continuously shut.
                    if openness <= PERCLOS_CLOSED_LEVEL:
                        if closed_since is None:
                            closed_since = now
                    else:
                        closed_since = None
            else:
                closed_since = None
                # Losing the face is not evidence that the driver is fine. The
                # head going down is what takes it out of frame, so a head
                # that was already dropping goes on counting as dropped.
                head_down = head_drop_enabled and head.update_no_face(now)
                if no_face_start is None:
                    no_face_start = now
                elif (now - no_face_start > NO_FACE_TIMEOUT
                      and now - last_no_face_alert >= NO_FACE_TIMEOUT):
                    last_no_face_alert = now
                    if setting("voice_alert_on"):
                        Thread(target=speak,
                               args=("Driver not detected! Stay alert!",),
                               daemon=True).start()

            # ---------- drowsiness decision ----------
            score = perclos.value()
            coverage = perclos.coverage()
            eyes_shut_for = (now - closed_since) if closed_since else 0.0
            head_down_for = head.down_for(now) if head_down else 0.0

            if not calib.done:
                state, colour = "CALIBRATING", (0, 200, 255)
            elif eyes_shut_for >= MICROSLEEP_SECONDS:
                state, colour = "MICROSLEEP", (0, 0, 255)
            elif head_down_for >= HEAD_DROP_SECONDS:
                # Ranked with microsleep rather than below the PERCLOS states:
                # a head that has been down for most of a second is not a
                # statistical trend, it is happening now.
                state, colour = "HEAD DOWN", (0, 0, 255)
            elif rect is None:
                # Every reading below this line is stale the moment the face
                # goes: the eye timer is reset, and PERCLOS stops being fed
                # but keeps returning its last value, which on a driver who
                # was fine until a second ago is a low one. Falling through to
                # those checks is what used to paint a vanished driver green.
                # Amber, not red -- not monitoring is a warning, not an alarm.
                state, colour = "NO FACE", (0, 165, 255)
            elif coverage < PERCLOS_MIN_COVERAGE:
                state, colour = "WARMING UP", (0, 200, 255)
            elif score >= PERCLOS_ALERT:
                state, colour = "DROWSY", (0, 0, 255)
            elif score >= PERCLOS_WARN:
                state, colour = "FATIGUE WARNING", (0, 165, 255)
            else:
                state, colour = "ALERT", (0, 255, 0)

            # One line saying why, in the words a person would use.
            if state == "MICROSLEEP":
                reason = "eyes shut {:.1f}s".format(eyes_shut_for)
            elif state == "HEAD DOWN":
                reason = "head down {:.1f}s".format(head_down_for)
                if head.baseline and head.ratio:
                    reason += "   {:.0f}% of upright".format(
                        100.0 * head.ratio / head.baseline)
            elif state in ("DROWSY", "FATIGUE WARNING"):
                reason = "PERCLOS {:.1f}% of the last {:.0f}s".format(
                    score * 100, PERCLOS_WINDOW)
            elif state == "NO FACE":
                reason = "cannot see your face - not monitoring"
            elif state == "ALERT":
                reason = "eyes open"
            else:
                reason = ""

            # ---------- hardware ----------
            drowsy_now = state in ("DROWSY", "MICROSLEEP", "HEAD DOWN")
            if arduino_enabled:
                set_led(drowsy_now)     # edge-triggered inside set_led
                if not drowsy_now:
                    if was_drowsy:
                        # Eyes open again before the burst was up. Cut it now
                        # rather than make them sit through the rest of it.
                        stop_buzzer()
                    # Cleared on every clear frame, not just on the falling
                    # edge. Pressing s while already alert would otherwise
                    # leave the mute set with no edge coming to lift it, and
                    # swallow the buzzer for the whole of the NEXT episode.
                    buzzer_muted = False
            was_drowsy = drowsy_now

            if score < PERCLOS_REARM:
                perclos_armed = True

            if (drowsy_now and now - last_drowsy_alert >= DROWSY_COOLDOWN
                    and (state in ("MICROSLEEP", "HEAD DOWN") or perclos_armed)):
                last_drowsy_alert = now
                sleepy_sets += 1
                if state == "DROWSY":
                    # One episode, one alert from the slow path.
                    perclos_armed = False
                episodes[state] = episodes.get(state, 0) + 1
                if setting("voice_alert_on"):
                    # Tell the driver what is actually wrong. "Keep your eyes
                    # open" is the wrong instruction for a dropped head.
                    Thread(target=speak,
                           args=("Wake up! Head up!" if state == "HEAD DOWN"
                                 else "Wake up! Keep your eyes open!",),
                           daemon=True).start()
                if (arduino_enabled and setting("buzzer_on")
                        and not buzzer_muted
                        and now - last_buzz >= BUZZ_COOLDOWN):
                    last_buzz = now
                    # Threaded: a write to a board that has just been unplugged
                    # blocks, and a stalled frame loop is a stalled detector.
                    Thread(target=trigger_buzzer, daemon=True).start()
                if sleepy_sets % WHATSAPP_EVERY_N_ALERTS == 0:
                    send_whatsapp(WHATSAPP_NUMBER, "User appears drowsy! Please check.")

                # A microsleep has a literal duration. A PERCLOS alert does not,
                # so report the time the eyes spent shut inside the window --
                # which is what the score actually measures.
                report_event(state, eyes_shut_for if state == "MICROSLEEP"
                             else head_down_for if state == "HEAD DOWN"
                             else score * PERCLOS_WINDOW)

            # ---------- yawn ----------
            if mouth_opening > YAWN_THRESH and now - last_yawn_alert >= YAWN_COOLDOWN:
                last_yawn_alert = now
                if setting("voice_alert_on"):
                    Thread(target=speak, args=("Stop yawning! Stay focused!",),
                           daemon=True).start()
                episodes["YAWN"] = episodes.get("YAWN", 0) + 1
                report_event("YAWN", 0.0)

            if now - last_status_post >= STATUS_EVERY:
                last_status_post = now
                report_status(state, score)

            # ---------- history ----------
            score_history.append((now, score))
            while score_history and now - score_history[0][0] > TIMELINE_SECONDS:
                score_history.popleft()
            peak_score = max(peak_score, score)
            longest_closure = max(longest_closure, eyes_shut_for)

            # ---------- draw ----------
            display, disp_scale, off_x, off_y = fit_letterbox(frame)
            for pts in contours:
                scaled = np.round(pts.reshape(-1, 2) * disp_scale
                                  + (off_x, off_y)).astype(np.int32)
                cv2.drawContours(display, [scaled], -1, (0, 255, 0), 1, cv2.LINE_AA)

            # Under the HUD and the eye outlines, so neither is drawn over.
            if show_mesh and landmarks is not None:
                draw_landmarks(display, landmarks, disp_scale, off_x, off_y,
                               head_down)

            draw_hud(display, state, colour, score, coverage, calib,
                     calib.elapsed(now), ear, openness, mouth_opening, fps,
                     arduino_connected() if arduino_enabled else None,
                     head.ratio if (head_drop_enabled and rect is not None)
                     else None, head.baseline, reason)

            if calib.done:
                draw_timeline(display, perclos, score_history, now,
                              HUD_MARGIN, DISPLAY_H - 180, 430)

            # Said on screen, not just in the write-up. Anyone watching a
            # recording of a detector has a right to know it is a recording,
            # and being the one to say so first is worth more than hoping
            # nobody wonders.
            if args.video:
                draw_text(display, "RECORDED CLIP", DISPLAY_W // 2, 40, 0.55,
                          (120, 200, 255), 1, align="center")

            # Last, so the border sits over everything else.
            if drowsy_now:
                draw_alert_frame(display, colour)

            cv2.imshow("Sentra", display)
            # A clip is paced to its own frame rate so it plays at life speed.
            # --fast drops the pacing, for when the point is to get through
            # footage rather than to watch it.
            delay = 1
            if src_fps is not None and not args.fast:
                delay = max(1, int(1000.0 / src_fps))
            key = cv2.waitKey(delay) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s") and arduino_enabled:
                # Silences the buzzer for the rest of THIS episode, not just
                # the current burst -- cutting one burst was useless, the next
                # alert simply started another. It re-arms as soon as the
                # driver reads alert again, so this cannot mute the drive.
                # The screen alert and the voice are untouched.
                stop_buzzer()
                buzzer_muted = True
                print("Buzzer muted until you read alert again")
            if key == ord("m"):
                show_mesh = not show_mesh
            if key == ord("c"):
                print("Recalibrating - look at the camera with your eyes open.")
                calib.reset()
                perclos.clear()
                ear_history.clear()
                head.reset()
                score_history.clear()
                closed_since = None

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        # Hardware first: a crash on the way out must not leave the buzzer
        # sounding with no window left to close.
        if arduino_enabled:
            close_arduino()
        cap.release()
        cv2.destroyAllWindows()
        write_session_summary(args.video or "webcam {}".format(args.webcam),
                              session_start, last_frame_time, episodes,
                              peak_score, longest_closure)
        print("Sentra terminated")


if __name__ == "__main__":
    main()
