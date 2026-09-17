
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
PROC_WIDTH = 640          # width we run detection at. Bigger = better landmark
                        

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
             ear, openness, mouth_opening, fps, arduino_ok=None):
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

    # s is only listed when there is a board to silence.
    hints = "q quit    c recalibrate"
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


# ----------------------------------------------------------------- main -----
def main():
    ap = argparse.ArgumentParser(description="Sentra drowsiness detector (PERCLOS)")
    ap.add_argument("-w", "--webcam", type=int, default=0, help="webcam index")
    ap.add_argument("--arduino-port", default=os.environ.get("ARDUINO_PORT", ""),
                    help="serial port of the board, e.g. COM5. Default: scan "
                         "for it, which costs a few seconds at startup.")
    ap.add_argument("--no-arduino", action="store_true",
                    help="skip the board entirely; screen and voice alerts only")
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

    # Hardware and switches. Both are optional and both fail quietly: no board
    # and no relay just means the alerts stay on this screen.
    arduino_enabled = not args.no_arduino
    if arduino_enabled:
        connect_arduino(args.arduino_port)
    start_settings_poll()

    calib = EyeCalibration()
    perclos = PerclosTracker()
    ear_history = deque(maxlen=EAR_SMOOTH_N)

    closed_since = None          # start of the current run of closed frames
    was_drowsy = False           # previous frame's verdict, for the LED edge
    perclos_armed = True         # False once the slow path has alerted, until
                                 # the score falls back to PERCLOS_REARM
    buzzer_muted = False         # s pressed; clears when the episode ends
    last_buzz = 0.0
    sleepy_sets = 0
    last_drowsy_alert = 0.0
    last_yawn_alert = 0.0
    last_no_face_alert = 0.0
    last_status_post = 0.0
    no_face_start = None
    fps = 0.0
    last_frame_time = time.time()

    cv2.namedWindow("Sentra", cv2.WINDOW_NORMAL)
    print("\n  Sentra - Keeps You in Sight\n")
    print("Look at the camera with your eyes open normally.")
    print("Calibrating for {:.0f} seconds...  (q = quit, c = recalibrate{})"
          .format(CALIB_SECONDS, ", s = silence buzzer" if arduino_enabled else ""))

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
                    if setting("voice_alert_on"):
                        Thread(target=speak,
                               args=("Driver not detected! Stay alert!",),
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

            # ---------- hardware ----------
            drowsy_now = state in ("DROWSY", "MICROSLEEP")
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
                    and (state == "MICROSLEEP" or perclos_armed)):
                last_drowsy_alert = now
                sleepy_sets += 1
                if state == "DROWSY":
                    # One episode, one alert from the slow path.
                    perclos_armed = False
                if setting("voice_alert_on"):
                    Thread(target=speak, args=("Wake up! Keep your eyes open!",),
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
                             else score * PERCLOS_WINDOW)

            # ---------- yawn ----------
            if mouth_opening > YAWN_THRESH and now - last_yawn_alert >= YAWN_COOLDOWN:
                last_yawn_alert = now
                if setting("voice_alert_on"):
                    Thread(target=speak, args=("Stop yawning! Stay focused!",),
                           daemon=True).start()
                report_event("YAWN", 0.0)

            if now - last_status_post >= STATUS_EVERY:
                last_status_post = now
                report_status(state, score)

            # ---------- draw ----------
            display, disp_scale, off_x, off_y = fit_letterbox(frame)
            for pts in contours:
                scaled = np.round(pts.reshape(-1, 2) * disp_scale
                                  + (off_x, off_y)).astype(np.int32)
                cv2.drawContours(display, [scaled], -1, (0, 255, 0), 1, cv2.LINE_AA)

            draw_hud(display, state, colour, score, coverage, calib,
                     calib.elapsed(now), ear, openness, mouth_opening, fps,
                     arduino_connected() if arduino_enabled else None)

            cv2.imshow("Sentra", display)
            key = cv2.waitKey(1) & 0xFF
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
            if key == ord("c"):
                print("Recalibrating - look at the camera with your eyes open.")
                calib.reset()
                perclos.clear()
                ear_history.clear()
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
        print("Sentra terminated")


if __name__ == "__main__":
    main()
