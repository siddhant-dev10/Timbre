import 'package:flutter_test/flutter_test.dart';
import 'package:timbre/services/mock_citizen_repository.dart';

void main() {
  group('MockCitizenRepository Lifecycle & Simulation Tests', () {
    late MockCitizenRepository repo;

    setUp(() {
      repo = MockCitizenRepository();
    });

    test('getCitizens returns synthetic records with fictional flag', () async {
      final citizens = await repo.getCitizens();
      expect(citizens.isNotEmpty, true);
      for (final c in citizens) {
        expect(c.isFictional, true);
      }
    });

    test('getCitizens search filter matches name or state', () async {
      final results = await repo.getCitizens(query: 'Aarav');
      expect(results.length, 1);
      expect(results.first.firstName, 'Aarav');

      final gujaratCitizens = await repo.getCitizens(query: 'Gujarat');
      expect(gujaratCitizens.isNotEmpty, true);
    });

    test('Simulating DOB change to age 18 detects MILESTONE_AGE_18 and creates call job', () async {
      final citizens = await repo.getCitizens();
      final aarav = citizens.firstWhere((c) => c.firstName == 'Aarav');

      // Aarav starts as 17 years old
      expect(aarav.age, 17);

      final now = DateTime.now();
      // Set DOB to exactly 18 years ago
      final eighteenthDob = DateTime(now.year - 18, now.month, now.day);

      final result = await repo.updateCitizenDob(aarav.id, eighteenthDob);
      expect(result.previousAge, 17);
      expect(result.newAge, 18);
      expect(result.eventDetected, 'MILESTONE_AGE_18');
      expect(result.generatedCallJob, isNotNull);
      expect(result.generatedCallJob!.jobStatus, 'QUEUED');
      expect(
        result.generatedCallJob!.idempotencyKey.contains(
          'CALL_AGE18_${aarav.id}',
        ),
        true,
      );

      // Verify that repeating the simulation does not create a duplicate call job (idempotency)
      final repeatResult = await repo.updateCitizenDob(aarav.id, eighteenthDob);
      expect(
        repeatResult.generatedCallJob?.idempotencyKey,
        result.generatedCallJob?.idempotencyKey,
      );
    });

    test('evaluateEligibility qualifies 18-year-old for Voter ID and Learner Licence', () async {
      final citizens = await repo.getCitizens();
      final priya = citizens.firstWhere((c) => c.firstName == 'Priya');
      expect(priya.isAdult, true);

      final results = await repo.evaluateEligibility(priya.id);
      final voterId = results.firstWhere(
        (r) => r.service.serviceCode == 'VOTER_ID_ECI',
      );
      final licence = results.firstWhere(
        (r) => r.service.serviceCode == 'LEARNERS_LICENCE_MORTH',
      );

      expect(voterId.isEligible, true);
      expect(voterId.service.statutoryFeeInr, 0.0);
      expect(licence.isEligible, true);
      expect(licence.service.statutoryFeeInr, 200.0);
    });
  });
}
