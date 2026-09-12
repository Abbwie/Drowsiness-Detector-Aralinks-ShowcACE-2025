import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';

/// One episode the detector reported.
class DrowsyEvent {
  final int id;
  final DateTime time; // local time; the relay sends UTC
  final double seconds; // how long the eyes stayed shut
  final String kind; // DROWSY, MICROSLEEP or YAWN

  DrowsyEvent({
    required this.id,
    required this.time,
    required this.seconds,
    required this.kind,
  });

  factory DrowsyEvent.fromJson(Map<String, dynamic> json) => DrowsyEvent(
        id: json['id'] as int,
        // The relay stamps UTC on every timestamp, so parse gives a UTC value
        // and toLocal() puts it back in the driver's own hours.
        time: DateTime.parse(json['occurred_at'] as String).toLocal(),
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
        updatedAt: DateTime.parse(json['updated_at'] as String).toLocal(),
        online: json['online'] as bool? ?? false,
      );
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
      : baseUrl = (baseUrl ?? apiUrl).replaceAll(RegExp(r'/+$'), ''),
        key = key ?? apiKey,
        _client = client ?? http.Client();

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
      res = await (method == 'POST'
              ? _client.post(uri, headers: _headers, body: jsonEncode(body))
              : _client.get(uri, headers: _headers))
          // A phone on bad mobile data should give up and say so rather than
          // leave the page spinning; the detector posts every second anyway.
          .timeout(const Duration(seconds: 10));
    } on TimeoutException {
      throw ApiException('The relay did not answer in time.');
    } catch (_) {
      throw ApiException('Cannot reach the relay. Check your connection.');
    }

    if (res.statusCode == 401) throw ApiException(onUnauthorized);
    if (res.statusCode >= 400) {
      throw ApiException('The relay returned an error (${res.statusCode}).');
    }

    try {
      return jsonDecode(res.body);
    } catch (_) {
      throw ApiException('The relay sent something the app could not read.');
    }
  }

  void close() => _client.close();
}
