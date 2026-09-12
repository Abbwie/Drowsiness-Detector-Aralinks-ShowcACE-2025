import 'package:flutter/material.dart';

import 'api.dart';
import 'theme.dart';

const _days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

String formatDate(DateTime t) => '${_months[t.month - 1]} ${t.day}';

String formatTime(DateTime t) {
  final h = t.hour % 12 == 0 ? 12 : t.hour % 12;
  final m = t.minute.toString().padLeft(2, '0');
  final ampm = t.hour < 12 ? 'AM' : 'PM';
  return '$h:$m $ampm';
}

String formatDay(DateTime t) {
  final now = DateTime.now();
  final diff = DateTime(now.year, now.month, now.day)
      .difference(DateTime(t.year, t.month, t.day))
      .inDays;
  if (diff == 0) return 'Today';
  if (diff == 1) return 'Yesterday';
  return _days[t.weekday - 1];
}

/// Plain-language name for a detector state, plus the colour it earns.
/// The raw values come straight from the detector's HUD.
({String label, Color colour}) describeState(LiveStatus s) {
  if (!s.online) return (label: 'Detector offline', colour: muted);
  return switch (s.state) {
    'ALERT' => (label: 'Awake', colour: green),
    'FATIGUE WARNING' => (label: 'Getting tired', colour: amber),
    'DROWSY' => (label: 'Drowsy', colour: red),
    'MICROSLEEP' => (label: 'Microsleep', colour: red),
    'CALIBRATING' => (label: 'Calibrating', colour: muted),
    'WARMING UP' => (label: 'Warming up', colour: muted),
    _ => (label: s.state, colour: muted),
  };
}

class Logo extends StatelessWidget {
  final double size;
  const Logo({super.key, this.size = 40});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            color: red,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(Icons.warning_amber_rounded,
              color: Colors.white, size: size * 0.6),
        ),
        SizedBox(width: size * 0.3),
        Text(
          'VigiWatch',
          style: TextStyle(fontSize: size * 0.55, fontWeight: FontWeight.bold),
        ),
      ],
    );
  }
}

/// The live tile: what the detector is seeing this second.
class StatusCard extends StatelessWidget {
  final LiveStatus status;
  const StatusCard({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final d = describeState(status);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: status.online ? d.colour : line),
      ),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(color: d.colour, shape: BoxShape.circle),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(d.label,
                    style: const TextStyle(
                        fontSize: 17, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text(
                  status.online
                      ? 'Eyes closed ${(status.perclos * 100).round()}% of the last 30s'
                      : 'Start the detector on the laptop to see live status',
                  style: const TextStyle(fontSize: 12, color: muted),
                ),
              ],
            ),
          ),
          if (status.online)
            Text(formatTime(status.updatedAt),
                style: const TextStyle(fontSize: 12, color: muted)),
        ],
      ),
    );
  }
}

class EventTile extends StatelessWidget {
  final DrowsyEvent event;
  final bool showDay;

  const EventTile({super.key, required this.event, this.showDay = true});

  @override
  Widget build(BuildContext context) {
    final when = showDay
        ? '${formatDay(event.time)}, ${formatTime(event.time)}'
        : formatTime(event.time);

    // A yawn has no meaningful duration -- the detector reports it as 0.
    final detail =
        event.kind == 'YAWN' ? 'Yawn' : '${event.seconds.toStringAsFixed(1)}s';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      decoration: BoxDecoration(
        color: card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: line),
      ),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: event.kind == 'YAWN' ? muted : red,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(when, style: const TextStyle(fontSize: 14))),
          if (event.kind == 'MICROSLEEP') ...[
            const Text('microsleep', style: TextStyle(fontSize: 11, color: red)),
            const SizedBox(width: 8),
          ],
          Text(detail, style: const TextStyle(fontSize: 13, color: muted)),
        ],
      ),
    );
  }
}

class WeekChart extends StatelessWidget {
  final List<int> counts;
  const WeekChart({super.key, required this.counts});

  @override
  Widget build(BuildContext context) {
    final max = counts.isEmpty ? 0 : counts.reduce((a, b) => a > b ? a : b);
    final now = DateTime.now();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: line),
      ),
      child: SizedBox(
        height: 120,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: List.generate(7, (i) {
            final count = i < counts.length ? counts[i] : 0;
            final day = now.subtract(Duration(days: 6 - i));
            return Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    count == 0 ? '' : '$count',
                    style: const TextStyle(fontSize: 12, color: muted),
                  ),
                  const SizedBox(height: 4),
                  Expanded(
                    child: FractionallySizedBox(
                      alignment: Alignment.bottomCenter,
                      heightFactor: max == 0 ? 0 : count / max,
                      child: Container(
                        margin: const EdgeInsets.symmetric(horizontal: 5),
                        decoration: BoxDecoration(
                          color: red,
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _days[day.weekday - 1].substring(0, 1),
                    style: const TextStyle(fontSize: 12, color: muted),
                  ),
                ],
              ),
            );
          }),
        ),
      ),
    );
  }
}

/// Shown in place of a list when a request failed.
class ErrorNote extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const ErrorNote({super.key, required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: line),
      ),
      child: Column(
        children: [
          const Icon(Icons.cloud_off, color: muted),
          const SizedBox(height: 10),
          Text(message,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 13, color: muted)),
          const SizedBox(height: 10),
          TextButton(
            onPressed: onRetry,
            child: const Text('Try again', style: TextStyle(color: red)),
          ),
        ],
      ),
    );
  }
}
