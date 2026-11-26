import 'package:flutter/material.dart';

import 'theme.dart';

/// What Sentra records, and what it cannot do.
///
/// Both halves belong in the product rather than only in a write-up. A driver
/// being watched by a camera is owed a plain account of what the camera sends
/// on, and a safety tool that overstates itself is worse than one that admits
/// where it fails -- someone who believes this will catch every lapse will
/// drive tireder than someone who knows it might not.
///
/// Every line here is checkable against the detector's source. If the detector
/// changes what it sends, this page is wrong until it is edited too.
class PrivacyPage extends StatelessWidget {
  const PrivacyPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Your data')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [
          _Section(
            title: 'What leaves the laptop',
            body: 'Two kinds of message, and nothing else:',
            bullets: [
              'When an episode ends: what kind it was (drowsy, microsleep, '
                  'head down or yawn) and how many seconds it lasted.',
              'Every few seconds while running: the current state and the '
                  'PERCLOS score behind it.',
            ],
          ),
          _Section(
            title: 'What never leaves it',
            body: 'The camera feed is measured on the laptop and each frame is '
                'thrown away as the next one arrives.',
            bullets: [
              'No video and no still images are stored or sent.',
              'No face landmarks, eye measurements or face prints are sent.',
              'Nothing that could identify your face is kept after the frame '
                  'it came from.',
            ],
          ),
          _Section(
            title: 'What you can delete',
            body: 'The history on the previous screen is the whole record. '
                'Remove a single episode by swiping it, or clear all of it '
                'from the history page. Deleting removes it from the server '
                'too, not just from this phone.',
          ),
          _Divider(),
          _Section(
            title: 'What Sentra cannot do',
            body: 'It measures eyelids and head position. That is not the same '
                'as measuring sleep, and the gap matters:',
            bullets: [
              'It has to see your face. Darkness, strong light behind you, '
                  'sunglasses or anything over the camera stops it. When that '
                  'happens it says so rather than showing you as awake.',
              'It can miss drowsiness in someone whose eyes stay open, and it '
                  'can read an unusually long blink as a closure.',
              'The face-finding models it relies on were trained on datasets '
                  'that do not represent everyone equally, so it is not '
                  'equally accurate for every face.',
              'It knows nothing about the road. It cannot tell a yawn in '
                  'traffic from a yawn on an empty motorway.',
            ],
          ),
          _Section(
            title: 'It is an alert, not permission',
            body: 'Sentra is there to catch the moment you stop noticing that '
                'you are tired. It is not a reason to keep driving while you '
                'are. If it wakes you, stop and rest -- that is the only thing '
                'that actually fixes being tired.',
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final String body;
  final List<String> bullets;

  const _Section({
    required this.title,
    required this.body,
    this.bullets = const [],
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          Text(body,
              style: const TextStyle(fontSize: 13, color: muted, height: 1.45)),
          if (bullets.isNotEmpty) const SizedBox(height: 10),
          for (final b in bullets)
            Padding(
              padding: const EdgeInsets.only(bottom: 7),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 6, right: 9),
                    child: _Dot(),
                  ),
                  Expanded(
                    child: Text(b,
                        style: const TextStyle(
                            fontSize: 13, color: muted, height: 1.45)),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot();

  @override
  Widget build(BuildContext context) => Container(
        width: 5,
        height: 5,
        decoration: const BoxDecoration(color: red, shape: BoxShape.circle),
      );
}

class _Divider extends StatelessWidget {
  const _Divider();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 10),
        child: Divider(color: line, height: 1),
      );
}
