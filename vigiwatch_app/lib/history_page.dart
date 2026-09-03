import 'package:flutter/material.dart';
import 'mock_data.dart';
import 'theme.dart';
import 'widgets.dart';

/// Full episode log, grouped by day, newest first.
class HistoryPage extends StatelessWidget {
  const HistoryPage({super.key});

  @override
  Widget build(BuildContext context) {
    // Group episodes under their calendar day.
    final grouped = <DateTime, List<DrowsyEvent>>{};
    for (final e in mockEvents) {
      final day = DateTime(e.time.year, e.time.month, e.time.day);
      grouped.putIfAbsent(day, () => []).add(e);
    }
    final days = grouped.keys.toList()..sort((a, b) => b.compareTo(a));

    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
        children: [
          const Text(
            'History',
            style: TextStyle(
                fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -1),
          ),
          const SizedBox(height: 4),
          Text(
            '${mockEvents.length} episodes recorded over ${days.length} days',
            style: const TextStyle(fontSize: 13.5, color: VW.muted),
          ),
          const SizedBox(height: 22),
          for (final day in days) ...[
            Padding(
              padding: const EdgeInsets.only(bottom: 10, top: 6),
              child: Row(
                children: [
                  Text(
                    formatDayLabel(day),
                    style: const TextStyle(
                        fontSize: 13.5, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: Container(height: 1, color: VW.line)),
                  const SizedBox(width: 10),
                  Text(
                    '${grouped[day]!.length}',
                    style: const TextStyle(
                        fontSize: 12,
                        color: VW.muted,
                        fontWeight: FontWeight.w700),
                  ),
                ],
              ),
            ),
            ...grouped[day]!.map((e) => EventTile(event: e)),
            const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}
