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

  /// Wipes everything. Confirmed in a dialog here before it is called.
  final Future<void> Function() onClear;

  /// Removes one episode, from a swipe. The caller drops it from its own list
  /// straight away -- a Dismissible left in the tree after the swipe throws.
  final Future<void> Function(int id) onDelete;

  const HistoryPage({
    super.key,
    required this.events,
    required this.loading,
    required this.error,
    required this.onRefresh,
    required this.onClear,
    required this.onDelete,
  });

  Future<void> _confirmClear(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: card,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: const Text('Delete all history?'),
        content: Text(
          events.length == 1
              ? 'This removes the one recorded episode. It cannot be undone.'
              : 'This removes all ${events.length} recorded episodes. '
                  'It cannot be undone.',
          style: const TextStyle(fontSize: 13, color: muted),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: muted)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete', style: TextStyle(color: red)),
          ),
        ],
      ),
    );
    // Null when the dialog is dismissed by tapping outside, which is a no.
    if (confirmed == true) await onClear();
  }

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
            for (final e in g.value)
              Dismissible(
                key: ValueKey(e.id),
                // One direction only. A list you can wipe by brushing either
                // way is a list you delete from by accident.
                direction: DismissDirection.endToStart,
                background: Container(
                  alignment: Alignment.centerRight,
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.only(right: 18),
                  decoration: BoxDecoration(
                    color: red,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.delete_outline, color: Colors.white),
                ),
                onDismissed: (_) => onDelete(e.id),
                child: EventTile(event: e, showDay: false),
              ),
            const SizedBox(height: 16),
          ],
          if (events.isNotEmpty) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () => _confirmClear(context),
              icon: const Icon(Icons.delete_outline, size: 18),
              label: const Text('Delete all history'),
              style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(48),
                side: const BorderSide(color: line),
                foregroundColor: red,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
            ),
            const SizedBox(height: 10),
            const Text(
              'Swipe an entry left to remove just that one.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: muted),
            ),
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
