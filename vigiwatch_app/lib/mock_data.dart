// Fake data for the mockup. No backend yet.

class DrowsyEvent {
  final DateTime time;
  final double seconds; // how long the eyes stayed closed

  DrowsyEvent(this.time, this.seconds);
}

final _now = DateTime.now();

final driverName = 'Abigail Jurado';

final events = [
  DrowsyEvent(_now.subtract(const Duration(minutes: 40)), 1.7),
  DrowsyEvent(_now.subtract(const Duration(hours: 3)), 5.3),
  DrowsyEvent(_now.subtract(const Duration(hours: 6)), 2.1),
  DrowsyEvent(_now.subtract(const Duration(days: 1, hours: 2)), 3.4),
  DrowsyEvent(_now.subtract(const Duration(days: 1, hours: 9)), 1.9),
  DrowsyEvent(_now.subtract(const Duration(days: 2, hours: 1)), 6.2),
  DrowsyEvent(_now.subtract(const Duration(days: 2, hours: 4)), 2.8),
  DrowsyEvent(_now.subtract(const Duration(days: 2, hours: 7)), 4.1),
  DrowsyEvent(_now.subtract(const Duration(days: 2, hours: 10)), 1.5),
  DrowsyEvent(_now.subtract(const Duration(days: 4, hours: 5)), 3.0),
  DrowsyEvent(_now.subtract(const Duration(days: 5, hours: 2)), 2.4),
  DrowsyEvent(_now.subtract(const Duration(days: 5, hours: 6)), 7.1),
  DrowsyEvent(_now.subtract(const Duration(days: 5, hours: 11)), 1.8),
  DrowsyEvent(_now.subtract(const Duration(days: 6, hours: 3)), 2.6),
  DrowsyEvent(_now.subtract(const Duration(days: 6, hours: 8)), 3.9),
];

bool _sameDay(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

int get todayCount => events.where((e) => _sameDay(e.time, _now)).length;

int get weekCount => events.length;

/// Episodes per day for the last 7 days, oldest first.
List<int> get weekCounts => List.generate(7, (i) {
      final day = _now.subtract(Duration(days: 6 - i));
      return events.where((e) => _sameDay(e.time, day)).length;
    });
