import 'package:flutter/material.dart';
import 'mock_data.dart';
import 'theme.dart';

// ---------------- formatting helpers (no intl dependency) ----------------

const weekdayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const monthNames = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

String formatTime(DateTime t) {
  final h = t.hour % 12 == 0 ? 12 : t.hour % 12;
  final m = t.minute.toString().padLeft(2, '0');
  final suffix = t.hour < 12 ? 'AM' : 'PM';
  return '$h:$m $suffix';
}

String formatDayLabel(DateTime t) {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final day = DateTime(t.year, t.month, t.day);
  final diff = today.difference(day).inDays;
  if (diff == 0) return 'Today';
  if (diff == 1) return 'Yesterday';
  if (diff < 7) return weekdayNames[day.weekday - 1];
  return '${monthNames[day.month - 1]} ${day.day}';
}

String formatSeconds(Duration d) {
  final s = d.inMilliseconds / 1000;
  return '${s.toStringAsFixed(1)}s';
}

String formatAgo(Duration d) {
  if (d.inMinutes < 60) return '${d.inMinutes}m ago';
  if (d.inHours < 24) return '${d.inHours}h ago';
  return '${d.inDays}d ago';
}

Color severityColor(Severity s) => switch (s) {
      Severity.mild => VW.muted,
      Severity.moderate => VW.amber,
      Severity.critical => VW.red,
    };

// ---------------- brand ----------------

class BrandMark extends StatelessWidget {
  final double size;
  final bool showTagline;
  const BrandMark({super.key, this.size = 44, this.showTagline = true});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            color: VW.red,
            borderRadius: BorderRadius.circular(size * 0.28),
          ),
          child: Icon(Icons.warning_amber_rounded,
              color: Colors.white, size: size * 0.62),
        ),
        SizedBox(width: size * 0.32),
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'VigiWatch',
              style: TextStyle(
                fontSize: size * 0.60,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.5,
                height: 1.05,
              ),
            ),
            if (showTagline)
              Text(
                'Drivers Edition',
                style: TextStyle(
                  fontSize: size * 0.26,
                  color: VW.muted,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.6,
                ),
              ),
          ],
        ),
      ],
    );
  }
}

// ---------------- cards ----------------

class StatCard extends StatelessWidget {
  final String label;
  final String value;
  final String? sub;
  final IconData icon;
  final Color accent;

  const StatCard({
    super.key,
    required this.label,
    required this.value,
    required this.icon,
    this.sub,
    this.accent = VW.red,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: VW.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: VW.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(7),
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(9),
            ),
            child: Icon(icon, size: 15, color: accent),
          ),
          const SizedBox(height: 14),
          Text(
            value,
            style: const TextStyle(
              fontSize: 30,
              fontWeight: FontWeight.w800,
              height: 1,
              letterSpacing: -1,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: const TextStyle(
                fontSize: 12.5, color: VW.muted, fontWeight: FontWeight.w600),
          ),
          if (sub != null) ...[
            const SizedBox(height: 2),
            Text(sub!, style: TextStyle(fontSize: 11, color: accent)),
          ],
        ],
      ),
    );
  }
}

/// Dependency-free bar chart of episodes per day.
class DailyBars extends StatelessWidget {
  final List<int> counts;
  const DailyBars({super.key, required this.counts});

  @override
  Widget build(BuildContext context) {
    final maxCount = counts.fold<int>(1, (a, b) => b > a ? b : a);
    final now = DateTime.now();

    return Container(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 14),
      decoration: BoxDecoration(
        color: VW.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: VW.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Episodes per day',
              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          const SizedBox(height: 2),
          Text('Last ${counts.length} days',
              style: const TextStyle(fontSize: 11.5, color: VW.muted)),
          const SizedBox(height: 20),
          SizedBox(
            height: 140,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: List.generate(counts.length, (i) {
                final c = counts[i];
                final isToday = i == counts.length - 1;
                final day = now.subtract(Duration(days: counts.length - 1 - i));
                final barColor = c == 0
                    ? VW.line
                    : isToday
                        ? VW.red
                        : VW.red.withValues(alpha: 0.42);
                return Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Text(
                        c == 0 ? '' : '$c',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: isToday ? VW.red : VW.muted,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Expanded(
                        child: FractionallySizedBox(
                          alignment: Alignment.bottomCenter,
                          heightFactor: c == 0 ? 0.02 : c / maxCount,
                          child: Container(
                            margin: EdgeInsets.symmetric(
                                horizontal: counts.length > 14 ? 1.5 : 3),
                            decoration: BoxDecoration(
                              color: barColor,
                              borderRadius: BorderRadius.circular(5),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        weekdayNames[day.weekday - 1].substring(0, 1),
                        style: TextStyle(
                          fontSize: 10.5,
                          color: isToday ? VW.text : VW.muted,
                          fontWeight:
                              isToday ? FontWeight.w800 : FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }
}

class EventTile extends StatelessWidget {
  final DrowsyEvent event;
  final bool showDay;
  const EventTile({super.key, required this.event, this.showDay = false});

  @override
  Widget build(BuildContext context) {
    final color = severityColor(event.severity);
    final plural = event.alerts == 1 ? '' : 's';
    final heading = showDay
        ? '${formatDayLabel(event.time)}, ${formatTime(event.time)}'
        : formatTime(event.time);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
      decoration: BoxDecoration(
        color: VW.surface,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: VW.line),
      ),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 42,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(3),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        heading,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 14),
                      ),
                    ),
                    if (event.escalated) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: VW.red.withValues(alpha: 0.16),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Text(
                          'WhatsApp sent',
                          style: TextStyle(
                              fontSize: 9.5,
                              color: VW.red,
                              fontWeight: FontWeight.w700),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  'Eyes closed ${formatSeconds(event.eyesClosed)}  ·  ${event.alerts} alert$plural',
                  style: const TextStyle(fontSize: 12, color: VW.muted),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            event.severity.label,
            style: TextStyle(
                fontSize: 11.5, color: color, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}
