import 'package:flutter_test/flutter_test.dart';
import 'package:timbre/models/citizen.dart';

void main() {
  group('Citizen Model Tests', () {
    test('calculateAge computes exact age correctly', () {
      final refDate = DateTime(2026, 10, 25);

      // Born exactly 18 years ago today -> age 18
      final dob18 = DateTime(2008, 10, 25);
      expect(Citizen.calculateAge(dob18, refDate), 18);

      // Birthday tomorrow -> still 17
      final dob17 = DateTime(2008, 10, 26);
      expect(Citizen.calculateAge(dob17, refDate), 17);

      // Born on leap day 2008-02-29, evaluated on 2026-03-01 -> age 18
      final leapDob = DateTime(2008, 2, 29);
      expect(Citizen.calculateAge(leapDob, DateTime(2026, 3, 1)), 18);
    });

    test('toJson and fromJson maintain data integrity', () {
      final citizen = Citizen(
        id: 'cit-test-01',
        firstName: 'Aarav',
        lastName: 'Sharma',
        dateOfBirth: DateTime(2008, 10, 21),
        gender: 'MALE',
        phoneNumber: '+91-99999-00012',
        state: 'Uttar Pradesh',
        district: 'Lucknow',
        pincode: '226001',
        simulatedIncomeBracket: 'MIDDLE',
        isFictional: true,
      );

      final json = citizen.toJson();
      expect(json['first_name'], 'Aarav');
      expect(json['is_fictional'], true);
      expect(json['date_of_birth'], '2008-10-21');

      final reconstructed = Citizen.fromJson(json);
      expect(reconstructed.id, citizen.id);
      expect(reconstructed.fullName, 'Aarav Sharma');
      expect(reconstructed.state, 'Uttar Pradesh');
    });

    test('copyWith updates specified fields correctly', () {
      final citizen = Citizen(
        id: 'cit-01',
        firstName: 'Priya',
        lastName: 'Patel',
        dateOfBirth: DateTime(2007, 4, 12),
        gender: 'FEMALE',
        phoneNumber: '+91-99999-00013',
        state: 'Gujarat',
        district: 'Ahmedabad',
        pincode: '380001',
        simulatedIncomeBracket: 'LOW',
      );

      final newDob = DateTime(2008, 10, 10);
      final updated = citizen.copyWith(dateOfBirth: newDob);
      expect(updated.dateOfBirth, newDob);
      expect(updated.firstName, 'Priya');
      expect(updated.state, 'Gujarat');
    });
  });
}
