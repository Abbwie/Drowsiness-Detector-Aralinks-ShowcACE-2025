import 'package:flutter_test/flutter_test.dart';
import 'package:vigiwatch_app/main.dart';

void main() {
  testWidgets('login goes to the home page', (tester) async {
    await tester.pumpWidget(const VigiWatchApp());

    expect(find.text('Sign in'), findsOneWidget);

    await tester.tap(find.text('Login'));
    await tester.pumpAndSettle();

    expect(find.text('This week'), findsOneWidget);
    expect(find.text('times drowsy'), findsOneWidget);
  });

  testWidgets('history tab lists the events', (tester) async {
    await tester.pumpWidget(const VigiWatchApp());
    await tester.tap(find.text('Login'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();

    expect(find.textContaining('times in the last 7 days'), findsOneWidget);
  });
}
