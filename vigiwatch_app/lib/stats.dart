import 'api.dart';

bool sameDay(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

int todayCount(List<DrowsyEvent> events) {
  final now = DateTime.now();
  return events.where((e) => sameDay(e.time, now)).length;
}

/// Episodes per day for the last 7 days, oldest first -- the home page chart.
List<int> weekCounts(List<DrowsyEvent> events) {
  final now = DateTime.now();
  return List.generate(7, (i) {
    final day = now.subtract(Duration(days: 6 - i));
    return events.where((e) => sameDay(e.time, day)).length;
  });
}

/// Events grouped under the day they happened, newest day first.
List<MapEntry<DateTime, List<DrowsyEvent>>> byDay(List<DrowsyEvent> events) {
  final groups = <DateTime, List<DrowsyEvent>>{};
  for (final e in events) {
    final day = DateTime(e.time.year, e.time.month, e.time.day);
    groups.putIfAbsent(day, () => []).add(e);
  }
  final days = groups.keys.toList()..sort((a, b) => b.compareTo(a));
  return [for (final d in days) MapEntry(d, groups[d]!)];
}
