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

    // Verify Dashboard Overview elements
    expect(find.text('Administrative Overview'), findsOneWidget);
    expect(find.text('Total Fictional Citizens'), findsOneWidget);

    // Tap on Citizens tab in Navigation Rail
    await tester.tap(find.text('Citizens'));
    await tester.pumpAndSettle();

    // Verify Citizens Screen loaded
    expect(find.text('Fictional Citizen Registry'), findsOneWidget);
    expect(find.text('Aarav Sharma'), findsWidgets);

    // Tap on Simulation tab
    await tester.tap(find.text('Simulation'));
    await tester.pumpAndSettle();

    // Verify Simulation Screen loaded
    expect(find.text('Life-Event Simulation Cockpit'), findsOneWidget);
    expect(find.text('Trigger Life-Event Recalculation'), findsOneWidget);
  });
}
