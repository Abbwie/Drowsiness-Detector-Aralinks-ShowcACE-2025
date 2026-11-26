import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';

/// Read a timestamp from the relay as an instant in UTC.
///
/// The relay stamps UTC on everything it sends, but a naive value can still
/// arrive from an older deploy or one running on SQLite instead of Postgres.
/// DateTime.parse would read that as the phone's own local time, putting every
/// episode eight hours out in Manila, so assume UTC when no zone is given.
DateTime parseInstant(String raw) {
  final hasZone = raw.endsWith('Z') ||
      RegExp(r'[+-]\d{2}:?\d{2}$').hasMatch(raw);
  return DateTime.parse(hasZone ? raw : '${raw}Z').toLocal();
}

/// One episode the detector reported.
class DrowsyEvent {
  final int id;
  final DateTime time; // local time; the relay sends UTC
  /// What the duration measures depends on the kind -- see describeEvent.
  final double seconds;
  final String kind; // DROWSY, MICROSLEEP, HEAD DOWN or YAWN

  DrowsyEvent({
    required this.id,
    required this.time,
    required this.seconds,
    required this.kind,
  });

  factory DrowsyEvent.fromJson(Map<String, dynamic> json) => DrowsyEvent(
        id: json['id'] as int,
        time: parseInstant(json['occurred_at'] as String),
        seconds: (json['seconds'] as num).toDouble(),
        kind: json['kind'] as String? ?? 'DROWSY',
      );
}

/// What the detector is seeing right now.
class LiveStatus {
  final String state;
  final double perclos;
  final DateTime updatedAt;
  final bool online;

  LiveStatus({
    required this.state,
    required this.perclos,
    required this.updatedAt,
    required this.online,
  });

  /// What the app shows before the first reading arrives.
  factory LiveStatus.offline() => LiveStatus(
        state: 'OFFLINE',
        perclos: 0,
        updatedAt: DateTime.now(),
        online: false,
      );

  factory LiveStatus.fromJson(Map<String, dynamic> json) => LiveStatus(
        state: json['state'] as String? ?? 'OFFLINE',
        perclos: (json['perclos'] as num?)?.toDouble() ?? 0,
        updatedAt: parseInstant(json['updated_at'] as String),
        online: json['online'] as bool? ?? false,
      );
}

/// The alert switches, shared with the detector through the relay.
///
/// The detector polls these every few seconds, so flipping one here reaches the
/// laptop without touching it. Both default on: if the relay ever answers
/// without a field, the safe reading is that the alert is armed.
class AlertSettings {
  final bool buzzerOn;
  final bool voiceAlertOn;

  /// Who to message, and whether to message them at all.
  ///
  /// On the relay rather than on this phone because the detector is what
  /// sends the message, and the detector runs on the laptop -- it has no way
  /// to read SharedPreferences. Keeping it local was why the app could
  /// promise to message someone the detector had never heard of.
  final bool notifyContactOn;
  final String contactName;
  final String contactNumber;

  /// Detection tuning, kept on the relay for the same reason as the rest:
  /// the detector is what acts on it, and the detector is not this phone.
  ///
  /// headDropRatio is the fraction of the driver's own upright posture that
  /// still counts as head-up. Higher reacts to a smaller nod. It is worth a
  /// control rather than a constant because the right value depends on where
  /// the camera sits relative to the eyes, which differs per car and per rig.
  final double headDropRatio;
  final double noFaceAlertSeconds;
  final double noFaceContactSeconds;

  const AlertSettings({
    required this.buzzerOn,
    required this.voiceAlertOn,
    this.notifyContactOn = false,
    this.contactName = '',
    this.contactNumber = '',
    this.headDropRatio = 0.72,
    this.noFaceAlertSeconds = 20,
    this.noFaceContactSeconds = 30,
  });

  factory AlertSettings.fromJson(Map<String, dynamic> json) => AlertSettings(
        buzzerOn: json['buzzer_on'] as bool? ?? true,
        voiceAlertOn: json['voice_alert_on'] as bool? ?? true,
        // Off and empty when the relay does not send them. A relay on an
        // older deploy saying nothing is not consent to message anybody --
        // which is the opposite of how the two switches above default.
        notifyContactOn: json['notify_contact_on'] as bool? ?? false,
        contactName: json['contact_name'] as String? ?? '',
        contactNumber: json['contact_number'] as String? ?? '',
        headDropRatio: (json['head_drop_ratio'] as num?)?.toDouble() ?? 0.72,
        noFaceAlertSeconds:
            (json['no_face_alert_seconds'] as num?)?.toDouble() ?? 20,
        noFaceContactSeconds:
            (json['no_face_contact_seconds'] as num?)?.toDouble() ?? 30,
      );

  Map<String, dynamic> toJson() => {
        'buzzer_on': buzzerOn,
        'voice_alert_on': voiceAlertOn,
        'notify_contact_on': notifyContactOn,
        'contact_name': contactName,
        'contact_number': contactNumber,
        'head_drop_ratio': headDropRatio,
        'no_face_alert_seconds': noFaceAlertSeconds,
        'no_face_contact_seconds': noFaceContactSeconds,
      };
}

/// A failure worth showing the driver, already phrased for a snackbar.
class ApiException implements Exception {
  final String message;
  ApiException(this.message);

  @override
  String toString() => message;
}

class VigiWatchApi {
  final String baseUrl;
  final String key;
  final http.Client _client;

  VigiWatchApi({String? baseUrl, String? key, http.Client? client})
      : baseUrl = _normalise(baseUrl ?? apiUrl),
        key = key ?? apiKey,
        _client = client ?? http.Client();

  /// Railway shows the host without a scheme and that is what gets pasted, so
  /// fill in https:// rather than failing on a relative URI. The detector does
  /// the same with its own copy of the address.
  static String _normalise(String url) {
    var u = url.trim().replaceAll(RegExp(r'/+$'), '');
    if (u.isEmpty) return u;
    if (!u.startsWith('http://') && !u.startsWith('https://')) {
      u = 'https://$u';
    }
    return u;
  }

  Map<String, String> get _headers => {
        'X-API-Key': key,
        'Content-Type': 'application/json',
      };

  /// Returns the driver's display name. Throws [ApiException] on a bad login.
  Future<String> login(String username, String password) async {
    final json = await _send(
      'POST',
      '/login',
      body: {'username': username, 'password': password},
      onUnauthorized: 'Wrong username or password.',
    );
    return (json as Map<String, dynamic>)['driver_name'] as String;
  }

  Future<LiveStatus> status() async =>
      LiveStatus.fromJson(await _send('GET', '/status') as Map<String, dynamic>);

  Future<List<DrowsyEvent>> events({int days = 7}) async {
    final json = await _send('GET', '/events?days=$days') as List<dynamic>;
    return json
        .map((e) => DrowsyEvent.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Wipes the episode history. Returns how many the relay actually removed.
  Future<int> clearEvents() async =>
      _deleted(await _send('DELETE', '/events'));

  /// Removes one episode. 0 means it was already gone, which is not an error.
  Future<int> deleteEvent(int id) async =>
      _deleted(await _send('DELETE', '/events/$id'));

  static int _deleted(dynamic json) =>
      ((json as Map<String, dynamic>)['deleted'] as num?)?.toInt() ?? 0;

  Future<AlertSettings> settings() async => AlertSettings.fromJson(
      await _send('GET', '/settings') as Map<String, dynamic>);

  /// Returns what the relay stored, so the page shows the saved state rather
  /// than assuming the write landed exactly as sent.
  Future<AlertSettings> saveSettings(AlertSettings value) async =>
      AlertSettings.fromJson(await _send('PUT', '/settings', body: value.toJson())
          as Map<String, dynamic>);

  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
    String onUnauthorized = 'This app is not authorised to reach the relay.',
  }) async {
    if (baseUrl.isEmpty || key.isEmpty) {
      throw ApiException(
          'The app was built without API_URL or API_KEY. See run.example.ps1.');
    }

    final uri = Uri.parse('$baseUrl$path');
    late final http.Response res;
    try {
      final Future<http.Response> call;
      if (method == 'POST') {
        call = _client.post(uri, headers: _headers, body: jsonEncode(body));
      } else if (method == 'PUT') {
        call = _client.put(uri, headers: _headers, body: jsonEncode(body));
      } else if (method == 'DELETE') {
        call = _client.delete(uri, headers: _headers);
      } else {
        call = _client.get(uri, headers: _headers);
      }
      // A phone on bad mobile data should give up and say so rather than
      // leave the page spinning; the detector posts every second anyway.
      res = await call.timeout(const Duration(seconds: 10));
    } on TimeoutException {
      throw ApiException('The relay did not answer in time.');
    } catch (_) {
      throw ApiException('Cannot reach the relay. Check your connection.');
    }

    // A rejected API key and a rejected password are both 401, and reporting
    // the key problem as "wrong password" sends you hunting for the wrong
    // thing. The relay names which one it was, so pass that on.
    if (res.statusCode == 401) {
      throw ApiException(_detail(res.body).toLowerCase().contains('api key')
          ? 'The relay rejected this app\'s API key. Check the '
              'API_KEY it was built with.'
          : onUnauthorized);
    }
    if (res.statusCode >= 400) {
      throw ApiException('The relay returned an error (${res.statusCode}).');
    }

    try {
      return jsonDecode(res.body);
    } catch (_) {
      throw ApiException('The relay sent something the app could not read.');
    }
  }

  /// FastAPI puts the reason in `detail`. Returns '' if the body is not that
  /// shape, which is fine -- the caller falls back to its own wording.
  static String _detail(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } catch (_) {
      // Not JSON. Nothing to learn from it.
    }
    return '';
  }

  void close() => _client.close();
}
