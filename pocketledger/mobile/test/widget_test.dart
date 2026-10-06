import 'package:flutter_test/flutter_test.dart';

import 'package:pocketledger/main.dart';

void main() {
  testWidgets('Capture screen offers a camera', (WidgetTester tester) async {
    await tester.pumpWidget(const PocketLedgerApp());

    expect(find.text('PocketLedger'), findsOneWidget);
    expect(find.text('Camera'), findsOneWidget);
    expect(find.text('Process ledger'), findsNothing);
  });

  testWidgets('Capture screen offers a health score check', (WidgetTester tester) async {
    await tester.pumpWidget(const PocketLedgerApp());

    expect(find.text('Check health score'), findsOneWidget);
  });

  testWidgets('Health card shows score, local band, and actions', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: HealthCard(
          language: 'ChiShona',
          health: {
            'status': 'Established',
            'score': 77,
            'band': 'Good',
            'band_local': {'English': 'Good', 'ChiShona': 'Rakanaka', 'IsiNdebele': 'Lihle'},
            'evidence_level': 'Captured same-day',
            'window': {'start': '2026-08-11', 'end': '2026-10-05', 'trading_days': 44},
            'actions': [
              {'component': 'credit_health', 'English': 'Collect chikwereti before giving new credit.'},
            ],
            'affordability': {
              'safe_daily_repayment_usd': 5.0,
              'indicative_amount_30d_usd': 128.57,
              'note': 'Guide only — not a loan offer. A lender will do its own checks.',
            },
          },
        ),
      ),
    ));

    expect(find.text('77/100'), findsOneWidget);
    expect(find.text('Rakanaka'), findsOneWidget);
    expect(find.text('• Collect chikwereti before giving new credit.'), findsOneWidget);
    expect(find.textContaining(r'$128.57'), findsOneWidget);
  });

  testWidgets('Health card asks for more days when there is no score', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(
        body: HealthCard(
          language: 'English',
          health: {
            'status': 'Not enough data',
            'score': null,
            'record_more_days': 3,
            'window': {'start': '2026-08-11', 'end': '2026-10-05', 'trading_days': 2},
          },
        ),
      ),
    ));

    expect(find.text('Record 3 more trading day(s) to get your score.'), findsOneWidget);
    expect(find.textContaining('/100'), findsNothing);
  });
}
