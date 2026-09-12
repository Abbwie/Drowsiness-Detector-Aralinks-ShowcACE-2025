import 'package:flutter/material.dart';

import 'api.dart';
import 'stats.dart';
import 'theme.dart';
import 'widgets.dart';

class HomePage extends StatelessWidget {
  final String driverName;
  final LiveStatus status;
  final List<DrowsyEvent> events;
  final bool loading;
  final String? error;
  final Future<void> Function() onRefresh;
  final VoidCallback onSeeAll;

  const HomePage({
    super.key,
    required this.driverName,
    required this.status,
    required this.events,
    required this.loading,
    required this.error,
    required this.onRefresh,
    required this.onSeeAll,
  });

  @override
  Widget build(BuildContext context) {
    final recent = events.take(3).toList();
    final today = todayCount(events);

    return RefreshIndicator(
      color: red,
      backgroundColor: card,
      onRefresh: onRefresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Hi, $driverName', style: const TextStyle(fontSize: 16)),
          const SizedBox(height: 16),
          StatusCard(status: status),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: card,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: line),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('This week', style: TextStyle(color: muted)),
                const SizedBox(height: 8),
                Text(
                  loading ? '--' : '${events.length}',
                  style: const TextStyle(
                      fontSize: 44, fontWeight: FontWeight.bold),
                ),
                const Text('times drowsy', style: TextStyle(color: muted)),
                const SizedBox(height: 12),
                Text(loading ? 'Today: --' : 'Today: $today',
                    style: const TextStyle(fontSize: 14)),
              ],
            ),
          ),
          const SizedBox(height: 16),
          WeekChart(counts: weekCounts(events)),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Recent', style: TextStyle(fontSize: 16)),
              TextButton(
                onPressed: onSeeAll,
                child: const Text('See all', style: TextStyle(color: red)),
              ),
            ],
          ),
          const SizedBox(height: 4),
          if (error != null)
            ErrorNote(message: error!, onRetry: onRefresh)
          else if (loading)
            const Center(
                child: Padding(
              padding: EdgeInsets.all(24),
              child: CircularProgressIndicator(color: red),
            ))
          else if (recent.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Text('Nothing yet this week. Drive safe.',
                  style: TextStyle(color: muted)),
            )
          else
            for (final e in recent) EventTile(event: e),
        ],
      ),
    );
  }
}
