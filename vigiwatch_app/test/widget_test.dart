import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:vigiwatch_app/api.dart';
import 'package:vigiwatch_app/login_page.dart';
import 'package:vigiwatch_app/theme.dart';

/// A relay that answers from memory, so the tests never touch the network.
VigiWatchApi fakeApi({
  bool goodLogin = true,
  List<Map<String, dynamic>>? events,
  Map<String, dynamic>? status,
}) {
  final client = MockClient((req) async {
    if (req.url.path == '/login') {
      return goodLogin
          ? http.Response(jsonEncode({'driver_name': 'Abigail Jurado'}), 200)
          : http.Response(jsonEncode({'detail': 'nope'}), 401);
    }
    if (req.url.path == '/status') {
      return http.Response(
        jsonEncode(status ??
            {
              'state': 'ALERT',
              'perclos': 0.12,
              'updated_at': '2026-09-12T02:00:00Z',
              'online': true,
            }),
        200,
      );
    }
    if (req.url.path == '/events') {
      return http.Response(jsonEncode(events ?? _sampleEvents), 200);
    }
    return http.Response('not found', 404);
  });

  return VigiWatchApi(
      baseUrl: 'https://relay.test', key: 'test-key', client: client);
}

final _sampleEvents = [
  {
    'id': 2,
    'occurred_at': '2026-09-12T01:30:00Z',
    'seconds': 5.3,
    'kind': 'MICROSLEEP',
  },
  {
    'id': 1,
    'occurred_at': '2026-09-11T22:05:00Z',
    'seconds': 0.0,
    'kind': 'YAWN',
  },
];

Widget wrap(Widget child) =>
    MaterialApp(theme: appTheme(), home: child);

/// Signs in and lands on the home shell.
Future<void> signIn(WidgetTester tester, {VigiWatchApi? api}) async {
  await tester.pumpWidget(wrap(LoginPage(api: api ?? fakeApi())));
  await tester.enterText(find.byType(TextField).first, 'abigail');
  await tester.enterText(find.byType(TextField).last, 'secret');
  await tester.tap(find.text('Login'));
  await tester.pumpAndSettle();
}

/// Unmounts the tree so HomeShell's polling timers are cancelled before the
/// test ends -- a live Timer.periodic fails the test otherwise.
Future<void> tearDownTree(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox());
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('login goes to the home page', (tester) async {
    await signIn(tester);

    expect(find.text('Hi, Abigail Jurado'), findsOneWidget);
    expect(find.text('This week'), findsOneWidget);
    expect(find.text('times drowsy'), findsOneWidget);

    await tearDownTree(tester);
  });

  testWidgets('a rejected login stays put and explains why', (tester) async {
    await tester.pumpWidget(wrap(LoginPage(api: fakeApi(goodLogin: false))));
    await tester.enterText(find.byType(TextField).first, 'abigail');
    await tester.enterText(find.byType(TextField).last, 'wrong');
    await tester.tap(find.text('Login'));
    await tester.pumpAndSettle();

    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('Wrong username or password.'), findsOneWidget);
  });

  testWidgets('the live tile reflects the detector state', (tester) async {
    await signIn(tester);
    expect(find.text('Awake'), findsOneWidget);
    await tearDownTree(tester);

    await signIn(
      tester,
      api: fakeApi(status: {
        'state': 'MICROSLEEP',
        'perclos': 0.9,
        'updated_at': '2026-09-12T02:00:00Z',
        'online': true,
      }),
    );
    expect(find.text('Microsleep'), findsOneWidget);
    await tearDownTree(tester);
  });

  testWidgets('a stale heartbeat reads as offline', (tester) async {
    await signIn(
      tester,
      api: fakeApi(status: {
        'state': 'ALERT',
        'perclos': 0.1,
        'updated_at': '2026-09-11T02:00:00Z',
        'online': false,
      }),
    );

    // Never show a reassuring "Awake" from a detector that stopped reporting.
    expect(find.text('Detector offline'), findsOneWidget);
    expect(find.text('Awake'), findsNothing);

    await tearDownTree(tester);
  });

  testWidgets('history tab lists the events', (tester) async {
    await signIn(tester);

    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();

    expect(find.textContaining('times in the last 7 days'), findsOneWidget);
    expect(find.textContaining('5.3s'), findsOneWidget);
    expect(find.text('Yawn'), findsOneWidget);

    await tearDownTree(tester);
  });

  testWidgets('an empty week says so instead of showing nothing',
      (tester) async {
    await signIn(tester, api: fakeApi(events: []));

    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();

    expect(find.text('No episodes recorded yet.'), findsOneWidget);

    await tearDownTree(tester);
  });

  testWidgets('settings tab shows the emergency contact', (tester) async {
    await signIn(tester);

    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();

    expect(find.text('Emergency contact'), findsOneWidget);
    expect(find.text('+63 967 009 2434'), findsOneWidget);

    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(find.text('Settings saved'), findsOneWidget);

    await tearDownTree(tester);
  });

  group('a 401 says which credential was rejected', () {
    VigiWatchApi apiRejecting(String detail) => VigiWatchApi(
          baseUrl: 'https://relay.test',
          key: 'k',
          client: MockClient(
              (_) async => http.Response(jsonEncode({'detail': detail}), 401)),
        );

    test('a bad API key is not reported as a bad password', () async {
      // The whole point: a mistyped --dart-define sends you hunting for the
      // wrong problem if this reads "wrong username or password".
      await expectLater(
        apiRejecting('Bad API key').login('abigail', 'right-password'),
        throwsA(isA<ApiException>()
            .having((e) => e.message, 'message', contains('API key'))),
      );
    });

    test('a bad password still reads as a bad password', () async {
      await expectLater(
        apiRejecting('Wrong username or password').login('abigail', 'nope'),
        throwsA(isA<ApiException>().having(
            (e) => e.message, 'message', 'Wrong username or password.')),
      );
    });

    test('an unparseable body falls back to the caller wording', () async {
      await expectLater(
        VigiWatchApi(
          baseUrl: 'https://relay.test',
          key: 'k',
          client: MockClient((_) async => http.Response('<html>502</html>', 401)),
        ).login('abigail', 'nope'),
        throwsA(isA<ApiException>().having(
            (e) => e.message, 'message', 'Wrong username or password.')),
      );
    });
  });

  test('a bare host gets https:// filled in', () {
    // Railway shows the address without a scheme, and that is what gets pasted
    // into --dart-define.
    expect(VigiWatchApi(baseUrl: 'app.up.railway.app', key: 'k').baseUrl,
        'https://app.up.railway.app');
    expect(VigiWatchApi(baseUrl: 'https://app.up.railway.app/', key: 'k').baseUrl,
        'https://app.up.railway.app');
    expect(VigiWatchApi(baseUrl: 'http://127.0.0.1:8077', key: 'k').baseUrl,
        'http://127.0.0.1:8077');
  });

  test('a UTC timestamp becomes local time', () {
    final e = DrowsyEvent.fromJson({
      'id': 1,
      'occurred_at': '2026-09-12T01:30:00Z',
      'seconds': 5.3,
      'kind': 'MICROSLEEP',
    });

    // Whatever zone the test machine is in, the instant must survive the trip.
    expect(e.time.isUtc, isFalse);
    expect(e.time.toUtc(), DateTime.utc(2026, 9, 12, 1, 30));
  });

  test('a timestamp with no zone is read as UTC, not as local time', () {
    // What an older deploy, or one on SQLite rather than Postgres, sends.
    // Trusting the phone's zone here would put every episode hours out.
    expect(parseInstant('2026-09-12T01:30:00.123456').toUtc(),
        DateTime.utc(2026, 9, 12, 1, 30, 0, 123, 456));

    // An explicit offset is still honoured rather than overwritten.
    expect(parseInstant('2026-09-12T09:30:00+08:00').toUtc(),
        DateTime.utc(2026, 9, 12, 1, 30));
    expect(parseInstant('2026-09-12T01:30:00Z').toUtc(),
        DateTime.utc(2026, 9, 12, 1, 30));
  });
}
