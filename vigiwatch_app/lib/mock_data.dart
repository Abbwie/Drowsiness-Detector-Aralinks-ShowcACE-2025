// Fake data for the mockup. No backend yet.

class DrowsyEvent {
  final DateTime time;
  final double seconds; // how long the eyes stayed closed

  DrowsyEvent(this.time, this.seconds);
}

final _now = DateTime.now();

final driverName = 'Abigail Jurado';

DateTime _day(int daysAgo, int hour, int minute) {
  final d = DateTime(_now.year, _now.month, _now.day - daysAgo);
  return DateTime(d.year, d.month, d.day, hour, minute);
}

final events = [
  DrowsyEvent(_day(0, 21, 30), 1.7),
  DrowsyEvent(_day(0, 13, 15), 5.3),
  DrowsyEvent(_day(0, 6, 40), 2.1),
  DrowsyEvent(_day(1, 22, 05), 3.4),
  DrowsyEvent(_day(1, 15, 20), 1.9),
  DrowsyEvent(_day(2, 23, 10), 6.2),
  DrowsyEvent(_day(2, 19, 45), 2.8),
  DrowsyEvent(_day(2, 14, 30), 4.1),
  DrowsyEvent(_day(2, 8, 15), 1.5),
  DrowsyEvent(_day(4, 17, 50), 3.0),
  DrowsyEvent(_day(5, 20, 25), 2.4),
  DrowsyEvent(_day(5, 16, 05), 7.1),
  DrowsyEvent(_day(5, 9, 40), 1.8),
  DrowsyEvent(_day(6, 18, 35), 2.6),
  DrowsyEvent(_day(6, 7, 55), 3.9),
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

// Settings the user can change in the app.
String emergencyName = 'Mama';
String emergencyNumber = '+63 967 009 2434';
bool voiceAlertOn = true;
bool buzzerOn = false;
