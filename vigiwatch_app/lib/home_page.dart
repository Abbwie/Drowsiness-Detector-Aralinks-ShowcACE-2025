import 'package:flutter/material.dart';
import 'mock_data.dart';
import 'theme.dart';
import 'widgets.dart';

class HomePage extends StatelessWidget {
  final VoidCallback onSeeAll;
  const HomePage({super.key, required this.onSeeAll});

  @override
  Widget build(BuildContext context) {
    final recent = events.take(3).toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Hi, $driverName', style: const TextStyle(fontSize: 16)),
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
                '$weekCount',
                style: const TextStyle(fontSize: 44, fontWeight: FontWeight.bold),
              ),
              const Text('times drowsy', style: TextStyle(color: muted)),
              const SizedBox(height: 12),
              Text('Today: $todayCount', style: const TextStyle(fontSize: 14)),
            ],
          ),
        ),
        const SizedBox(height: 16),
        const WeekChart(),
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
        for (final e in recent) EventTile(event: e),
      ],
    );
  }
}
