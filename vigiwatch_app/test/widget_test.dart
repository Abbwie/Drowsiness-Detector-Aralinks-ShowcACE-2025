import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vigiwatch_app/main.dart';

void main() {
  testWidgets('login screen signs in and lands on the tracker',
      (WidgetTester tester) async {
    await tester.pumpWidget(const VigiWatchApp());

    // Login is the entry point.
    expect(find.text('VigiWatch'), findsOneWidget);
    expect(find.text('SIGN IN'), findsOneWidget);

    await tester.tap(find.text('SIGN IN'));
    await tester.pump(const Duration(milliseconds: 950));
    await tester.pumpAndSettle();

    // Tracker hero and the bottom navigation are present.
    expect(find.text('DROWSY EPISODES'), findsOneWidget);
    expect(find.text('Tracker'), findsOneWidget);

    // The episode list sits below the fold, so scroll it into view.
    await tester.dragUntilVisible(
      find.text('Recent episodes'),
      find.byType(ListView).first,
      const Offset(0, -300),
    );
    expect(find.text('Recent episodes'), findsOneWidget);
  });

  testWidgets('range selector switches the tracked period',
      (WidgetTester tester) async {
    await tester.pumpWidget(const VigiWatchApp());
    await tester.tap(find.text('SIGN IN'));
    await tester.pump(const Duration(milliseconds: 950));
    await tester.pumpAndSettle();

    // Default period is 7 days; today's count should differ from the week.
    expect(find.text('7 days'), findsOneWidget);
    await tester.tap(find.text('Today'));
    await tester.pumpAndSettle();

    expect(find.text('You were caught drowsy today.'), findsOneWidget);
  });

  testWidgets('history tab lists every recorded episode',
      (WidgetTester tester) async {
    await tester.pumpWidget(const VigiWatchApp());
    await tester.tap(find.text('SIGN IN'));
    await tester.pump(const Duration(milliseconds: 950));
    await tester.pumpAndSettle();

    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();

    expect(find.textContaining('episodes recorded over'), findsOneWidget);
  });
}
