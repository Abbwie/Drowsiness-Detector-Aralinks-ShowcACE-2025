import 'package:flutter/material.dart';
import 'mock_data.dart';
import 'theme.dart';
import 'widgets.dart';

class HistoryPage extends StatelessWidget {
  const HistoryPage({super.key});

  @override
  Widget build(BuildContext context) {
    // Group the events under the day they happened.
    final byDay = <DateTime, List<DrowsyEvent>>{};
    for (final e in events) {
      final day = DateTime(e.time.year, e.time.month, e.time.day);
      byDay.putIfAbsent(day, () => []).add(e);
    }
    final days = byDay.keys.toList()..sort((a, b) => b.compareTo(a));

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          '${events.length} times in the last 7 days',
          style: const TextStyle(color: muted),
        ),
        const SizedBox(height: 20),
        for (final day in days) ...[
          _DayHeader(day: day, count: byDay[day]!.length),
          for (final e in byDay[day]!) EventTile(event: e, showDay: false),
          const SizedBox(height: 16),
        ],
      ],
    );
  }
}

class _DayHeader extends StatelessWidget {
  final DateTime day;
  final int count;

  const _DayHeader({required this.day, required this.count});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Text(
            formatDay(day),
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
          ),
          const SizedBox(width: 8),
          Text(
            formatDate(day),
            style: const TextStyle(fontSize: 12, color: muted),
          ),
          const Spacer(),
          Text(
            count == 1 ? '1 time' : '$count times',
            style: const TextStyle(fontSize: 12, color: muted),
          ),
        ],
      ),
    );
  }
}
