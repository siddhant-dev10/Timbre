import 'package:flutter_test/flutter_test.dart';
import 'package:timbre/services/mock_citizen_repository.dart';
import 'package:timbre/state/app_state.dart';

void main() {
  group('AppState Tests', () {
    late AppState state;

    setUp(() {
      state = AppState(repository: MockCitizenRepository());
    });

    test('init loads citizens, call jobs, and services', () async {
      await state.init();
      expect(state.citizens.isNotEmpty, true);
      expect(state.selectedCitizen, isNotNull);
      expect(state.callJobs.isNotEmpty, true);
      expect(state.services.isNotEmpty, true);
      expect(state.isDemoMode, true);
    });

    test(
      'selectCitizen updates selected citizen and loads eligibility',
      () async {
        await state.init();
        final target = state.citizens.last;
        await state.selectCitizen(target);

        expect(state.selectedCitizen?.id, target.id);
        expect(state.getEligibilityForSelected().isNotEmpty, true);
      },
    );

    test('simulateDobChange triggers reactive state updates', () async {
      await state.init();
      final aarav = state.citizens.firstWhere((c) => c.firstName == 'Aarav');
      final now = DateTime.now();
      final dob18 = DateTime(now.year - 18, now.month, now.day);

      await state.simulateDobChange(aarav.id, dob18);
      expect(state.lastSimulationResult, isNotNull);
      expect(state.lastSimulationResult?.eventDetected, 'MILESTONE_AGE_18');
      expect(state.lastSimulationResult?.newAge, 18);
    });
  });
}
