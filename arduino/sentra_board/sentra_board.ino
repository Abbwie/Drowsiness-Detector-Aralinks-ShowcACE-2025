/*
  Sentra - the alert board.

  The detector runs on the laptop, because it needs the webcam and dlib. This
  board is everything the driver can hear and see without looking at a screen,
  which matters: a HUD only helps someone already watching the screen, and a
  driver who has stopped watching the road is not watching that either.

  vigiwatch.py sends one newline-terminated command at 9600 baud:
    BUZZ     buzzer on, auto-off after BUZZ_MS (a WhatsApp alert was sent)
    BUZZOFF  buzzer off now
    LEDON    LED on  - drowsiness detected
    LEDOFF   LED off - eyes open again
    OFF      everything off (sent when VigiWatch exits)
    PING     replies VIGIWATCH, so the Python side can tell this board apart
             from the Bluetooth COM ports Windows lists next to it

  The buzzer runs on a millis() deadline instead of delay(), so the board keeps
  reading serial while it sounds and stops on its own even if the PC crashes or
  is unplugged mid-alert.
*/

const int BUZZER_PIN = 2;
const int LED_PIN    = 4;

// 0 drives the pin with a square wave through tone(); 1 just holds it HIGH.
//
// 0 is the safer default of the two. A passive buzzer -- a bare piezo disc
// with no oscillator of its own -- is silent on a plain HIGH and needs a
// driven frequency, while an active buzzer sounds on either. Holding HIGH on
// a passive one looks exactly like a dead buzzer next to an LED that works,
// because digitalWrite is the right thing for the LED and the wrong thing
// here. Set this to 1 only if you know yours is active and prefer its tone.
#define ACTIVE_BUZZER 0
const int BUZZ_TONE_HZ = 2000;        // used only when ACTIVE_BUZZER is 0

const unsigned long BUZZ_MS = 5000;  // how long one BUZZ lasts

bool buzzing = false;
unsigned long buzzUntil = 0;
String cmd = "";

void buzzerOn() {
#if ACTIVE_BUZZER
  digitalWrite(BUZZER_PIN, HIGH);
#else
  tone(BUZZER_PIN, BUZZ_TONE_HZ);
#endif
  buzzing = true;
  buzzUntil = millis() + BUZZ_MS;
}

void buzzerOff() {
#if ACTIVE_BUZZER
  digitalWrite(BUZZER_PIN, LOW);
#else
  noTone(BUZZER_PIN);
#endif
  buzzing = false;
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  buzzerOff();
  digitalWrite(LED_PIN, LOW);
  cmd.reserve(16);
  Serial.begin(9600);
}

void handle(String c) {
  c.trim();
  if (c == "BUZZ") {
    buzzerOn();
  } else if (c == "BUZZOFF") {
    buzzerOff();
  } else if (c == "LEDON") {
    digitalWrite(LED_PIN, HIGH);
  } else if (c == "LEDOFF") {
    digitalWrite(LED_PIN, LOW);
  } else if (c == "OFF") {
    buzzerOff();
    digitalWrite(LED_PIN, LOW);
  } else if (c == "PING") {
    Serial.println("VIGIWATCH");
  }
}

void loop() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (cmd.length() > 0) {
        handle(cmd);
        cmd = "";
      }
    } else if (cmd.length() < 15) {
      cmd += ch;
    }
  }

  // Deadline compared as a signed difference so it survives the millis() wrap.
  if (buzzing && (long)(millis() - buzzUntil) >= 0) {
    buzzerOff();
  }
}
