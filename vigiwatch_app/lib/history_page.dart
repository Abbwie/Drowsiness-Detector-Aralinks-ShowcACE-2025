import 'package:flutter/material.dart';
import 'mock_data.dart';
import 'theme.dart';
import 'widgets.dart';

class HistoryPage extends StatelessWidget {
  const HistoryPage({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          '${events.length} times in the last 7 days',
          style: const TextStyle(color: muted),
        ),
        const SizedBox(height: 16),
        for (final e in events) EventTile(event: e),
      ],
    );
  }
}
