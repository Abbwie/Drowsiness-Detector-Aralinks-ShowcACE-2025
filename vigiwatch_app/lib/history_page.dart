import 'package:flutter/material.dart';

import 'api.dart';
import 'stats.dart';
import 'theme.dart';
import 'widgets.dart';

class HistoryPage extends StatelessWidget {
  final List<DrowsyEvent> events;
  final bool loading;
  final String? error;
  final Future<void> Function() onRefresh;

  const HistoryPage({
    super.key,
    required this.events,
    required this.loading,
    required this.error,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Center(child: CircularProgressIndicator(color: red));
    }

    if (error != null) {
      return RefreshIndicator(
        color: red,
        backgroundColor: card,
        onRefresh: onRefresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [ErrorNote(message: error!, onRetry: onRefresh)],
        ),
      );
    }

    final groups = byDay(events);

    return RefreshIndicator(
      color: red,
      backgroundColor: card,
      onRefresh: onRefresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            '${events.length} times in the last 7 days',
            style: const TextStyle(color: muted),
          ),
          const SizedBox(height: 20),
          if (groups.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 40),
              child: Center(
                child: Text('No episodes recorded yet.',
                    style: TextStyle(color: muted)),
              ),
            ),
          for (final g in groups) ...[
            _DayHeader(day: g.key, count: g.value.length),
            for (final e in g.value) EventTile(event: e, showDay: false),
            const SizedBox(height: 16),
          ],
        ],
      ),
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
