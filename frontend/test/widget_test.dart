import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timbre/main.dart';
import 'package:timbre/services/mock_citizen_repository.dart';
import 'package:timbre/state/app_state.dart';
import 'package:timbre/widgets/fictional_banner.dart';

void main() {
  testWidgets('TimbreApp dashboard renders with safety banner and navigation', (
    WidgetTester tester,
  ) async {
    // Set a wide desktop/tablet test viewport
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() => tester.view.resetPhysicalSize());

    final state = AppState(repository: MockCitizenRepository());
    await state.init();

    await tester.pumpWidget(TimbreApp(state: state));
    await tester.pumpAndSettle();

    // Verify Title & Subtitle
    expect(find.text('Timbre'), findsOneWidget);
    expect(
      find.textContaining('AI Government-Services Assistant'),
      findsOneWidget,
    );

    // Verify Safety Banner
    expect(find.byType(FictionalBanner), findsOneWidget);
    expect(find.text('FICTIONAL DATA'), findsOneWidget);

    // Verify Navigation Rail items
    expect(find.text('Overview'), findsOneWidget);
    expect(find.text('Citizens'), findsOneWidget);
    expect(find.text('Simulation'), findsOneWidget);
    expect(find.text('Eligibility'), findsOneWidget);
    expect(find.text('Calls'), findsOneWidget);
    expect(find.text('Schemes'), findsOneWidget);
    expect(find.text('Chat'), findsOneWidget);

    // Verify Dashboard Overview elements
    expect(find.text('Administrative Overview'), findsOneWidget);
    expect(find.text('Total Records'), findsOneWidget);

    // Tap on Citizens tab in Navigation Rail
    await tester.tap(find.text('Citizens'));
    await tester.pumpAndSettle();

    // Verify Citizens Screen loaded
    expect(find.text('Citizen Records'), findsOneWidget);
    expect(find.text('Aarav Sharma'), findsWidgets);

    // Tap on Simulation tab
    await tester.tap(find.text('Simulation'));
    await tester.pumpAndSettle();

    // Verify Simulation Screen loaded
    expect(find.text('Life-Event Simulation Cockpit'), findsOneWidget);
    expect(find.text('Trigger Life-Event Recalculation'), findsOneWidget);

    await tester.tap(find.text('Chat'));
    await tester.pumpAndSettle();
    expect(find.text('Conversation'), findsOneWidget);
    expect(
      find.textContaining('Demo mode makes no provider calls'),
      findsOneWidget,
    );

    await tester.tap(find.text('Calls'));
    await tester.pumpAndSettle();
    expect(find.text('One-recipient test'), findsOneWidget);
    expect(find.text('Run local dry-run'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, '9000000099');
    await tester.tap(
      find.text('The recipient agreed to receive this one test call.'),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Run local dry-run'));
    await tester.pumpAndSettle();
    expect(
      find.text('Local dry-run created. No call was placed.'),
      findsOneWidget,
    );
    expect(find.text('Local simulation'), findsOneWidget);

    await tester.tap(find.text('Approved live test'));
    await tester.pumpAndSettle();
    expect(
      find.text(
        'I verified and approved the configured Bolna caller ID for this test.',
      ),
      findsOneWidget,
    );
    final liveCallButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Review and place one call'),
    );
    expect(liveCallButton.onPressed, isNull);
  });
}
