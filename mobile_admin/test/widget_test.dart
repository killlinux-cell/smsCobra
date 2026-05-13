import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_admin/main.dart';

void main() {
  testWidgets('Admin app démarre', (WidgetTester tester) async {
    await tester.pumpWidget(const CobraAdminBootstrap(firebaseConfigured: false));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
