import 'package:flutter_test/flutter_test.dart';

import 'package:pocketledger/main.dart';

void main() {
  testWidgets('Capture screen offers a camera', (WidgetTester tester) async {
    await tester.pumpWidget(const PocketLedgerApp());

    expect(find.text('PocketLedger'), findsOneWidget);
    expect(find.text('Camera'), findsOneWidget);
    expect(find.text('Process ledger'), findsNothing);
  });
}
