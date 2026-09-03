import 'package:flutter/material.dart';
import 'mock_data.dart';
import 'theme.dart';

const _days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

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

class EventTile extends StatelessWidget {
  final DrowsyEvent event;
  final bool showDay;

  const EventTile({super.key, required this.event, this.showDay = true});

  @override
  Widget build(BuildContext context) {
    final label = showDay
        ? '${formatDay(event.time)}, ${formatTime(event.time)}'
        : formatTime(event.time);

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
            decoration: const BoxDecoration(color: red, shape: BoxShape.circle),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(label, style: const TextStyle(fontSize: 14))),
          Text(
            '${event.seconds}s',
            style: const TextStyle(fontSize: 13, color: muted),
          ),
        ],
      ),
    );
  }
}

class WeekChart extends StatelessWidget {
  const WeekChart({super.key});

  @override
  Widget build(BuildContext context) {
    final counts = weekCounts;
    final max = counts.reduce((a, b) => a > b ? a : b);
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
            final count = counts[i];
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
